"""Phase 3: run each demand scenario twice through TraCI — once with the
network's fixed-time program untouched, once with the center intersection
(B1) driven by the rule-based adaptive controller — and record both SUMO's
network-wide outputs and B1-local metrics (stopped-time, queue lengths,
vehicles served, max red wait per route).

Only B1 is adaptive in Phase 3; the other 8 signals keep fixed timing in
both modes, so the fixed runs double as an apples-to-apples local baseline.

Run from anywhere with the project venv active:
    python simulation/scripts/run_adaptive.py
Optional: --break-detection-at <t> makes B1's queue detection start failing
at simulation time t in adaptive mode, to demonstrate the fixed-time
fallback (safety requirement #6).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SIM_ROOT, ".."))

import traci

from simulation.controller.adaptive import AdaptiveIntersectionController

NET = os.path.join(SIM_ROOT, "network", "grid3x3.net.xml")
DEMAND_DIR = os.path.join(SIM_ROOT, "demand")
OUTPUTS_DIR = os.path.join(SIM_ROOT, "outputs", "phase3")

SIM_END = 3600
SCENARIOS = ["low", "medium", "rush", "asymmetric"]
MODES = ["fixed", "adaptive"]
TLS_ID = "B1"


def sumo_bin() -> str:
    import sumo

    path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo.exe")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo")
    return path


class LocalMetrics:
    """Per-route metrics on one intersection's approach lanes, sampled every
    simulation second. Total halted vehicle-seconds divided by vehicles
    served gives average stopped time per vehicle at this intersection."""

    def __init__(self, conn, tls_id: str):
        self.conn = conn
        lanes = set()
        self.route_lanes = []
        program = conn.trafficlight.getAllProgramLogics(tls_id)[0]
        links = conn.trafficlight.getControlledLinks(tls_id)
        self.signals_per_route = []
        for phase in program.phases:
            if "G" not in phase.state and "g" not in phase.state:
                continue
            sigs = [i for i, ch in enumerate(phase.state) if ch in "Gg"]
            self.signals_per_route.append(sigs)
            rl = sorted({links[s][0][0] for s in sigs if links[s]})
            self.route_lanes.append(rl)
            lanes.update(rl)
        self.tls = tls_id
        self.all_lanes = sorted(lanes)
        self.n = len(self.route_lanes)

        self.halted_veh_seconds = 0.0
        self.queue_samples = []  # total halting vehicles per second
        self.max_queue = 0
        self.on_approach = set()
        self.served = 0
        self.red_time = [0.0] * self.n
        self.max_red = [0.0] * self.n

    def sample(self):
        halting = sum(
            self.conn.lane.getLastStepHaltingNumber(l) for l in self.all_lanes
        )
        self.halted_veh_seconds += halting
        self.queue_samples.append(halting)
        self.max_queue = max(self.max_queue, halting)

        current = set()
        for l in self.all_lanes:
            current.update(self.conn.lane.getLastStepVehicleIDs(l))
        self.served += len(self.on_approach - current)
        self.on_approach = current

        state = self.conn.trafficlight.getRedYellowGreenState(self.tls)
        for r, sigs in enumerate(self.signals_per_route):
            if all(state[s] in "rR" for s in sigs):
                self.red_time[r] += 1.0
                self.max_red[r] = max(self.max_red[r], self.red_time[r])
            else:
                self.red_time[r] = 0.0

    def summary(self) -> dict:
        return {
            "vehicles_served": self.served,
            "avg_stopped_s_per_vehicle": round(
                self.halted_veh_seconds / self.served, 2
            )
            if self.served
            else None,
            "avg_queue_veh": round(
                sum(self.queue_samples) / len(self.queue_samples), 2
            ),
            "max_queue_veh": self.max_queue,
            "max_red_wait_s": max(self.max_red),
        }


def run(scenario: str, mode: str, break_detection_at: int | None):
    suffix = "_fallback" if break_detection_at is not None else ""
    out_dir = os.path.join(OUTPUTS_DIR, f"{scenario}_{mode}{suffix}")
    os.makedirs(out_dir, exist_ok=True)
    traci.start(
        [
            sumo_bin(),
            "-n", NET,
            "-r", os.path.join(DEMAND_DIR, f"{scenario}.rou.xml"),
            "-b", "0",
            "-e", str(SIM_END),
            "--tripinfo-output", os.path.join(out_dir, "tripinfo.xml"),
            "--no-step-log",
            "--duration-log.disable",
        ]
    )
    try:
        metrics = LocalMetrics(traci, TLS_ID)
        controller = None
        if mode == "adaptive":
            controller = AdaptiveIntersectionController(traci, TLS_ID)
            if break_detection_at is not None:
                real_read = controller.read_queues

                def failing_read():
                    if traci.simulation.getTime() >= break_detection_at:
                        raise RuntimeError("simulated detection failure")
                    return real_read()

                controller.read_queues = failing_read

        while traci.simulation.getTime() < SIM_END:
            traci.simulationStep()
            now = traci.simulation.getTime()
            if controller is not None:
                controller.step(now)
            metrics.sample()

        result = {"scenario": scenario, "mode": mode, **metrics.summary()}
        if controller is not None:
            result["fallback_cycles"] = controller.fallback_cycles
            result["controller_max_red_s"] = controller.max_red_seen
    finally:
        traci.close()

    with open(os.path.join(out_dir, "local_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[{scenario}/{mode}] {result}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    parser.add_argument("--modes", nargs="*", default=MODES)
    parser.add_argument("--break-detection-at", type=int, default=None)
    args = parser.parse_args()

    for scenario in args.scenarios:
        for mode in args.modes:
            run(scenario, mode, args.break_detection_at)
    print("All Phase 3 runs completed.")
