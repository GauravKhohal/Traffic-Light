"""Runs a trained DQN policy on intersection B1 over TraCI during evaluation,
so the RL agent is measured with the same LocalMetrics harness as the fixed
and rule-based strategies.

Mirrors SumoIntersectionEnv's control loop (same DELTA / min-max green /
yellow+all-red transitions and the same shared `build_observation`), stepped
once per simulation second so it drops into the common evaluation loop
alongside AdaptiveIntersectionController.
"""
from simulation.rl.sumo_env import (
    ACTION_EXTEND,
    ALLRED_S,
    DELTA_S,
    MAX_GREEN_S,
    MIN_GREEN_S,
    YELLOW_S,
    build_observation,
    derive_routes,
)


class RLController:
    def __init__(self, conn, tls_id, model, deterministic=True):
        self.conn = conn
        self.tls = tls_id
        self.model = model
        self.deterministic = deterministic

        self.green_phase, self.route_lanes, self.all_lanes = derive_routes(conn, tls_id)
        self.n = len(self.green_phase)

        self.route = 0
        self.state = "green"
        self.state_elapsed = 0
        self.green_elapsed = 0
        self._set_phase(self.green_phase[self.route])

        # reported for parity with the other controllers
        self.fallback_cycles = 0
        self.max_red_seen = 0.0
        self.red_times = [0.0] * self.n

    def _set_phase(self, phase_idx):
        self.conn.trafficlight.setPhase(self.tls, phase_idx)
        self.conn.trafficlight.setPhaseDuration(self.tls, 10_000)

    def _enter(self, state, phase_idx):
        self.state = state
        self.state_elapsed = 0
        self._set_phase(phase_idx)

    def _decide(self):
        if self.green_elapsed < MIN_GREEN_S:
            return  # min-green protection: extend
        if self.green_elapsed < MAX_GREEN_S:
            obs = build_observation(self.conn, self.route_lanes, self.route, self.green_elapsed)
            action, _ = self.model.predict(obs, deterministic=self.deterministic)
            if int(action) == ACTION_EXTEND:
                return
        # switch (agent chose to, or max-green forces it): begin yellow
        self._enter("yellow", self.green_phase[self.route] + 1)

    def step(self, now):
        for r in range(self.n):
            if self.state == "green" and r == self.route:
                self.red_times[r] = 0.0
            else:
                self.red_times[r] += 1.0
                self.max_red_seen = max(self.max_red_seen, self.red_times[r])

        self.state_elapsed += 1
        if self.state == "green":
            self.green_elapsed += 1
            if self.green_elapsed % DELTA_S == 0:
                self._decide()
        elif self.state == "yellow":
            if self.state_elapsed >= YELLOW_S:
                self._enter("allred", self.green_phase[self.route] + 2)
        elif self.state == "allred":
            if self.state_elapsed >= ALLRED_S:
                self.route = (self.route + 1) % self.n
                self._enter("green", self.green_phase[self.route])
                self.green_elapsed = 0
