"""Tests for the dashboard backend: state store, demo feed, REST, override,
and the WebSocket stream. No SUMO or MQTT broker needed.

    python -m pytest dashboard/backend/test_app.py -q
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from feeds import SIGNAL_IDS, DemoFeed
from state_store import APPROACH_LABELS, StateStore, grid_position


def test_grid_position():
    assert grid_position("A0") == (0, 0)
    assert grid_position("B1") == (1, 1)
    assert grid_position("C2") == (2, 2)


def test_demo_feed_populates_all_signals():
    store = StateStore()
    feed = DemoFeed(store, seed=1)
    for _ in range(5):
        feed._tick()
    signals = store.signals()
    assert len(signals) == len(SIGNAL_IDS) == 9
    for s in signals:
        assert set(s["queues"]) == set(APPROACH_LABELS)
        assert set(s["greens"]) == set(APPROACH_LABELS)
        assert all(15 <= g <= 60 for g in s["greens"].values())
        assert "phase" in s and "countdown" in s
        assert "x" in s and "y" in s
    assert len(store.history()) == 5


def test_override_set_clear_and_unknown():
    store = StateStore()
    feed = DemoFeed(store, seed=2)
    feed._tick()
    assert store.set_override("B1", "N") is True
    assert store.get_override("B1") == "N"
    assert store.set_override("B1", None) is True
    assert store.get_override("B1") is None
    assert store.set_override("ZZ", "N") is False  # unknown signal


def test_demo_override_forces_that_approach():
    store = StateStore()
    feed = DemoFeed(store, seed=3)
    feed._tick()
    store.set_override("B1", "S")
    # step until B1 next shows a green (not mid yellow/all-red); it must be S
    b1 = None
    for _ in range(120):
        feed._tick()
        b1 = next(s for s in store.signals() if s["id"] == "B1")
        if b1["phase"] in APPROACH_LABELS:  # a green approach, not a transition
            break
    assert b1["override"] == "S"
    assert b1["phase"] == "S"


def test_mode_defaults_fixed_and_switch_resets_served():
    store = StateStore()
    assert store.get_mode() == "fixed"
    store.record_served(5)
    assert store.set_mode("ai") is True
    assert store.get_mode() == "ai"
    assert store.snapshot()["served_since_mode_change"] == 0  # reset on switch
    assert store.set_mode("nonsense") is False
    assert store.get_mode() == "ai"  # unchanged by the rejected call


def test_fixed_mode_ignores_demand():
    store = StateStore()
    store.set_mode("fixed")
    feed = DemoFeed(store, seed=4)
    # force one approach heavily busy, others empty
    feed.sig["B1"]["queues"] = [22, 0, 0, 0]
    feed.sig["B1"]["rates"] = [0.0, 0.0, 0.0, 0.0]  # freeze arrivals
    for _ in range(400):
        feed._tick_signal("B1")
    b1 = next(s for s in store.signals() if s["id"] == "B1")
    # fixed mode: every green is exactly the base 30s regardless of queue
    assert all(g == 30 for g in b1["greens"].values())


def test_ai_mode_reacts_to_demand_and_skips_empty():
    store = StateStore()
    store.set_mode("ai")
    feed = DemoFeed(store, seed=4)
    feed.sig["B1"]["queues"] = [22, 0, 0, 0]
    feed.sig["B1"]["rates"] = [0.0, 0.0, 0.0, 0.0]
    feed.sig["B1"]["route"] = 1  # currently serving the empty E approach
    feed.sig["B1"]["kind"] = "green"
    feed.sig["B1"]["countdown"] = 1
    for _ in range(20):
        feed._tick_signal("B1")
    b1 = next(s for s in store.signals() if s["id"] == "B1")
    # jumps straight to the busy N approach with a boosted green, skipping
    # the empty S/W approaches entirely
    assert b1["phase"] == "N"
    assert b1["greens"]["N"] == 60


def test_ai_mode_gapout_ends_empty_green_early():
    store = StateStore()
    store.set_mode("ai")
    feed = DemoFeed(store, seed=6)
    s = feed.sig["B1"]
    s["queues"] = [0, 22, 0, 0]  # currently-served approach just drained; E is heavy
    s["rates"] = [0.0, 0.0, 0.0, 0.0]  # freeze arrivals so the queue can't refill
    s["route"] = 0
    s["kind"] = "green"
    s["greens"] = [30, 30, 30, 30]
    s["countdown"] = 24  # elapsed = 30-24 = 6s, past the 5s minimum
    feed._tick_signal("B1")
    assert s["kind"] == "yellow"  # cut short rather than idling out a 30s green on nobody


def test_ai_mode_no_gapout_before_min_green():
    store = StateStore()
    store.set_mode("ai")
    feed = DemoFeed(store, seed=6)
    s = feed.sig["B1"]
    s["queues"] = [0, 22, 0, 0]
    s["rates"] = [0.0, 0.0, 0.0, 0.0]
    s["route"] = 0
    s["kind"] = "green"
    s["greens"] = [30, 30, 30, 30]
    s["countdown"] = 27  # elapsed = 3s, under the 5s minimum
    feed._tick_signal("B1")
    assert s["kind"] == "green"  # too soon - avoids flickering a just-started green


def test_fixed_mode_never_gaps_out():
    store = StateStore()
    store.set_mode("fixed")
    feed = DemoFeed(store, seed=6)
    s = feed.sig["B1"]
    s["queues"] = [0, 22, 0, 0]
    s["rates"] = [0.0, 0.0, 0.0, 0.0]
    s["route"] = 0
    s["kind"] = "green"
    s["greens"] = [30, 30, 30, 30]
    s["countdown"] = 10  # well past the AI minimum, but fixed mode never gaps out
    feed._tick_signal("B1")
    assert s["kind"] == "green"


def test_topology_upstream_downstream():
    store = StateStore()
    feed = DemoFeed(store, seed=1)
    # B1 (centre of the grid) is fully interior: every approach is fed by a
    # real neighbour, none from outside the grid
    assert all(feed.upstream["B1"][a] is not None for a in APPROACH_LABELS)
    # A0 (bottom-left corner) has two fringe approaches (grid edges) and two
    # fed by real neighbours
    assert feed.upstream["A0"]["S"] is None  # bottom edge - nothing further south
    assert feed.upstream["A0"]["W"] is None  # left edge - nothing further west
    assert feed.upstream["A0"]["N"] == "A1"
    assert feed.upstream["A0"]["E"] == "B0"


def test_interior_signal_has_no_boosted_local_rate():
    store = StateStore()
    feed = DemoFeed(store, seed=3)
    # B1 has zero fringe approaches, so none of its local rates should ever
    # be boosted to the "busy external demand" range - its only real demand
    # comes from neighbours' discharge
    assert all(r <= 0.03 for r in feed.sig["B1"]["rates"])


def test_discharge_propagates_to_downstream_neighbor():
    store = StateStore()
    store.set_mode("ai")
    feed = DemoFeed(store, seed=2)
    b1 = feed.sig["B1"]
    b1["queues"] = [5, 0, 0, 0]  # N approach has demand
    b1["rates"] = [0.0, 0.0, 0.0, 0.0]
    b1["route"] = 0
    b1["kind"] = "green"
    b1["greens"] = [30, 30, 30, 30]
    b1["countdown"] = 20
    feed.sig["B0"]["rates"] = [0.0, 0.0, 0.0, 0.0]  # isolate: only propagation can grow it
    feed.sig["B0"]["kind"] = "allred"  # not currently discharging anything itself
    feed.sig["B0"]["countdown"] = 100
    before = feed.sig["B0"]["queues"][0]  # B0's N-approach queue
    feed._tick()
    after = feed.sig["B0"]["queues"][0]
    assert after > before, "B1's N-approach discharge should arrive at B0's N-approach queue"


def test_rest_and_websocket_endpoints():
    from app import app

    with TestClient(app) as client:
        # let the demo feed produce at least one tick
        deadline = time.time() + 3
        while time.time() < deadline:
            if client.get("/api/state").json()["signals"]:
                break
            time.sleep(0.1)

        state = client.get("/api/state").json()
        assert state["signals"], "no signals populated"
        assert state["mode"] == "fixed"
        sid = state["signals"][0]["id"]

        assert client.post("/api/mode", json={"mode": "bogus"}).status_code == 400
        assert client.post("/api/mode", json={"mode": "ai"}).status_code == 200
        assert client.get("/api/state").json()["mode"] == "ai"

        assert client.post(f"/api/signals/{sid}/override", json={"approach": "E"}).status_code == 200
        assert client.post(f"/api/signals/{sid}/override", json={"approach": "X"}).status_code == 400
        assert client.post("/api/signals/ZZ/override", json={"approach": "E"}).status_code == 404
        assert client.post(f"/api/signals/{sid}/override", json={"approach": None}).status_code == 200

        with client.websocket_connect("/ws") as websocket:
            msg = websocket.receive_json()
            assert "signals" in msg and "history" in msg


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
