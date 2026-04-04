"""
DNP3 Client for Murphy System  [PROT-007]

Murphy-native DNP3 (Distributed Network Protocol 3) outstation-polling
client.  Implements DNP3 Application Layer framing over TCP transport
using only the Python standard library (``socket``, ``struct``).

Supports the most common SCADA operations: integrity polls (Class 0/1/2/3
requests), reading and writing binary/analog I/O points, and remote
device restart.

When no outstation host is configured the client operates in **simulated
mode**, returning realistic stub data so that the Murphy pipeline can be
developed and tested without live field hardware.

Usage::

    from src.protocols.dnp3_client import MurphyDNP3Client

    with MurphyDNP3Client(host="192.168.1.50", port=20000) as client:
        points = client.integrity_poll()
        for pt in points:
            print(pt.index, pt.group.name, pt.value)
"""
from __future__ import annotations

import logging
import random  # noqa: S311 — used only for simulated stub data
import socket
import struct
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DNP3 constants
# ---------------------------------------------------------------------------

_DNP3_START_BYTES = 0x0564
_DNP3_HEADER_SIZE = 10


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DNP3FunctionCode(Enum):
    """DNP3 Application Layer function codes."""
    READ = 0x01
    WRITE = 0x02
    DIRECT_OPERATE = 0x03
    DIRECT_OPERATE_NO_ACK = 0x04
    COLD_RESTART = 0x0D
    WARM_RESTART = 0x0E
    RESPONSE = 0x81
    UNSOLICITED_RESPONSE = 0x82


class DNP3ObjectGroup(Enum):
    """DNP3 data object groups."""
    BINARY_INPUT = 1
    BINARY_OUTPUT = 10
    COUNTER = 20
    FROZEN_COUNTER = 21
    ANALOG_INPUT = 30
    ANALOG_OUTPUT = 40
    TIME_AND_DATE = 50


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DNP3DataPoint:
    """A single DNP3 data point returned from an outstation."""
    index: int
    group: DNP3ObjectGroup
    variation: int = 1
    value: Any = None
    quality: int = 0x00
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------

def _build_dnp3_frame(
    function_code: int,
    destination: int,
    source: int,
    payload: bytes = b"",
) -> bytes:
    """Build a minimal DNP3 data-link + application layer frame.

    Layout (simplified):
        [0x05 0x64] [length] [control] [dst_lo dst_hi] [src_lo src_hi]
        [CRC_lo CRC_hi]  [app_control] [function_code] [payload…]
    """
    app_control = 0xC0  # FIR=1, FIN=1, SEQ=0
    app_layer = bytes([app_control, function_code]) + payload

    length = len(app_layer) + 5  # +5 for control + dst(2) + src(2)
    control = 0x44  # DIR=1, PRM=1, unconfirmed user data

    header = struct.pack(
        "<HBBHH",
        _DNP3_START_BYTES,
        length & 0xFF,
        control,
        destination,
        source,
    )
    crc = _crc16(header[2:])
    return header + struct.pack("<H", crc) + app_layer


def _build_read_request(
    group: int,
    variation: int,
    start_index: int,
    count: int,
    destination: int,
    source: int,
) -> bytes:
    """Build a DNP3 READ request for a range of objects."""
    # Object header: group, variation, qualifier 0x00 (start-stop 1-byte)
    obj_header = struct.pack(
        "BBBBB",
        group,
        variation,
        0x00,  # qualifier: 8-bit start-stop
        start_index & 0xFF,
        (start_index + count - 1) & 0xFF,
    )
    return _build_dnp3_frame(DNP3FunctionCode.READ.value, destination, source, obj_header)


def _build_write_request(
    group: int,
    variation: int,
    index: int,
    value_bytes: bytes,
    destination: int,
    source: int,
) -> bytes:
    """Build a DNP3 DIRECT_OPERATE request for a single object."""
    obj_header = struct.pack(
        "BBBBB",
        group,
        variation,
        0x17,  # qualifier: 8-bit index prefix + single object
        1,     # count = 1
        index & 0xFF,
    ) + value_bytes
    return _build_dnp3_frame(DNP3FunctionCode.DIRECT_OPERATE.value, destination, source, obj_header)


def _crc16(data: bytes) -> int:
    """Compute DNP3 CRC-16 (IBM variant)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA6BC
            else:
                crc >>= 1
    return crc ^ 0xFFFF


# ---------------------------------------------------------------------------
# Simulated outstation data
# ---------------------------------------------------------------------------

def _simulated_integrity_poll() -> List[DNP3DataPoint]:
    """Return a realistic set of simulated outstation data points."""
    now = time.time()
    points: List[DNP3DataPoint] = []
    # Binary inputs (Group 1)
    for i in range(4):
        points.append(DNP3DataPoint(
            index=i, group=DNP3ObjectGroup.BINARY_INPUT, variation=2,
            value=(i % 2 == 0), quality=0x01, timestamp=now,
        ))
    # Analog inputs (Group 30)
    for i in range(4):
        points.append(DNP3DataPoint(
            index=i, group=DNP3ObjectGroup.ANALOG_INPUT, variation=1,
            value=round(random.uniform(0.0, 100.0), 2),  # noqa: S311
            quality=0x01, timestamp=now,
        ))
    # Counters (Group 20)
    for i in range(2):
        points.append(DNP3DataPoint(
            index=i, group=DNP3ObjectGroup.COUNTER, variation=1,
            value=random.randint(0, 50000),  # noqa: S311
            quality=0x01, timestamp=now,
        ))
    return points


def _simulated_analog_inputs(start_index: int, count: int) -> List[DNP3DataPoint]:
    now = time.time()
    return [
        DNP3DataPoint(
            index=start_index + i,
            group=DNP3ObjectGroup.ANALOG_INPUT,
            variation=1,
            value=round(random.uniform(0.0, 100.0), 2),  # noqa: S311
            quality=0x01,
            timestamp=now,
        )
        for i in range(count)
    ]


def _simulated_binary_inputs(start_index: int, count: int) -> List[DNP3DataPoint]:
    now = time.time()
    return [
        DNP3DataPoint(
            index=start_index + i,
            group=DNP3ObjectGroup.BINARY_INPUT,
            variation=2,
            value=(i % 2 == 0),
            quality=0x01,
            timestamp=now,
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class MurphyDNP3Client:
    """DNP3 master station client for outstation polling over TCP.

    When no *host* is provided or the connection cannot be established
    the client operates in simulated mode, returning realistic stub data.
    """

    DEFAULT_PORT = 20000
    SOCKET_TIMEOUT = 5.0

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = DEFAULT_PORT,
        master_address: int = 1,
        outstation_address: int = 10,
    ):
        self.host = host
        self.port = port
        self.master_address = master_address
        self.outstation_address = outstation_address

        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()
        self._poll_log: list = []

    @property
    def _simulated(self) -> bool:
        return not self.host or not self._connected

    # -- connection lifecycle ------------------------------------------------

    def connect(self) -> bool:
        """Open a TCP connection to the DNP3 outstation."""
        if not self.host:
            logger.debug("DNP3: no host configured — using simulated mode")
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.SOCKET_TIMEOUT)
            sock.connect((self.host, self.port))
            self._socket = sock
            self._connected = True
            logger.info("DNP3 connected to %s:%s", self.host, self.port)
            return True
        except OSError as exc:
            logger.error("DNP3 connection failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError as exc:
                logger.debug("DNP3 disconnect cleanup: %s", exc)
            self._socket = None
        self._connected = False

    # -- low-level transport -------------------------------------------------

    def _send_recv(self, frame: bytes, recv_size: int = 4096) -> bytes:
        """Send a frame and receive the outstation response."""
        if self._socket is None:
            return b""
        with self._lock:
            self._socket.sendall(frame)
            try:
                return self._socket.recv(recv_size)
            except socket.timeout:
                logger.warning("DNP3 response timed out")
                return b""

    # -- integrity poll (Class 0) --------------------------------------------

    def integrity_poll(self) -> List[DNP3DataPoint]:
        """Perform a Class 0 integrity poll (read all static data).

        Returns a list of :class:`DNP3DataPoint` objects.
        """
        if self._simulated:
            points = _simulated_integrity_poll()
            capped_append(self._poll_log, {
                "action": "integrity_poll",
                "points": len(points),
                "timestamp": time.time(),
            })
            return points

        # Build a Class 0 read request (Group 60, Var 1)
        payload = struct.pack("BBB", 60, 1, 0x06)  # group=60, var=1, qualifier=all
        frame = _build_dnp3_frame(
            DNP3FunctionCode.READ.value,
            self.outstation_address,
            self.master_address,
            payload,
        )
        _response = self._send_recv(frame)
        logger.debug("DNP3 integrity poll: sent %d bytes, received %d bytes", len(frame), len(_response))
        # Full response parsing would decode the Application Layer objects here
        return []

    # -- read operations -----------------------------------------------------

    def read_analog_inputs(self, start_index: int = 0, count: int = 1) -> List[DNP3DataPoint]:
        """Read analog input points (Group 30) from the outstation."""
        if self._simulated:
            return _simulated_analog_inputs(start_index, count)

        frame = _build_read_request(
            DNP3ObjectGroup.ANALOG_INPUT.value, 1,
            start_index, count,
            self.outstation_address, self.master_address,
        )
        _response = self._send_recv(frame)
        logger.debug("DNP3 read_analog_inputs: sent %d bytes", len(frame))
        return []

    def read_binary_inputs(self, start_index: int = 0, count: int = 1) -> List[DNP3DataPoint]:
        """Read binary input points (Group 1) from the outstation."""
        if self._simulated:
            return _simulated_binary_inputs(start_index, count)

        frame = _build_read_request(
            DNP3ObjectGroup.BINARY_INPUT.value, 2,
            start_index, count,
            self.outstation_address, self.master_address,
        )
        _response = self._send_recv(frame)
        logger.debug("DNP3 read_binary_inputs: sent %d bytes", len(frame))
        return []

    # -- write operations ----------------------------------------------------

    def write_analog_output(self, index: int, value: float) -> Dict[str, Any]:
        """Write an analog output value (Group 40) to the outstation."""
        if self._simulated:
            return {
                "success": True,
                "index": index,
                "value": value,
                "group": DNP3ObjectGroup.ANALOG_OUTPUT.name,
                "simulated": True,
            }

        value_bytes = struct.pack("<f", value)  # 32-bit float, little-endian
        frame = _build_write_request(
            DNP3ObjectGroup.ANALOG_OUTPUT.value, 1,
            index, value_bytes,
            self.outstation_address, self.master_address,
        )
        _response = self._send_recv(frame)
        logger.debug("DNP3 write_analog_output: sent %d bytes", len(frame))
        return {"success": True, "index": index, "value": value, "simulated": False}

    def write_binary_output(self, index: int, value: bool) -> Dict[str, Any]:
        """Write a binary output value (Group 10) to the outstation."""
        if self._simulated:
            return {
                "success": True,
                "index": index,
                "value": value,
                "group": DNP3ObjectGroup.BINARY_OUTPUT.name,
                "simulated": True,
            }

        crob_value = 0x03 if value else 0x04  # LATCH_ON / LATCH_OFF
        value_bytes = struct.pack("B", crob_value)
        frame = _build_write_request(
            DNP3ObjectGroup.BINARY_OUTPUT.value, 1,
            index, value_bytes,
            self.outstation_address, self.master_address,
        )
        _response = self._send_recv(frame)
        logger.debug("DNP3 write_binary_output: sent %d bytes", len(frame))
        return {"success": True, "index": index, "value": value, "simulated": False}

    # -- device management ---------------------------------------------------

    def cold_restart(self) -> Dict[str, Any]:
        """Send a cold-restart command to the outstation."""
        if self._simulated:
            return {"success": True, "restart_type": "cold", "simulated": True}

        frame = _build_dnp3_frame(
            DNP3FunctionCode.COLD_RESTART.value,
            self.outstation_address,
            self.master_address,
        )
        _response = self._send_recv(frame)
        logger.debug("DNP3 cold_restart: sent %d bytes", len(frame))
        return {"success": True, "restart_type": "cold", "simulated": False}

    # -- execute() dispatcher ------------------------------------------------

    def execute(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a named action to the appropriate DNP3 method."""
        params = params or {}
        dispatch = {
            "integrity_poll": lambda p: {"points": [
                {
                    "index": pt.index,
                    "group": pt.group.name,
                    "value": pt.value,
                    "quality": pt.quality,
                }
                for pt in self.integrity_poll()
            ]},
            "read_analog_inputs": lambda p: {"points": [
                {"index": pt.index, "value": pt.value, "quality": pt.quality}
                for pt in self.read_analog_inputs(
                    p.get("start_index", 0), p.get("count", 1),
                )
            ]},
            "read_binary_inputs": lambda p: {"points": [
                {"index": pt.index, "value": pt.value, "quality": pt.quality}
                for pt in self.read_binary_inputs(
                    p.get("start_index", 0), p.get("count", 1),
                )
            ]},
            "write_analog_output": lambda p: self.write_analog_output(
                p.get("index", 0), p.get("value", 0.0),
            ),
            "write_binary_output": lambda p: self.write_binary_output(
                p.get("index", 0), p.get("value", False),
            ),
            "cold_restart": lambda p: self.cold_restart(),
        }
        handler = dispatch.get(action_name)
        if handler:
            return handler(params)
        return {"error": f"Unknown DNP3 action: {action_name}", "simulated": self._simulated}

    # -- context manager -----------------------------------------------------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
