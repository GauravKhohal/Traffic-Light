"""Rule-based adaptive signal control (Phase 3).

Implements the spec's core algorithm for a single intersection:

    demand_i = q_i + alpha * incoming_i
    green_i  = clamp(G_min, G_max, G_base * n * demand_i / total_demand)
    renormalize so the full cycle (greens + fixed yellow/all-red lost time)
    stays within [CYCLE_MIN, CYCLE_MAX]
    anti-starvation: a route about to breach MAX_RED_S of red preempts the
    current green (cut short, transitions still honored) and is served next
    safety: 4s yellow + 2s all-red between phases, never skipped
    fallback: if queue detection fails, revert to the fixed 30s schedule

`incoming_i` (predicted arrivals from upstream signals) is plumbed through
but always 0 in Phase 3 — it comes alive with MQTT coordination in Phase 4.

The pure allocation math lives in `allocate_green_times` (unit-testable
without SUMO); `AdaptiveIntersectionController` wraps it in a TraCI-driven
phase state machine for one traffic light.
"""

GREEN_BASE_S = 30.0
GREEN_MIN_S = 15.0
GREEN_MAX_S = 60.0
YELLOW_S = 4.0
ALLRED_S = 2.0
CYCLE_MIN_S = 90.0
CYCLE_MAX_S = 180.0
MAX_RED_S = 120.0
# Preempt early enough that the yellow + all-red transition still lands the
# starving route's green before its red time crosses MAX_RED_S.
PREEMPT_RED_S = MAX_RED_S - YELLOW_S - ALLRED_S
ALPHA = 0.5
# Queue-clearance cap: a green longer than what its queue needs to discharge
# (saturation headway per vehicle + startup lost time) just inflates the
# cycle and everyone else's red wait, so greens are capped at clearance time.
SATURATION_HEADWAY_S = 2.0
STARTUP_LOST_S = 3.0


def clamp(lo: float, hi: float, x: float) -> float:
    return max(lo, min(hi, x))


def allocate_green_times(queues, incoming=None, alpha: float = ALPHA):
    """Return one green duration per route for the next cycle.

    Proportional share of the base cycle by demand, clamped per route to
    [GREEN_MIN_S, GREEN_MAX_S] and capped at the queue's clearance time,
    then iteratively rescaled so the cycle length (greens + per-phase
    yellow/all-red lost time) lands within [CYCLE_MIN_S, CYCLE_MAX_S].
    With 4 routes the feasible green-sum range is [66, 156]s, which the
    per-route clamps can always satisfy.
    """
    n = len(queues)
    if incoming is None:
        incoming = [0.0] * n
    demand = [q + alpha * inc for q, inc in zip(queues, incoming)]
    total = sum(demand)
    if total <= 0:
        return [GREEN_BASE_S] * n

    greens = []
    for d in demand:
        share = clamp(GREEN_MIN_S, GREEN_MAX_S, GREEN_BASE_S * n * d / total)
        clear = max(GREEN_MIN_S, SATURATION_HEADWAY_S * d + STARTUP_LOST_S)
        greens.append(min(share, clear))

    lost = n * (YELLOW_S + ALLRED_S)
    lo, hi = CYCLE_MIN_S - lost, CYCLE_MAX_S - lost
    for _ in range(8):
        s = sum(greens)
        if lo <= s <= hi:
            break
        target = clamp(lo, hi, s)
        greens = [clamp(GREEN_MIN_S, GREEN_MAX_S, g * target / s) for g in greens]
    return greens


def pick_next_route(red_times, unserved):
    """Anti-starvation phase ordering: serve the route whose red time has
    reached the preemption threshold (worst first) even out of rotation;
    otherwise the longest-waiting route not yet served this cycle."""
    starving = [r for r, t in enumerate(red_times) if t >= PREEMPT_RED_S]
    if starving:
        return max(starving, key=lambda r: red_times[r])
    return max(unserved, key=lambda r: red_times[r])


class AdaptiveIntersectionController:
    """Drives one SUMO traffic light adaptively over TraCI.

    Assumes the netconvert `--tls.layout incoming` program shape: for each
    of the n approaches a green phase followed by its yellow and all-red
    phases (indices g, g+1, g+2). Call `step(now)` once per simulation
    second after `simulationStep()`.
    """

    def __init__(self, conn, tls_id: str):
        self.conn = conn
        self.tls = tls_id

        program = conn.trafficlight.getAllProgramLogics(tls_id)[0]
        links = conn.trafficlight.getControlledLinks(tls_id)
        self.green_phase = []  # phase index of each route's green
        self.route_lanes = []  # incoming lanes of each route
        for idx, phase in enumerate(program.phases):
            if "G" not in phase.state and "g" not in phase.state:
                continue
            self.green_phase.append(idx)
            lanes = {
                links[sig][0][0]
                for sig, ch in enumerate(phase.state)
                if ch in "Gg" and links[sig]
            }
            self.route_lanes.append(sorted(lanes))
        self.n = len(self.green_phase)

        self.red_times = [0.0] * self.n
        self.fallback_cycles = 0
        self.max_red_seen = 0.0
        self._reset_queue_average()

        # first cycle runs at base timing; no demand has been observed yet
        self.greens = [GREEN_BASE_S] * self.n
        self.unserved = set(range(self.n))
        self._start_green(self._pick_route(), now=0.0)

    # -- detection ---------------------------------------------------------
    def read_queues(self):
        """Halting-vehicle count per route on its approach lanes. Raising
        here (detection failure) triggers the fixed-time fallback."""
        return [
            sum(self.conn.lane.getLastStepHaltingNumber(l) for l in lanes)
            for lanes in self.route_lanes
        ]

    def _reset_queue_average(self):
        self._queue_sums = [0.0] * self.n
        self._queue_steps = 0
        self._detection_ok = True

    # -- cycle planning ----------------------------------------------------
    def _plan_cycle(self):
        """Allocate the next cycle's greens from each route's queue averaged
        over the whole previous cycle. An instantaneous snapshot would
        systematically under-count whichever route was served last (its
        queue is empty right at the cycle boundary); the average measures
        actual demand. Any detection failure during the cycle falls back to
        the fixed 30s schedule for the next cycle."""
        if self._detection_ok and self._queue_steps > 0:
            queues = [s / self._queue_steps for s in self._queue_sums]
            self.greens = allocate_green_times(queues)
        else:
            self.greens = [GREEN_BASE_S] * self.n
            self.fallback_cycles += 1
        self._reset_queue_average()
        self.unserved = set(range(self.n))

    def _pick_route(self):
        return pick_next_route(self.red_times, self.unserved)

    # -- phase state machine ------------------------------------------------
    def _set(self, phase_idx: int, duration: float, now: float):
        self.conn.trafficlight.setPhase(self.tls, phase_idx)
        self.conn.trafficlight.setPhaseDuration(self.tls, duration)
        self.switch_at = now + duration

    def _start_green(self, route: int, now: float):
        self.route = route
        self.unserved.discard(route)
        self.state = "green"
        self._set(self.green_phase[route], self.greens[route], now)

    def step(self, now: float):
        # accumulate this cycle's queue observations for the next plan
        try:
            for r, q in enumerate(self.read_queues()):
                self._queue_sums[r] += q
            self._queue_steps += 1
        except Exception:
            self._detection_ok = False

        # red-time bookkeeping (the currently-green route's timer resets)
        for r in range(self.n):
            if self.state == "green" and r == self.route:
                self.red_times[r] = 0.0
            else:
                self.red_times[r] += 1.0
                self.max_red_seen = max(self.max_red_seen, self.red_times[r])

        # max-red-time override: if any waiting route is about to breach
        # MAX_RED_S, cut the current green short (yellow/all-red still run)
        preempt = self.state == "green" and any(
            self.red_times[r] >= PREEMPT_RED_S
            for r in range(self.n)
            if r != self.route
        )
        if now < self.switch_at and not preempt:
            return
        if self.state == "green":
            self.state = "yellow"
            self._set(self.green_phase[self.route] + 1, YELLOW_S, now)
        elif self.state == "yellow":
            self.state = "allred"
            self._set(self.green_phase[self.route] + 2, ALLRED_S, now)
        else:  # all-red finished -> next green
            if not self.unserved:
                self._plan_cycle()
            self._start_green(self._pick_route(), now)
