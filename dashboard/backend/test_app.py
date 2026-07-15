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
        sid = state["signals"][0]["id"]

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
