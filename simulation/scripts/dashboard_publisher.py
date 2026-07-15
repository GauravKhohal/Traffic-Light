"""Feed the Phase 6 dashboard from a live SUMO run over MQTT.

Runs the corridor scenario with the row-1 signals (A1/B1/C1) under coordinated
adaptive control and the other six fixed, and publishes *every* signal's live
state — per-approach queues, current phase, phase kind, and countdown — to
`signals/{id}/state` every second, so the dashboard shows all nine
intersections driven by the real simulation (not the synthetic demo feed).

The corridor controllers coordinate over an in-process bus; MQTT here is used
purely to stream state to the dashboard. Loops forever (restarts each hour)
and is paced to be watchable.

Prereqs: an MQTT broker on localhost:1883, and the backend in mqtt mode.
    docker run -d --rm --name mq -p 1883:1883 eclipse-mosquitto:2
    DASHBOARD_FEED=mqtt python -m uvicorn app:app --app-dir dashboard/backend --port 8000
    python simulation/scripts/dashboard_publisher.py
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(SIM_ROOT, ".."))

import paho.mqtt.client as mqtt
import traci

from simulation.controller.coordinated import CoordinatedIntersectionController
from simulation.coordination.topology import build_topology
from simulation.coordination.transport import InProcessBus

NET = os.path.join(SIM_ROOT, "network", "grid3x3.net.xml")
DEMAND_DIR = os.path.join(SIM_ROOT, "demand")
SIM_END = 3600
CORRIDOR = ["A1", "B1", "C1"]
SCENARIOS = ["corridor", "low", "medium", "rush", "asymmetric"]


def sumo_bin():
    import sumo

    p = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo.exe")
    return p if os.path.exists(p) else os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo")


def derive_routes(tls):
    program = traci.trafficlight.getAllProgramLogics(tls)[0]
    links = traci.trafficlight.getControlledLinks(tls)
    green_phase, route_lanes = [], []
    for idx, ph in enumerate(program.phases):
        if "G" not in ph.state and "g" not in ph.state:
            continue
        green_phase.append(idx)
        lanes = {links[s][0][0] for s, c in enumerate(ph.state) if c in "Gg" and links[s]}
        route_lanes.append(sorted(lanes))
    return green_phase, route_lanes


def signal_state(tls, green_phase, route_lanes, controller, now):
    queues = [int(sum(traci.lane.getLastStepHaltingNumber(l) for l in lanes)) for lanes in route_lanes]
    if controller is not None:
        route, kind = controller.route, controller.state
        countdown = max(0, round(controller.switch_at - now))
        greens = [round(g) for g in controller.greens]  # AI-planned green per approach
    else:
        greens = [30] * len(route_lanes)  # fixed signals: static 30s plan
        cur = traci.trafficlight.getPhase(tls)
        if cur in green_phase:
            route, kind = green_phase.index(cur), "green"
        elif cur - 1 in green_phase:
            route, kind = green_phase.index(cur - 1), "yellow"
        elif cur - 2 in green_phase:
            route, kind = green_phase.index(cur - 2), "allred"
        else:
            route, kind = 0, "green"
        countdown = max(0, round(traci.trafficlight.getNextSwitch(tls) - now))
    return {
        "id": tls,
        "t": round(now, 1),
        "queues": queues,
        "greens": greens,
        "phase": route if kind == "green" else -1,
        "phase_kind": kind,
        "countdown": countdown,
    }


def run_once(client, pace, demand):
    traci.start([sumo_bin(), "-n", NET, "-r", demand, "-b", "0", "-e", str(SIM_END),
                 "--no-step-log", "--no-warnings", "--time-to-teleport", "-1"])
    try:
        topo = build_topology(NET)
        bus = InProcessBus()
        controllers = {sid: CoordinatedIntersectionController(traci, sid, topo[sid], bus, coordinate=True)
                       for sid in CORRIDOR}
        all_tls = traci.trafficlight.getIDList()
        routes = {t: derive_routes(t) for t in all_tls}

        while traci.simulation.getTime() < SIM_END:
            traci.simulationStep()
            now = traci.simulation.getTime()
            for sid in CORRIDOR:
                controllers[sid].step(now)
            for t in all_tls:
                gp, rl = routes[t]
                msg = signal_state(t, gp, rl, controllers.get(t), now)
                client.publish(f"signals/{t}/state", json.dumps(msg), qos=1, retain=True)
            time.sleep(pace)
    finally:
        traci.close()


def main(host, port, pace, loop, scenario):
    demand = os.path.join(DEMAND_DIR, f"{scenario}.rou.xml")
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="tl-dash-pub")
    client.connect(host, port)
    client.loop_start()
    print(f"Publishing all 9 signals ({scenario} demand) to {host}:{port} (Ctrl+C to stop)")
    try:
        while True:
            run_once(client, pace, demand)
            if not loop:
                break
            print("episode complete; restarting...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--scenario", default="corridor", choices=SCENARIOS,
                    help="traffic demand pattern to simulate")
    ap.add_argument("--pace", type=float, default=0.08, help="real seconds per sim second")
    ap.add_argument("--no-loop", action="store_true")
    a = ap.parse_args()
    main(a.host, a.port, a.pace, loop=not a.no_loop, scenario=a.scenario)
