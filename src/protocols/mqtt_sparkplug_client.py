"""
MQTT Sparkplug B Client for Murphy System

Real MQTT + Sparkplug B implementation using paho-mqtt.
Guards the import so the module can be used without paho-mqtt installed.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt  # type: ignore[import]
    _PAHO_AVAILABLE = True
except ImportError:
    _PAHO_AVAILABLE = False
    logger.debug("paho-mqtt not installed — MQTT client will use stub mode")


class MurphyMQTTSparkplugClient:
    """MQTT + Sparkplug B client using paho-mqtt.

    Implements Sparkplug B NBIRTH, DBIRTH, DDATA, NCMD payloads.
    Falls back to stub responses when paho-mqtt is not installed.
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        group_id: str = "Murphy",
        edge_node_id: str = "Node1",
        client_id: Optional[str] = None,
    ):
        self.broker = broker
        self.port = port
        self.group_id = group_id
        self.edge_node_id = edge_node_id
        self.client_id = client_id or f"murphy_{edge_node_id}_{int(time.time())}"
        self._client = None
        self._connected = False
        self._messages: list = []

    def connect(self) -> bool:
        if not _PAHO_AVAILABLE:
            return False
        try:
            self._client = mqtt.Client(client_id=self.client_id)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            timeout = time.time() + 5
            while not self._connected and time.time() < timeout:
                time.sleep(0.1)
            return self._connected
        except Exception as exc:
            logger.error("MQTT connection failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception as exc:
                logger.debug("MQTT disconnect cleanup: %s", exc)
            self._client = None
            self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = (rc == 0)
        if self._connected:
            logger.info("MQTT connected to %s:%s", self.broker, self.port)
        else:
            logger.warning("MQTT connection refused, code %s", rc)

    def _on_message(self, client, userdata, msg):
        capped_append(self._messages, {"topic": msg.topic, "payload": msg.payload, "timestamp": time.time()})

    def _sparkplug_topic(self, msg_type: str, device_id: Optional[str] = None) -> str:
        if device_id:
            return f"spBv1.0/{self.group_id}/{msg_type}/{self.edge_node_id}/{device_id}"
        return f"spBv1.0/{self.group_id}/{msg_type}/{self.edge_node_id}"

    def publish_nbirth(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Publish Sparkplug B NBIRTH payload."""
        topic = self._sparkplug_topic("NBIRTH")
        payload = json.dumps({"timestamp": int(time.time() * 1000), "metrics": metrics, "seq": 0})
        return self._publish(topic, payload)

    def publish_ddata(self, device_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Publish Sparkplug B DDATA payload."""
        topic = self._sparkplug_topic("DDATA", device_id)
        payload = json.dumps({"timestamp": int(time.time() * 1000), "metrics": metrics})
        return self._publish(topic, payload)

    def publish_ncmd(self, command: str, value: Any) -> Dict[str, Any]:
        """Publish Sparkplug B NCMD payload."""
        topic = self._sparkplug_topic("NCMD")
        payload = json.dumps({"timestamp": int(time.time() * 1000), "metrics": {command: value}})
        return self._publish(topic, payload)

    def subscribe(self, topic: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Subscribe to a MQTT topic."""
        if not _PAHO_AVAILABLE or self._client is None:
            return {"success": False, "simulated": True, "reason": "mqtt_unavailable"}
        try:
            self._client.subscribe(topic)
            if callback:
                self._client.message_callback_add(topic, lambda c, u, m: callback(m.topic, m.payload))
            return {"success": True, "topic": topic, "simulated": False}
        except Exception as exc:
            logger.warning("MQTT subscribe failed: %s", exc)
            return {"success": False, "topic": topic, "error": str(exc), "simulated": False}

    def _publish(self, topic: str, payload: str) -> Dict[str, Any]:
        if not _PAHO_AVAILABLE or self._client is None:
            return {"success": False, "simulated": True, "reason": "mqtt_unavailable"}
        try:
            result = self._client.publish(topic, payload, qos=1)
            return {"success": result.rc == 0, "topic": topic, "simulated": False}
        except Exception as exc:
            logger.warning("MQTT publish failed: %s", exc)
            return {"success": False, "topic": topic, "error": str(exc), "simulated": False}

    def execute(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        dispatch = {
            "publish_nbirth": lambda p: self.publish_nbirth(p.get("metrics", {})),
            "publish_ddata": lambda p: self.publish_ddata(p.get("device_id", "device1"), p.get("metrics", {})),
            "publish_ncmd": lambda p: self.publish_ncmd(p.get("command", ""), p.get("value")),
            "subscribe": lambda p: self.subscribe(p.get("topic", "#")),
        }
        handler = dispatch.get(action_name)
        if handler:
            return handler(params)
        return {"error": f"Unknown MQTT action: {action_name}", "simulated": not _PAHO_AVAILABLE}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
