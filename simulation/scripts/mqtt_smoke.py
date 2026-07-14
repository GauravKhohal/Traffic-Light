"""Prove the MqttBus transport round-trips against a live MQTT broker with
QoS 1 retained messages — the real edge-deployment path for signal-to-signal
coordination (in-simulation runs use the in-process bus instead).

Prerequisites: a broker on localhost:1883, e.g. via Docker:
    docker run -d --rm --name tl-mosquitto -p 1883:1883 eclipse-mosquitto:2 \
      sh -c "printf 'listener 1883\\nallow_anonymous true\\n' > /m.conf && \
             exec mosquitto -c /m.conf"

Run:
    python simulation/scripts/mqtt_smoke.py [--host H] [--port P]
Exit code 0 on success, non-zero (with a clear message) if no broker.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from simulation.coordination.transport import MqttBus, build_state_message


def main(host, port):
    try:
        pub = MqttBus(host=host, port=port, client_id="tl-smoke-pub")
        sub = MqttBus(host=host, port=port, client_id="tl-smoke-sub")
    except Exception as e:
        sys.exit(f"Could not connect to MQTT broker at {host}:{port} - {e}")

    try:
        msg = build_state_message(
            "B1", 630.0, [3, 12, 4, 5], 1, {"A1": 6.0, "C1": 14.0}
        )
        pub.publish("B1", msg)

        deadline = time.time() + 5.0
        got = None
        while time.time() < deadline:
            got = sub.latest("B1")
            if got is not None:
                break
            time.sleep(0.05)

        if got is None:
            sys.exit("FAIL: no message received within 5s")
        assert got["id"] == "B1", got
        assert got["outflow"]["C1"] == 14.0, got
        print(f"OK: round-tripped B1 state over MQTT QoS 1 -> {got}")

        # retained-message check: a fresh subscriber gets last state immediately
        late = MqttBus(host=host, port=port, client_id="tl-smoke-late")
        try:
            deadline = time.time() + 5.0
            while time.time() < deadline and late.latest("B1") is None:
                time.sleep(0.05)
            if late.latest("B1") is None:
                sys.exit("FAIL: retained message not delivered to late subscriber")
            print("OK: late subscriber received retained B1 state")
        finally:
            late.close()
    finally:
        pub.close()
        sub.close()
    print("MQTT smoke test passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()
    main(args.host, args.port)
