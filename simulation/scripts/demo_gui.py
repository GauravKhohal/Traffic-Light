"""Visual demo: open the SUMO GUI and let the adaptive controller run the
row-1 corridor (A1-B1-C1) live, so you can watch real car / jeep / truck / bus
shapes queue up and see the busy east-west approach get a long green while the
light cross streets get short greens.

Run from anywhere with the project venv active:
    python simulation/scripts/demo_gui.py
    python simulation/scripts/demo_gui.py --scenario asymmetric   # any demand file
    python simulation/scripts/demo_gui.py --fixed                 # baseline for contrast

A SUMO GUI window opens and starts automatically. Close the window (or Ctrl+C)
to stop. B1 is the centre intersection.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SIM_ROOT, ".."))

import traci

from simulation.controller.coordinated import CoordinatedIntersectionController
from simulation.coordination.topology import build_topology
from simulation.coordination.transport import InProcessBus

NET = os.path.join(SIM_ROOT, "network", "grid3x3.net.xml")
DEMAND_DIR = os.path.join(SIM_ROOT, "demand")
SIM_END = 3600
CORRIDOR = ["A1", "B1", "C1"]


def sumo_gui_bin():
    import sumo

    b = os.path.join(os.path.dirname(sumo.__file__), "bin")
    p = os.path.join(b, "sumo-gui.exe")
    return p if os.path.exists(p) else os.path.join(b, "sumo-gui")


def main(scenario, adaptive, pace):
    demand = os.path.join(DEMAND_DIR, f"{scenario}.rou.xml")
    traci.start(
        [
            sumo_gui_bin(),
            "-n", NET,
            "-r", demand,
            "-b", "0",
            "-e", str(SIM_END),
            "--start",          # begin immediately, don't wait for the play button
            "--quit-on-end", "false",
            "--delay", "120",    # GUI render delay (ms) for watchability
            "--no-warnings",
            "--time-to-teleport", "-1",
        ]
    )
    controllers = []
    try:
        if adaptive:
            topo = build_topology(NET)
            bus = InProcessBus()
            controllers = [
                CoordinatedIntersectionController(traci, sid, topo[sid], bus, coordinate=True)
                for sid in CORRIDOR
            ]
        while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < SIM_END:
            traci.simulationStep()
            now = traci.simulation.getTime()
            for c in controllers:
                c.step(now)
            if pace:
                time.sleep(pace)
    except traci.exceptions.FatalTraCIError:
        pass  # window closed
    finally:
        try:
            traci.close()
        except Exception:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="demo_gui")
    ap.add_argument("--images", action="store_true",
                    help="render vehicles as overhead images (car/jeep/truck/bus) instead of shapes")
    ap.add_argument("--fixed", action="store_true", help="run the fixed-time baseline instead of adaptive")
    ap.add_argument("--pace", type=float, default=0.05, help="extra real seconds per sim step")
    a = ap.parse_args()
    scenario = "demo_gui_img" if (a.images and a.scenario == "demo_gui") else a.scenario
    main(scenario, adaptive=not a.fixed, pace=a.pace)
