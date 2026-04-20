# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
PiCar-X Hardware Abstraction Layer for Raspberry Pi 3B+.

Design Label: ROBO-PICARX-HW-001
Owner: Robotics / IoT

Wraps the SunFounder ``picarx`` SDK to expose servo, motor, ultrasonic,
camera, grayscale-line-follower and battery-voltage readings through
the Murphy robotics ProtocolClient interface.

External dependency:
  * ``picarx`` (GPLv3 — SunFounder HAT driver) — optional at import time.
  * ``robot-hat`` (GPLv3 — ADC / GPIO layer) — optional.

When the SDK is not installed the module operates in **stub mode** so that
all unit tests and CI can run without real hardware.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional SunFounder SDK imports
# ---------------------------------------------------------------------------

try:
    from picarx import Picarx as _SunFounderPicarx  # type: ignore[import-untyped]
    _PICARX_SDK_AVAILABLE = True
except ImportError:
    _SunFounderPicarx = None  # type: ignore[assignment,misc]
    _PICARX_SDK_AVAILABLE = False

try:
    from robot_hat import ADC as _ADC  # type: ignore[import-untyped]
    _ADC_AVAILABLE = True
except ImportError:
    _ADC = None  # type: ignore[assignment,misc]
    _ADC_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants — RPi 3B+ / PiCar-X specifics
# ---------------------------------------------------------------------------

class PiCarXPin(str, Enum):
    """GPIO / hat pin aliases for the PiCar-X on Pi 3B+."""
    SERVO_STEERING = "P0"   # steering servo
    SERVO_CAM_PAN = "P1"    # camera pan servo
    SERVO_CAM_TILT = "P2"   # camera tilt servo
    MOTOR_LEFT = "D0"       # left motor direction
    MOTOR_RIGHT = "D1"      # right motor direction
    ULTRASONIC_TRIG = "D2"  # HC-SR04 trigger
    ULTRASONIC_ECHO = "D3"  # HC-SR04 echo
    GRAYSCALE_LEFT = "A0"   # left line sensor
    GRAYSCALE_MID = "A1"    # middle line sensor
    GRAYSCALE_RIGHT = "A2"  # right line sensor
    BATTERY_ADC = "A4"      # battery voltage divider


# Voltage thresholds (2S LiPo via divider)
BATTERY_FULL_VOLTAGE = 8.4
BATTERY_LOW_VOLTAGE = 6.8
BATTERY_CRITICAL_VOLTAGE = 6.2
CHARGE_REQUEST_THRESHOLD = 7.0  # request charge below this


@dataclass
class MotorState:
    """Current motor state."""
    speed_left: int = 0       # -100..100
    speed_right: int = 0      # -100..100
    steering_angle: float = 0.0  # degrees, -40..40


@dataclass
class CameraState:
    """Camera gimbal angles."""
    pan: float = 0.0     # degrees
    tilt: float = 0.0    # degrees


@dataclass
class SensorSnapshot:
    """Point-in-time reading from all on-board sensors."""
    ultrasonic_cm: float = -1.0
    grayscale: List[int] = field(default_factory=lambda: [0, 0, 0])
    battery_voltage: float = 0.0
    battery_percent: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Hardware driver
# ---------------------------------------------------------------------------

class PiCarXHardware:
    """Low-level hardware interface for the SunFounder PiCar-X.

    In stub mode every method succeeds and returns plausible simulated
    values so that higher-level code can be tested without a Pi.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._px: Any = None
        self._adc: Any = None
        self._motor = MotorState()
        self._camera = CameraState()
        self._connected = False
        self._stub = not _PICARX_SDK_AVAILABLE

    # -- lifecycle -----------------------------------------------------------

    def connect(self) -> bool:
        """Initialise hardware (or enter stub mode)."""
        with self._lock:
            if self._connected:
                return True
            if self._stub:
                logger.info("PiCar-X hardware: stub mode (no SDK)")
                self._connected = True
                return True
            try:
                self._px = _SunFounderPicarx()
                if _ADC_AVAILABLE:
                    self._adc = _ADC(PiCarXPin.BATTERY_ADC.value)
                self._connected = True
                logger.info("PiCar-X hardware: connected via SDK")
                return True
            except Exception as exc:  # PICARX-HW-ERR-001
                logger.error("PiCar-X connect failed [PICARX-HW-ERR-001]: %s", exc)
                self._stub = True
                self._connected = True
                return True  # degrade to stub

    def disconnect(self) -> bool:
        """Shut down motors and release hardware."""
        with self._lock:
            self._stop_motors_unlocked()
            self._connected = False
            self._px = None
            self._adc = None
            return True

    @property
    def is_stub(self) -> bool:
        return self._stub

    @property
    def is_connected(self) -> bool:
        return self._connected

    # -- motor control -------------------------------------------------------

    def set_speed(self, left: int, right: int) -> None:
        """Set motor speeds (-100..100)."""
        left = max(-100, min(100, left))
        right = max(-100, min(100, right))
        with self._lock:
            self._motor.speed_left = left
            self._motor.speed_right = right
            if not self._stub and self._px:
                try:
                    self._px.forward(max(abs(left), abs(right)))
                except Exception as exc:  # PICARX-HW-ERR-002
                    logger.warning("set_speed SDK error [PICARX-HW-ERR-002]: %s", exc)

    def set_steering(self, angle: float) -> None:
        """Set steering angle in degrees (-40..40)."""
        angle = max(-40.0, min(40.0, angle))
        with self._lock:
            self._motor.steering_angle = angle
            if not self._stub and self._px:
                try:
                    self._px.set_dir_servo_angle(angle)
                except Exception as exc:  # PICARX-HW-ERR-003
                    logger.warning("set_steering SDK error [PICARX-HW-ERR-003]: %s", exc)

    def stop(self) -> None:
        """Emergency / full stop."""
        with self._lock:
            self._stop_motors_unlocked()

    def _stop_motors_unlocked(self) -> None:
        self._motor.speed_left = 0
        self._motor.speed_right = 0
        self._motor.steering_angle = 0.0
        if not self._stub and self._px:
            try:
                self._px.stop()
                self._px.set_dir_servo_angle(0)
            except Exception:
                pass

    # -- camera gimbal -------------------------------------------------------

    def set_camera_pan(self, angle: float) -> None:
        angle = max(-90.0, min(90.0, angle))
        with self._lock:
            self._camera.pan = angle
            if not self._stub and self._px:
                try:
                    self._px.set_cam_pan_angle(angle)
                except Exception as exc:  # PICARX-HW-ERR-004
                    logger.warning("cam_pan SDK error [PICARX-HW-ERR-004]: %s", exc)

    def set_camera_tilt(self, angle: float) -> None:
        angle = max(-35.0, min(65.0, angle))
        with self._lock:
            self._camera.tilt = angle
            if not self._stub and self._px:
                try:
                    self._px.set_cam_tilt_angle(angle)
                except Exception as exc:  # PICARX-HW-ERR-005
                    logger.warning("cam_tilt SDK error [PICARX-HW-ERR-005]: %s", exc)

    # -- sensors -------------------------------------------------------------

    def read_ultrasonic(self) -> float:
        """Read HC-SR04 distance in cm.  Returns -1.0 on failure."""
        with self._lock:
            if self._stub:
                return round(random.uniform(5.0, 200.0), 1)
            if self._px:
                try:
                    val = self._px.ultrasonic.read()
                    return float(val) if val and val > 0 else -1.0
                except Exception as exc:  # PICARX-HW-ERR-006
                    logger.warning("ultrasonic read error [PICARX-HW-ERR-006]: %s", exc)
            return -1.0

    def read_grayscale(self) -> List[int]:
        """Read 3-channel grayscale line sensor (0..4095 each)."""
        with self._lock:
            if self._stub:
                return [random.randint(0, 4095) for _ in range(3)]
            if self._px:
                try:
                    return list(self._px.get_grayscale_data())
                except Exception as exc:  # PICARX-HW-ERR-007
                    logger.warning("grayscale read error [PICARX-HW-ERR-007]: %s", exc)
            return [0, 0, 0]

    def read_battery_voltage(self) -> float:
        """Read battery voltage via ADC pin.  Returns 0.0 on failure."""
        with self._lock:
            if self._stub:
                return round(random.uniform(6.5, 8.4), 2)
            if self._adc:
                try:
                    raw = self._adc.read()
                    # Voltage divider: Vbat = raw * (3.3 / 4095) * 3
                    return round(raw * 3.3 / 4095.0 * 3.0, 2)
                except Exception as exc:  # PICARX-HW-ERR-008
                    logger.warning("battery ADC error [PICARX-HW-ERR-008]: %s", exc)
            return 0.0

    def read_all(self) -> SensorSnapshot:
        """Read every on-board sensor and return a snapshot."""
        voltage = self.read_battery_voltage()
        pct = 0.0
        if voltage > 0:
            pct = max(0.0, min(100.0,
                (voltage - BATTERY_CRITICAL_VOLTAGE)
                / (BATTERY_FULL_VOLTAGE - BATTERY_CRITICAL_VOLTAGE) * 100.0
            ))
        return SensorSnapshot(
            ultrasonic_cm=self.read_ultrasonic(),
            grayscale=self.read_grayscale(),
            battery_voltage=voltage,
            battery_percent=round(pct, 1),
        )

    def get_motor_state(self) -> MotorState:
        with self._lock:
            return MotorState(
                speed_left=self._motor.speed_left,
                speed_right=self._motor.speed_right,
                steering_angle=self._motor.steering_angle,
            )

    def get_camera_state(self) -> CameraState:
        with self._lock:
            return CameraState(
                pan=self._camera.pan,
                tilt=self._camera.tilt,
            )
