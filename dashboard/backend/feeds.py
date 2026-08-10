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
import os
import random

from state_store import APPROACH_LABELS, StateStore, grid_position

SIGNAL_IDS = [c + str(r) for c in "ABC" for r in range(3)]
YELLOW_S = 4
ALLRED_S = 2
GREEN_BASE, GREEN_MIN, GREEN_MAX = 30, 15, 60
QUEUE_CAP = 22  # per-approach ceiling: keeps the demo bounded no matter how long it runs

# Grid-coordinate step (col, row) toward the neighbour that FEEDS each
# approach: e.g. a signal's "N" queue is fed by the neighbour one row north
# (vehicles heading south), and that signal's own N-approach discharge
# continues south, landing in the N queue of the neighbour one row south -
# straight-through corridors, matching a real Manhattan grid. Independent of
# the frontend's on-screen pixel directions (constants.js DIR).
NEIGHBOR_STEP = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def _signal_at(x, y):
    if 0 <= x <= 2 and 0 <= y <= 2:
        return "ABC"[x] + str(y)
    return None


def _upstream_neighbor(sid, approach):
    """The signal whose same-label discharge feeds this approach, or None if
    this approach sits on the grid's fringe (fed by outside/external demand)."""
    x, y = grid_position(sid)
    dx, dy = NEIGHBOR_STEP[approach]
    return _signal_at(x + dx, y + dy)


def _downstream_neighbor(sid, approach):
    """Where this approach's own discharge continues on to, or None if it
    exits the grid."""
    x, y = grid_position(sid)
    dx, dy = NEIGHBOR_STEP[approach]
    return _signal_at(x - dx, y - dy)

# Real seconds per simulated second of the demo feed. >1 = slow motion, so a
# viewer can actually watch a queue build and then drain when the AI opens
# that lane. Override with DASHBOARD_DEMO_PACE (e.g. "1.0" for real-time).
DEMO_PACE_S = float(os.environ.get("DASHBOARD_DEMO_PACE", "1.5"))

# "Gap-out": in AI mode, a green that has fully drained its own queue ends
# early (once at least this many seconds have run, to avoid flicker) instead
# of burning its remaining planned time on an empty lane while another
# approach waits - the immediate hand-off a real actuated signal makes.
MIN_GREEN_BEFORE_GAPOUT_S = 5


def plan_greens(queues):
    """AI green-time allocation per direction (the spec's demand-proportional
    formula): busier approaches get more green, clamped to [15, 60]s. Returns
    integer seconds per approach."""
    n = len(queues)
    total = sum(queues)
    if total <= 0:
        return [GREEN_BASE] * n
    return [round(max(GREEN_MIN, min(GREEN_MAX, GREEN_BASE * n * q / total))) for q in queues]


class DemoFeed:
    """Synthetic but plausible signal dynamics, advanced once per second."""

    def __init__(self, store: StateStore, seed=0):
        self.store = store
        self.rng = random.Random(seed)
        self._avg_wait = 0.0
        # precompute static topology once: which approaches are fed by a
        # neighbour's discharge (interior) vs. from outside the grid (fringe)
        self.upstream = {
            sid: {a: _upstream_neighbor(sid, a) for a in APPROACH_LABELS} for sid in SIGNAL_IDS
        }
        self.downstream = {
            sid: {a: _downstream_neighbor(sid, a) for a in APPROACH_LABELS} for sid in SIGNAL_IDS
        }
        self.sig = {}
        for sid in SIGNAL_IDS:
            self.sig[sid] = {
                "route": 0,
                "kind": "green",
                "countdown": GREEN_BASE,
                "queues": [self.rng.randint(0, 6) for _ in range(4)],
                "greens": [GREEN_BASE] * 4,
                "rates": self._new_rates(sid),
            }

    def _new_rates(self, sid):
        """Per-approach arrival probabilities. Only approaches on the grid's
        fringe (no upstream neighbour, i.e. real traffic entering from
        outside) get random demand, one of them boosted to a clearly busier
        rate so there's an obvious source for congestion to propagate from.
        Interior approaches (fed by a neighbour's own discharge - see
        _tick()'s propagation step) get only a small local trickle; their
        real demand comes from actual upstream traffic, not randomness,
        which is the whole point of connecting the signals together."""
        fringe = [i for i, a in enumerate(APPROACH_LABELS) if self.upstream[sid][a] is None]
        rates = [self.rng.uniform(0.01, 0.03) for _ in range(4)]
        for i in fringe:
            rates[i] = self.rng.uniform(0.03, 0.10)
        if fringe:
            rates[self.rng.choice(fringe)] = self.rng.uniform(0.25, 0.42)
        return rates

    def _tick_signal(self, sid):
        s = self.sig[sid]
        ai = self.store.get_mode() == "ai"
        override = self.store.get_override(sid)
        override_idx = APPROACH_LABELS.index(override) if override in APPROACH_LABELS else None

        # occasionally the demand pattern shifts -> the AI re-allocates green
        if self.rng.random() < 0.004:
            s["rates"] = self._new_rates(sid)

        # local arrivals: fringe approaches get real random demand from
        # outside the grid; interior approaches only a small trickle, since
        # their real traffic arrives via _tick()'s neighbour propagation
        for i in range(4):
            if self.rng.random() < s["rates"][i]:
                s["queues"][i] = min(QUEUE_CAP, s["queues"][i] + 1)

        discharged = {a: 0 for a in APPROACH_LABELS}
        if s["kind"] == "green":
            served = s["route"]
            discharge = min(s["queues"][served], self.rng.choice([1, 1, 2, 2]))
            s["queues"][served] -= discharge
            if discharge:
                self.store.record_served(discharge)
                discharged[APPROACH_LABELS[served]] = discharge
            # a manual override to a different approach forces an early switch
            if override_idx is not None and override_idx != served:
                s["countdown"] = 0
            elif ai and override_idx is None:
                # gap-out: this approach's own queue just drained and another
                # approach has traffic waiting - end the green now instead of
                # burning the rest of its planned time on an empty lane
                elapsed = s["greens"][served] - s["countdown"]
                others_waiting = any(q > 0 for i, q in enumerate(s["queues"]) if i != served)
                if s["queues"][served] == 0 and others_waiting and elapsed >= MIN_GREEN_BEFORE_GAPOUT_S:
                    s["countdown"] = 0

        s["countdown"] -= 1
        if s["countdown"] <= 0:
            if s["kind"] == "green":
                s["kind"], s["countdown"] = "yellow", YELLOW_S
            elif s["kind"] == "yellow":
                s["kind"], s["countdown"] = "allred", ALLRED_S
            else:  # all-red -> next green
                if ai:
                    # AI mode: demand-proportional green (spec formula), and
                    # skip straight past any approach with zero queued
                    # vehicles instead of wasting a turn on it (up to 3
                    # skips, so it always terminates)
                    s["greens"] = plan_greens(s["queues"])
                    if override_idx is not None:
                        nxt = override_idx
                    else:
                        nxt = (s["route"] + 1) % 4
                        for _ in range(3):
                            if s["queues"][nxt] > 0:
                                break
                            nxt = (nxt + 1) % 4
                else:
                    # fixed mode: the "general" behaviour every uncontrolled
                    # intersection runs today - plain round robin, ignores
                    # queue length entirely, always the base 30s
                    s["greens"] = [GREEN_BASE] * 4
                    nxt = override_idx if override_idx is not None else (s["route"] + 1) % 4
                s["route"] = nxt
                s["kind"] = "green"
                s["countdown"] = s["greens"][s["route"]]  # serve exactly the planned time

        phase = APPROACH_LABELS[s["route"]] if s["kind"] == "green" else s["kind"]
        self.store.update_signal(
            {
                "id": sid,
                "queues": {APPROACH_LABELS[i]: s["queues"][i] for i in range(4)},
                "greens": {APPROACH_LABELS[i]: s["greens"][i] for i in range(4)},
                "phase": phase,
                "phase_index": s["route"],  # active/transitioning approach, always valid
                "countdown": max(0, s["countdown"]),
            }
        )
        return discharged

    def _tick(self):
        # 1) each signal advances independently (local arrivals + discharge
        #    if serving), recording what it discharged this tick per approach
        discharged = {sid: self._tick_signal(sid) for sid in SIGNAL_IDS}

        # 2) connect the grid: route each signal's discharge into the
        #    matching queue of its downstream neighbour (straight-through
        #    corridor), arriving next tick - real inter-signal traffic flow,
        #    not independent per-node randomness. A signal on the AI-mode
        #    side of the toggle reacts to this exactly like any other
        #    demand: bigger queue -> more green -> less chance of pile-up.
        for sid, amounts in discharged.items():
            for approach, amount in amounts.items():
                if amount <= 0:
                    continue
                down_sid = self.downstream[sid][approach]
                if down_sid is None:
                    continue  # exits the grid at the fringe
                idx = APPROACH_LABELS.index(approach)
                down = self.sig[down_sid]
                down["queues"][idx] = min(QUEUE_CAP, down["queues"][idx] + amount)

        total_queue = sum(sum(s["queues"]) for s in self.sig.values())
        # smooth synthetic network wait proxy tracking total congestion
        self._avg_wait = 0.85 * self._avg_wait + 0.15 * (total_queue * 2.5)
        self.store.record_metrics(avg_wait=self._avg_wait, total_queue=total_queue)

    async def run(self):
        while True:
            if self.store.get_running():
                self._tick()
                await asyncio.sleep(DEMO_PACE_S)
            else:
                # poll quickly while paused so resume picks up right away
                # instead of waiting out the rest of a normal tick interval
                await asyncio.sleep(0.2)


class MqttFeed:
    """Subscribes to the Phase 4 coordination messages and maps them into the
    store. Coordination messages carry per-route queues and the current phase
    index (no countdown), so cards show queues + current green in this mode."""

    def __init__(self, store: StateStore, host="localhost", port=1883):
        import paho.mqtt.client as mqtt

        self.store = store
        self._last_metric_t = None
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
            kind = p.get("phase_kind")  # enriched publisher sends green/yellow/allred
            if kind == "yellow":
                phase = "yellow"
            elif kind == "allred":
                phase = "allred"
            else:
                phase = APPROACH_LABELS[idx] if 0 <= idx < 4 else "—"
            greens = p.get("greens")  # AI-planned green seconds per approach
            state = {
                "id": p["id"],
                "queues": {
                    APPROACH_LABELS[i]: queues[i] for i in range(min(4, len(queues)))
                },
                "phase": phase,
                "phase_index": idx,
                "countdown": p.get("countdown"),  # None if not provided
            }
            if greens:
                state["greens"] = {
                    APPROACH_LABELS[i]: greens[i] for i in range(min(4, len(greens)))
                }
            self.store.update_signal(state)
            # record one history point per simulation second, not per message
            t = p.get("t")
            if t != self._last_metric_t:
                self._last_metric_t = t
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
