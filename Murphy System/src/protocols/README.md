# Protocols

The `protocols` package provides industrial-protocol clients for connecting
Murphy to building automation systems and IoT devices.

## Key Modules

| Module | Purpose |
|--------|---------|
| `bacnet_client.py` | BACnet/IP client for building automation |
| `knx_client.py` | KNX bus client |
| `modbus_client.py` | Modbus TCP/RTU client |
| `mqtt_sparkplug_client.py` | MQTT Sparkplug B client for industrial IoT |
| `opcua_client.py` | OPC-UA client for industrial control systems |

## Usage

```python
from protocols.modbus_client import ModbusClient
client = ModbusClient(host="192.168.1.100", port=502)
value = await client.read_holding_registers(address=0, count=10)
```
