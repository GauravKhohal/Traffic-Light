"""Smoke test for SumoIntersectionEnv: exercises reset/step end-to-end and
checks the observation/action contract and the phase-safety structure. Needs
SUMO (via libsumo/traci) but no trained model.

Run from anywhere with the project venv active:
    python simulation/rl/test_env.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from simulation.rl.sumo_env import (
    ACTION_SWITCH,
    DELTA_S,
    MIN_GREEN_S,
    SumoIntersectionEnv,
)


def main():
    env = SumoIntersectionEnv(scenario="asymmetric", episode_seconds=200, seed=0)
    obs, info = env.reset()

    assert obs.shape == env.observation_space.shape, obs.shape
    assert env.observation_space.contains(obs), obs
    assert env.action_space.n == 2

    # each route's green phase must be followed by its yellow then all-red
    # phase (the transitions the env relies on and never skips)
    import libsumo as tc  # same backend the env started
    program = tc.trafficlight.getAllProgramLogics(env.tls)[0]
    for g in env.green_phase:
        assert "y" in program.phases[g + 1].state, "green not followed by yellow"
        assert set(program.phases[g + 2].state) <= set("r"), "no all-red clearance"
    print(f"ok  phase structure: {env.n} routes, green->yellow->all-red verified")

    # a forced switch advances the served route round-robin and resets green timer
    route_before = env.route
    obs, r, term, trunc, info = env.step(ACTION_SWITCH)  # first step: green_elapsed==DELTA<MIN, so extend
    # extend until we can switch, then switch
    steps = 0
    while env.green_elapsed < MIN_GREEN_S and not trunc:
        obs, r, term, trunc, info = env.step(0)
        steps += 1
    route_at_switch = env.route
    obs, r, term, trunc, info = env.step(ACTION_SWITCH)
    assert env.route == (route_at_switch + 1) % env.n, (route_at_switch, env.route)
    assert env.green_elapsed == DELTA_S
    assert np.isfinite(r)
    print("ok  switch advances route round-robin, resets green timer, finite reward")

    # run to truncation with random actions; obs stays valid, no exceptions
    total_r = 0.0
    while not trunc:
        obs, r, term, trunc, info = env.step(env.action_space.sample())
        assert env.observation_space.contains(obs)
        assert not term  # time-limited task: truncates, never terminates
        total_r += r
    print(f"ok  full episode ran to truncation, cumulative reward {total_r:.2f}")
    env.close()
    print("env smoke test passed")


if __name__ == "__main__":
    main()
