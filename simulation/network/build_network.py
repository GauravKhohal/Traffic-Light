"""Generate the 3x3 grid SUMO network with a fixed-time (30s green / 4s
yellow / 2s all-red) traffic-light program baked into every junction, using
netconvert's native TLS duration options.

Run from anywhere with the project venv active:
    python simulation/network/build_network.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_NET = os.path.join(HERE, "grid3x3_raw.net.xml")
NET = os.path.join(HERE, "grid3x3.net.xml")

GREEN_S = 30
YELLOW_S = 4
ALLRED_S = 2

# netgenerate's grid junction naming: columns A,B,C x rows 0,1,2
INTERIOR_JUNCTIONS = [f"{col}{row}" for col in "ABC" for row in "012"]


def sumo_bin(name: str) -> str:
    import sumo

    path = os.path.join(os.path.dirname(sumo.__file__), "bin", f"{name}.exe")
    if not os.path.exists(path):
        # non-Windows fallback
        path = os.path.join(os.path.dirname(sumo.__file__), "bin", name)
    if not os.path.exists(path):
        sys.exit(f"Could not find bundled binary: {name} (looked at {path})")
    return path


def run_netgenerate():
    cmd = [
        sumo_bin("netgenerate"),
        "--grid",
        "--grid.x-number", "3",
        "--grid.y-number", "3",
        "--grid.x-length", "200",
        "--grid.y-length", "200",
        "--grid.attach-length", "200",
        "--default.lanenumber", "1",
        "--tls.default-type", "static",
        "--output-file", RAW_NET,
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_netconvert_fixed_tls():
    """Explicitly assign TLS to the 9 interior grid junctions (netgenerate's
    --tls.guess heuristic skips them at this grid's edge speeds/geometry),
    group each phase to one incoming approach (--tls.layout incoming), and
    bake in the spec's fixed 30s/4s/2s durations directly."""
    cmd = [
        sumo_bin("netconvert"),
        "-s", RAW_NET,
        "--tls.set", ",".join(INTERIOR_JUNCTIONS),
        "--tls.layout", "incoming",
        "--tls.default-type", "static",
        "--tls.green.time", str(GREEN_S),
        "--tls.yellow.time", str(YELLOW_S),
        "--tls.allred.time", str(ALLRED_S),
        "-o", NET,
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def verify():
    import sumolib

    net = sumolib.net.readNet(NET, withPrograms=True)
    tls_list = net.getTrafficLights()
    if len(tls_list) != 9:
        sys.exit(f"Expected 9 traffic-light junctions, got {len(tls_list)}")

    cycle = 4 * (GREEN_S + YELLOW_S + ALLRED_S)
    for tls in tls_list:
        program = next(iter(tls.getPrograms().values()))
        phases = program.getPhases()
        if len(phases) != 12:
            sys.exit(f"tls {tls.getID()}: expected 12 phases, got {len(phases)}")
        total = sum(p.duration for p in phases)
        if total != cycle:
            sys.exit(f"tls {tls.getID()}: expected cycle {cycle}s, got {total}s")
    print(f"Verified {len(tls_list)} tlLogic programs, 12 phases each, cycle={cycle}s")


if __name__ == "__main__":
    run_netgenerate()
    run_netconvert_fixed_tls()
    verify()
