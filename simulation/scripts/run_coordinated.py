"""Phase 4: run the corridor scenario under three control strategies and
record corridor-level metrics (eastbound travel time, time loss, stops) plus
network-wide waiting time.

Strategies (the row-1 signals A1, B1, C1 are the corridor; the other six
stay fixed in every mode):
  - fixed        : all 9 signals run the baked fixed-time program.
  - independent  : A1/B1/C1 adaptive (Phase 3), no messaging between them.
  - coordinated  : A1/B1/C1 adaptive + coordinated over the message bus,
                   predicting incoming platoons and pre-extending the
                   corridor green (green wave).

`independent` and `coordinated` use the *same* controller with coordination
toggled off/on, so the only difference is the incoming-traffic term — a clean
measurement of what coordination buys.

Run from anywhere with the project venv active:
    python simulation/scripts/run_coordinated.py
    python simulation/scripts/run_coordinated.py --transport mqtt   # over a live broker
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SIM_ROOT, ".."))

import traci

from simulation.controller.adaptive import AdaptiveIntersectionController  # noqa: F401
from simulation.controller.coordinated import CoordinatedIntersectionController
from simulation.coordination.topology import build_topology
from simulation.coordination.transport import InProcessBus, MqttBus

NET = os.path.join(SIM_ROOT, "network", "grid3x3.net.xml")
DEMAND = os.path.join(SIM_ROOT, "demand", "corridor.rou.xml")
OUTPUTS_DIR = os.path.join(SIM_ROOT, "outputs", "phase4")

SIM_END = 3600
CORRIDOR_SIGNALS = ["A1", "B1", "C1"]
MODES = ["fixed", "independent", "coordinated"]


def sumo_bin() -> str:
    import sumo

    path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo.exe")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo")
    return path


def make_bus(kind):
    if kind == "mqtt":
        return MqttBus(client_id="tl-sim")
    return InProcessBus()


def run(mode: str, transport: str):
    # keep the MQTT validation run's outputs separate from the deterministic
    # in-process metric runs so it never clobbers the reported numbers
    suffix = "_mqtt" if (transport == "mqtt" and mode == "coordinated") else ""
    out_dir = os.path.join(OUTPUTS_DIR, mode + suffix)
    os.makedirs(out_dir, exist_ok=True)
    traci.start(
        [
            sumo_bin(),
            "-n", NET,
            "-r", DEMAND,
            "-b", "0",
            "-e", str(SIM_END),
            "--tripinfo-output", os.path.join(out_dir, "tripinfo.xml"),
            "--no-step-log",
            "--duration-log.disable",
        ]
    )
    controllers = []
    bus = None
    try:
        if mode in ("independent", "coordinated"):
            topo = build_topology(NET)
            bus = make_bus(transport if mode == "coordinated" else "inprocess")
            for sid in CORRIDOR_SIGNALS:
                controllers.append(
                    CoordinatedIntersectionController(
                        traci, sid, topo[sid], bus,
                        coordinate=(mode == "coordinated"),
                    )
                )

        while traci.simulation.getTime() < SIM_END:
            traci.simulationStep()
            now = traci.simulation.getTime()
            for c in controllers:
                c.step(now)
    finally:
        traci.close()
        if bus is not None:
            bus.close()

    fb = sum(c.fallback_cycles for c in controllers)
    max_red = max((c.max_red_seen for c in controllers), default=0.0)
    result = {"mode": mode, "transport": transport, "fallback_cycles": fb,
              "controller_max_red_s": max_red}
    with open(os.path.join(out_dir, "run_info.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[{mode}] done (fallback_cycles={fb}, max_red={max_red:.0f}s)")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="*", default=MODES)
    parser.add_argument("--transport", choices=["inprocess", "mqtt"], default="inprocess")
    args = parser.parse_args()

    for mode in args.modes:
        run(mode, args.transport)
    print("All Phase 4 runs completed.")
