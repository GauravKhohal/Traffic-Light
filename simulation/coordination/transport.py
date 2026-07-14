"""Signal-to-signal message transport (Phase 4).

Each intersection publishes a state message every 5s and reads its upstream
neighbours' latest messages to predict incoming traffic. The controller only
depends on the small `Bus` interface below (`publish` / `latest`), so the
same coordination logic runs over either transport:

- `InProcessBus`: an in-memory dict, used for the deterministic SUMO metric
  runs (no broker, fully reproducible, and all 9 signals live in one process
  anyway).
- `MqttBus`: real Eclipse-Mosquitto / MQTT via paho, QoS 1, retained — what
  an actual edge deployment uses, where each intersection is a separate node.
  Both satisfy the same contract; `scripts/mqtt_smoke.py` proves the MQTT
  path round-trips against a live broker.

Message schema (one per signal, per publish):
    {"id": "B1", "t": 630.0, "queues": [3, 12, 4, 5],
     "phase": 1, "outflow": {"A1": 6.0, "C1": 14.0, "B0": 2.0, "B2": 3.0}}
`queues` is per the signal's own route order; `outflow` is veh/min heading
toward each neighbour junction (measured on the outgoing edge to that
neighbour).
"""
import json

STATE_TOPIC = "signals/{sid}/state"


def build_state_message(signal_id, t, queues, phase, outflow):
    """Assemble the canonical state dict both transports carry."""
    return {
        "id": signal_id,
        "t": round(float(t), 1),
        "queues": [round(float(q), 2) for q in queues],
        "phase": int(phase),
        "outflow": {k: round(float(v), 2) for k, v in outflow.items()},
    }


class InProcessBus:
    """Deterministic in-memory pub/sub. `latest(sid)` returns the most
    recently published message for signal `sid`, or None."""

    def __init__(self):
        self._latest = {}

    def publish(self, signal_id, payload):
        self._latest[signal_id] = dict(payload)

    def latest(self, signal_id):
        return self._latest.get(signal_id)

    def close(self):
        pass


class MqttBus:
    """paho-mqtt transport for real edge deployment.

    Publishes to `signals/{id}/state` at QoS 1, retained so a subscriber
    connecting late immediately receives each signal's last state. Caches
    the latest decoded message per signal id from its subscription callback.
    """

    def __init__(
        self,
        host="localhost",
        port=1883,
        client_id=None,
        subscribe="signals/+/state",
        keepalive=30,
    ):
        import paho.mqtt.client as mqtt

        self._latest = {}
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        self._client.on_message = self._on_message
        self._client.connect(host, port, keepalive)
        if subscribe:
            self._client.subscribe(subscribe, qos=1)
        self._client.loop_start()

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            self._latest[payload["id"]] = payload
        except (ValueError, KeyError):
            pass  # ignore malformed messages; a signal keeps its last-known state

    def publish(self, signal_id, payload):
        self._client.publish(
            STATE_TOPIC.format(sid=signal_id),
            json.dumps(payload),
            qos=1,
            retain=True,
        )

    def latest(self, signal_id):
        return self._latest.get(signal_id)

    def close(self):
        self._client.loop_stop()
        self._client.disconnect()
