"""Gymnasium environment wrapping SUMO for RL control of one intersection (B1),
matching the Phase 3/4 single-intersection comparison point (Phase 5).

Per the spec:
  - state  = queue lengths + incoming predictions + current phase + time in phase
  - action = extend the current green, or switch to the next approach
  - reward = negative sum of waiting times (differential form: the drop in
             total waiting seconds on B1's approaches since the last decision)

Safety is enforced by the env, not learned: every switch runs the fixed 4s
yellow + 2s all-red (never skipped), a minimum green protects each phase, and
a maximum green forces a switch. Fairness (no starvation) is left to the
reward — waiting on a demanded approach is penalised — rather than a hard cap,
so the agent's behaviour is genuinely learned.

Uses libsumo (in-process, fast) when available, else traci. Single instance
per process, so train with a single (non-subproc) env.
"""
import os

import gymnasium as gym
import numpy as np
from gymnasium import spaces

try:
    import libsumo as tc

    HAVE_LIBSUMO = True
except ImportError:  # pragma: no cover - fallback path
    import traci as tc

    HAVE_LIBSUMO = False

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
NET = os.path.join(SIM_ROOT, "network", "grid3x3.net.xml")
DEMAND_DIR = os.path.join(SIM_ROOT, "demand")

YELLOW_S = 4
ALLRED_S = 2
MIN_GREEN_S = 10
MAX_GREEN_S = 60
DELTA_S = 5              # decision interval / green extension quantum
COUNT_NORM = 20.0        # observation scaling for vehicle counts
REWARD_SCALE = 0.01      # keep reward magnitudes small for the Q-network

ACTION_EXTEND = 0
ACTION_SWITCH = 1


def sumo_bin() -> str:
    import sumo

    path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo.exe")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo")
    return path


# -- shared route/observation helpers (one source of truth for train + eval) --
def derive_routes(conn, tls_id):
    """Return (green_phase indices, per-route incoming lanes, all lanes) from
    the tls program, matching the adaptive controller's derivation."""
    program = conn.trafficlight.getAllProgramLogics(tls_id)[0]
    links = conn.trafficlight.getControlledLinks(tls_id)
    green_phase, route_lanes = [], []
    for idx, phase in enumerate(program.phases):
        if "G" not in phase.state and "g" not in phase.state:
            continue
        green_phase.append(idx)
        lanes = {
            links[sig][0][0]
            for sig, ch in enumerate(phase.state)
            if ch in "Gg" and links[sig]
        }
        route_lanes.append(sorted(lanes))
    all_lanes = sorted({l for lanes in route_lanes for l in lanes})
    return green_phase, route_lanes, all_lanes


def read_queues(conn, route_lanes):
    return np.array(
        [sum(conn.lane.getLastStepHaltingNumber(l) for l in lanes) for lanes in route_lanes],
        dtype=np.float32,
    )


def read_incoming(conn, route_lanes):
    """Approaching (moving) vehicles per route = on-approach minus halting; a
    single-intersection proxy for predicted arrivals."""
    out = []
    for lanes in route_lanes:
        total = sum(conn.lane.getLastStepVehicleNumber(l) for l in lanes)
        halt = sum(conn.lane.getLastStepHaltingNumber(l) for l in lanes)
        out.append(max(0, total - halt))
    return np.array(out, dtype=np.float32)


def build_observation(conn, route_lanes, route, green_elapsed):
    n = len(route_lanes)
    phase_onehot = np.zeros(n, dtype=np.float32)
    phase_onehot[route] = 1.0
    return np.concatenate(
        [
            read_queues(conn, route_lanes) / COUNT_NORM,
            read_incoming(conn, route_lanes) / COUNT_NORM,
            phase_onehot,
            np.array([green_elapsed / MAX_GREEN_S], dtype=np.float32),
        ]
    )


class SumoIntersectionEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, scenario="asymmetric", tls_id="B1", episode_seconds=1200, seed=None):
        super().__init__()
        self.scenario = scenario
        self.tls = tls_id
        self.episode_seconds = episode_seconds
        self._seed = seed
        self._started = False

        # discovered on first reset (route structure is fixed for this net)
        self.n = 4
        # obs: queues(n) + incoming(n) + phase one-hot(n) + time-in-phase(1)
        self.observation_space = spaces.Box(
            low=0.0, high=np.inf, shape=(3 * self.n + 1,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(2)

    # -- SUMO lifecycle -----------------------------------------------------
    def _start_sumo(self, seed):
        route = os.path.join(DEMAND_DIR, f"{self.scenario}.rou.xml")
        cmd = [
            sumo_bin(),
            "-n", NET,
            "-r", route,
            "-b", "0",
            "-e", str(self.episode_seconds),
            "--no-step-log",
            "--no-warnings",
            "--time-to-teleport", "-1",   # disable teleporting so gridlock is visible, not hidden
            "--seed", str(seed if seed is not None else 0),
        ]
        tc.start(cmd)
        self._started = True

    def _build_routes(self):
        self.green_phase, self.route_lanes, self.all_lanes = derive_routes(tc, self.tls)
        self.n = len(self.green_phase)

    # -- measurements -------------------------------------------------------
    def _total_wait(self):
        return sum(tc.lane.getWaitingTime(l) for l in self.all_lanes)

    def _obs(self):
        return build_observation(tc, self.route_lanes, self.route, self.green_elapsed)

    # -- phase control ------------------------------------------------------
    def _set_phase(self, phase_idx):
        tc.trafficlight.setPhase(self.tls, phase_idx)
        tc.trafficlight.setPhaseDuration(self.tls, 10_000)  # pin; we drive transitions

    def _advance(self, seconds):
        for _ in range(int(seconds)):
            if tc.simulation.getTime() >= self.episode_seconds:
                break
            tc.simulationStep()

    # -- gym API ------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if self._started:
            tc.close()
            self._started = False
        use_seed = seed if seed is not None else self._seed
        self._start_sumo(use_seed)
        self._build_routes()

        self.route = 0
        self.green_elapsed = 0
        self._set_phase(self.green_phase[self.route])
        self._advance(DELTA_S)
        self.green_elapsed = DELTA_S
        self._prev_wait = self._total_wait()
        return self._obs(), {}

    def step(self, action):
        # apply min/max-green safety constraints to the requested action
        if self.green_elapsed < MIN_GREEN_S:
            effective = ACTION_EXTEND
        elif self.green_elapsed >= MAX_GREEN_S:
            effective = ACTION_SWITCH
        else:
            effective = int(action)

        if effective == ACTION_SWITCH:
            self._set_phase(self.green_phase[self.route] + 1)  # yellow
            self._advance(YELLOW_S)
            self._set_phase(self.green_phase[self.route] + 2)  # all-red
            self._advance(ALLRED_S)
            self.route = (self.route + 1) % self.n
            self._set_phase(self.green_phase[self.route])
            self._advance(DELTA_S)
            self.green_elapsed = DELTA_S
        else:
            self._set_phase(self.green_phase[self.route])
            self._advance(DELTA_S)
            self.green_elapsed += DELTA_S

        cur_wait = self._total_wait()
        reward = (self._prev_wait - cur_wait) * REWARD_SCALE
        self._prev_wait = cur_wait

        truncated = tc.simulation.getTime() >= self.episode_seconds
        return self._obs(), float(reward), False, truncated, {"total_wait": cur_wait}

    def close(self):
        if self._started:
            tc.close()
            self._started = False
