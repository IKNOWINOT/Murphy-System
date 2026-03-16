# `src/protocols` — Industrial Protocol Clients

Real protocol client implementations for BACnet, Modbus, OPC-UA, KNX, and MQTT/Sparkplug B industrial and IoT connectivity.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The protocols package provides Murphy's physical-world connectivity to industrial control systems and IoT devices. Each client implements a common interface and gracefully falls back to a stub when the corresponding optional library is not installed, so the rest of the system can import the package unconditionally. The `validate_protocol_dependencies` function checks that all protocols listed in `MURPHY_ENABLED_PROTOCOLS` have their libraries present at startup, failing fast if a required protocol library is missing.

## Key Components

| Module | Purpose |
|--------|---------|
| `bacnet_client.py` | `MurphyBACnetClient` — BACnet/IP read/write for building automation |
| `modbus_client.py` | `MurphyModbusClient` — Modbus TCP/RTU for industrial PLCs |
| `opcua_client.py` | `MurphyOPCUAClient` — OPC-UA for manufacturing and SCADA |
| `knx_client.py` | `MurphyKNXClient` — KNX for smart building automation |
| `mqtt_sparkplug_client.py` | `MurphyMQTTSparkplugClient` — MQTT with Sparkplug B payload schema |

## Usage

```python
from protocols import MurphyModbusClient

client = MurphyModbusClient(host="192.168.1.10", port=502)
client.connect()
value = client.read_holding_register(address=100)
print(value)
```

## Configuration

| Variable | Description |
|----------|-------------|
| `MURPHY_ENABLED_PROTOCOLS` | Comma-separated list of required protocols (e.g. `bacnet,modbus`). Missing libraries raise `ImportError` at startup. |

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
