"""Unit tests for the coordination layer: topology, predictor, transport
(no SUMO and no MQTT broker required).

Run from anywhere with the project venv active:
    python simulation/coordination/test_coordination.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from simulation.coordination.predictor import predict_incoming
from simulation.coordination.topology import build_topology
from simulation.coordination.transport import (
    InProcessBus,
    build_state_message,
)

NET = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "network", "grid3x3.net.xml"
)


# -- topology --------------------------------------------------------------
def test_topology_center_junction():
    topo = build_topology(NET)
    b1 = topo["B1"]
    assert b1.signal_neighbours == {"A1", "B0", "B2", "C1"}
    # west approach A1B1 is fed by A1
    assert b1.edge_from["A1B1"] == "A1"
    # outflow toward C1 goes out on edge B1C1
    assert b1.out_edge_to["C1"] == "B1C1"
    # ~186m at ~13.9 m/s
    assert 12.0 < b1.edge_travel_time["A1B1"] < 15.0


def test_topology_corner_has_two_signal_neighbours():
    topo = build_topology(NET)
    assert topo["A0"].signal_neighbours == {"A1", "B0"}


# -- predictor -------------------------------------------------------------
def test_predict_fringe_route_is_zero():
    # route fed from a network fringe (no upstream signal) predicts nothing
    got = predict_incoming("A1", [None], {}, horizon_s=60)
    assert got == [0.0]


def test_predict_uses_upstream_outflow_toward_us():
    # A1 reports 30 veh/min heading toward B1; over a 60s horizon -> 30 arrivals
    msgs = {"A1": {"id": "A1", "outflow": {"B1": 30.0, "A0": 5.0}}}
    got = predict_incoming("B1", ["A1", None, None, None], msgs, horizon_s=60)
    assert got == [30.0, 0.0, 0.0, 0.0]


def test_predict_scales_with_horizon():
    msgs = {"A1": {"id": "A1", "outflow": {"B1": 12.0}}}
    assert predict_incoming("B1", ["A1"], msgs, horizon_s=120) == [24.0]
    assert predict_incoming("B1", ["A1"], msgs, horizon_s=30) == [6.0]


def test_predict_missing_message_or_key_is_zero():
    assert predict_incoming("B1", ["A1"], {"A1": None}, 60) == [0.0]
    assert predict_incoming("B1", ["A1"], {"A1": {"outflow": {}}}, 60) == [0.0]


# -- transport -------------------------------------------------------------
def test_build_state_message_shape_and_rounding():
    msg = build_state_message("B1", 630.04, [3.2, 12, 4, 5], 1, {"C1": 14.005})
    assert msg["id"] == "B1"
    assert msg["t"] == 630.0
    assert msg["queues"] == [3.2, 12.0, 4.0, 5.0]
    assert msg["phase"] == 1
    assert msg["outflow"] == {"C1": 14.0} or msg["outflow"] == {"C1": 14.01}


def test_inprocess_bus_roundtrip():
    bus = InProcessBus()
    assert bus.latest("B1") is None
    bus.publish("B1", {"id": "B1", "outflow": {"C1": 9.0}})
    assert bus.latest("B1")["outflow"]["C1"] == 9.0
    # a later publish for the same signal replaces the previous message
    bus.publish("B1", {"id": "B1", "outflow": {"C1": 4.0}})
    assert bus.latest("B1")["outflow"]["C1"] == 4.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
