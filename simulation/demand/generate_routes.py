"""Generate low/medium/rush traffic demand for the 3x3 grid network using
SUMO's bundled randomTrips.py.

Run from anywhere with the project venv active:
    python simulation/demand/generate_routes.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NET = os.path.join(HERE, "..", "network", "grid3x3.net.xml")

SIM_BEGIN = 0
SIM_END = 3600

# period (seconds between vehicle insertions, network-wide): lower = busier
SCENARIOS = {
    "low": {"period": 3.0, "seed": 1},
    "medium": {"period": 1.5, "seed": 2},
    "rush": {"period": 0.7, "seed": 3},
}


def find_random_trips_script() -> str:
    import sumo

    tools_dir = os.path.join(os.path.dirname(sumo.__file__), "tools")
    script = os.path.join(tools_dir, "randomTrips.py")
    if not os.path.exists(script):
        sys.exit(f"Could not find randomTrips.py under {tools_dir}")
    return script


def generate(name: str, period: float, seed: int, random_trips: str):
    trips_out = os.path.join(HERE, f"{name}.trips.xml")
    rou_out = os.path.join(HERE, f"{name}.rou.xml")
    cmd = [
        sys.executable,
        random_trips,
        "-n", NET,
        "-o", trips_out,
        "-r", rou_out,
        "-b", str(SIM_BEGIN),
        "-e", str(SIM_END),
        "-p", str(period),
        "--fringe-factor", "5",
        "--allow-fringe",
        "--validate",
        "--seed", str(seed),
        "--prefix", f"{name}_",
    ]
    print(f"[{name}] Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    with open(rou_out, encoding="utf-8") as f:
        count = f.read().count("<vehicle ")
    print(f"[{name}] {count} vehicles over {SIM_END - SIM_BEGIN}s (period={period})")
    return count


if __name__ == "__main__":
    random_trips = find_random_trips_script()
    counts = {}
    for name, cfg in SCENARIOS.items():
        counts[name] = generate(name, cfg["period"], cfg["seed"], random_trips)

    if not (counts["low"] < counts["medium"] < counts["rush"]):
        sys.exit(f"Expected low < medium < rush vehicle counts, got {counts}")
    print("Demand generation OK:", counts)
