"""Live data sources for the dashboard (Phase 6).

Two interchangeable feeds write into the same StateStore:

- `DemoFeed`: a self-contained synthetic generator for all 9 intersections
  (phases cycle with countdowns, queues ebb and flow, manual overrides take
  effect). Lets the dashboard run with no SUMO and no broker — the default.
- `MqttFeed`: subscribes to the Phase 4 coordination stream
  (`signals/+/state`) on an MQTT broker, so the dashboard shows the actual
  simulation. Run `scripts/run_coordinated.py --transport mqtt` as the source.

Selected by the DASHBOARD_FEED env var ("demo" or "mqtt").
"""
import asyncio
import json
import random

from state_store import APPROACH_LABELS, StateStore

SIGNAL_IDS = [c + str(r) for c in "ABC" for r in range(3)]
YELLOW_S = 4
ALLRED_S = 2


class DemoFeed:
    """Synthetic but plausible signal dynamics, advanced once per second."""

    def __init__(self, store: StateStore, seed=0):
        self.store = store
        self.rng = random.Random(seed)
        self._avg_wait = 0.0
        self.sig = {}
        for sid in SIGNAL_IDS:
            self.sig[sid] = {
                "route": 0,
                "kind": "green",
                "countdown": self.rng.randint(15, 40),
                "queues": [self.rng.randint(0, 6) for _ in range(4)],
            }

    def _tick_signal(self, sid):
        s = self.sig[sid]
        override = self.store.get_override(sid)
        override_idx = APPROACH_LABELS.index(override) if override in APPROACH_LABELS else None

        # arrivals on every approach; the served approach also discharges
        for i in range(4):
            s["queues"][i] += self.rng.random() < 0.35
        if s["kind"] == "green":
            served = s["route"]
            s["queues"][served] = max(0, s["queues"][served] - self.rng.choice([1, 1, 2]))
            # a manual override to a different approach forces an early switch
            if override_idx is not None and override_idx != served:
                s["countdown"] = 0

        s["countdown"] -= 1
        if s["countdown"] <= 0:
            if s["kind"] == "green":
                s["kind"], s["countdown"] = "yellow", YELLOW_S
            elif s["kind"] == "yellow":
                s["kind"], s["countdown"] = "allred", ALLRED_S
            else:  # allred -> next green
                if override_idx is not None:
                    s["route"] = override_idx
                else:
                    s["route"] = (s["route"] + 1) % 4
                s["kind"], s["countdown"] = "green", self.rng.randint(15, 40)

        phase = APPROACH_LABELS[s["route"]] if s["kind"] == "green" else s["kind"]
        self.store.update_signal(
            {
                "id": sid,
                "queues": {APPROACH_LABELS[i]: s["queues"][i] for i in range(4)},
                "phase": phase,
                "phase_index": s["route"] if s["kind"] == "green" else -1,
                "countdown": max(0, s["countdown"]),
            }
        )

    def _tick(self):
        for sid in SIGNAL_IDS:
            self._tick_signal(sid)
        total_queue = sum(sum(s["queues"]) for s in self.sig.values())
        # smooth synthetic network wait proxy tracking total congestion
        self._avg_wait = 0.85 * self._avg_wait + 0.15 * (total_queue * 2.5)
        self.store.record_metrics(avg_wait=self._avg_wait, total_queue=total_queue)

    async def run(self):
        while True:
            self._tick()
            await asyncio.sleep(1.0)


class MqttFeed:
    """Subscribes to the Phase 4 coordination messages and maps them into the
    store. Coordination messages carry per-route queues and the current phase
    index (no countdown), so cards show queues + current green in this mode."""

    def __init__(self, store: StateStore, host="localhost", port=1883):
        import paho.mqtt.client as mqtt

        self.store = store
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="tl-dashboard"
        )
        self._client.on_message = self._on_message
        self._client.connect(host, port)
        self._client.subscribe("signals/+/state", qos=1)
        self._client.loop_start()

    def _on_message(self, client, userdata, msg):
        try:
            p = json.loads(msg.payload.decode())
            queues = p.get("queues", [])
            idx = int(p.get("phase", -1))
            self.store.update_signal(
                {
                    "id": p["id"],
                    "queues": {
                        APPROACH_LABELS[i]: queues[i] for i in range(min(4, len(queues)))
                    },
                    "phase": APPROACH_LABELS[idx] if 0 <= idx < 4 else "—",
                    "phase_index": idx,
                    "countdown": None,
                }
            )
            total = sum(sum(s["queues"].values()) for s in self.store.signals())
            self.store.record_metrics(avg_wait=total * 2.5, total_queue=total)
        except (ValueError, KeyError):
            pass

    async def run(self):
        # paho runs its own network thread; nothing to drive here
        while True:
            await asyncio.sleep(3600)

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()
