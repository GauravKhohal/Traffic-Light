"""Unit tests for the pure allocation/starvation logic (no SUMO needed).

Run from anywhere with the project venv active:
    python simulation/controller/test_adaptive.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from simulation.controller.adaptive import (
    ALLRED_S,
    CYCLE_MAX_S,
    CYCLE_MIN_S,
    GREEN_BASE_S,
    GREEN_MAX_S,
    GREEN_MIN_S,
    YELLOW_S,
    allocate_green_times,
    pick_next_route,
)


def cycle_length(greens):
    return sum(greens) + len(greens) * (YELLOW_S + ALLRED_S)


def check_invariants(greens):
    assert all(GREEN_MIN_S <= g <= GREEN_MAX_S for g in greens), greens
    assert CYCLE_MIN_S <= cycle_length(greens) <= CYCLE_MAX_S, greens


def test_no_demand_gives_base_timing():
    assert allocate_green_times([0, 0, 0, 0]) == [GREEN_BASE_S] * 4


def test_equal_demand_stays_equal_and_trims_cycle():
    greens = allocate_green_times([7, 7, 7, 7])
    check_invariants(greens)
    assert len(set(greens)) == 1
    # 7 queued vehicles clear in well under 30s: no point burning base green
    assert greens[0] < GREEN_BASE_S


def test_light_demand_shrinks_cycle_to_minimum():
    greens = allocate_green_times([1, 1, 1, 1])
    check_invariants(greens)
    assert cycle_length(greens) == CYCLE_MIN_S


def test_saturated_equal_demand_keeps_base_timing():
    # queues too long to clear: clearance cap not binding, proportional rules
    assert allocate_green_times([40, 40, 40, 40]) == [GREEN_BASE_S] * 4


def test_heavy_route_gains_light_routes_shrink():
    greens = allocate_green_times([20, 1, 1, 1])
    check_invariants(greens)
    assert greens[0] > GREEN_BASE_S
    assert all(g < GREEN_BASE_S for g in greens[1:])
    assert greens[0] > max(greens[1:])


def test_extreme_skew_still_respects_clamps_and_cycle():
    greens = allocate_green_times([500, 0, 0, 0])
    check_invariants(greens)
    assert greens[0] == GREEN_MAX_S
    assert all(g == GREEN_MIN_S for g in greens[1:])


def test_monotonic_in_queue_size():
    greens = allocate_green_times([2, 4, 8, 16])
    check_invariants(greens)
    assert greens == sorted(greens)


def test_incoming_traffic_extends_green():
    without = allocate_green_times([5, 5, 5, 5], incoming=[0, 0, 0, 0])
    with_inc = allocate_green_times([5, 5, 5, 5], incoming=[20, 0, 0, 0])
    assert with_inc[0] > without[0]
    check_invariants(with_inc)


def test_starving_route_forced_next():
    # routes past the preemption threshold win even if already served or
    # not the longest-waiting unserved route; worst offender first
    assert pick_next_route([130.0, 40.0, 121.0, 0.0], unserved={1, 3}) == 0
    assert pick_next_route([10.0, 40.0, 121.0, 0.0], unserved={1, 3}) == 2
    # just below the threshold: normal rotation applies
    assert pick_next_route([113.0, 40.0, 0.0, 0.0], unserved={1, 3}) == 1


def test_normal_rotation_serves_longest_waiting_unserved():
    assert pick_next_route([50.0, 80.0, 20.0, 0.0], unserved={0, 2}) == 0
    assert pick_next_route([50.0, 80.0, 20.0, 0.0], unserved={1, 2, 3}) == 1


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
