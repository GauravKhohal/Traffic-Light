"""Run the fixed-time baseline for each demand scenario and write SUMO's
built-in output files (tripinfo, queue, statistics, summary) to
simulation/outputs/<scenario>/.

Run from anywhere with the project venv active:
    python simulation/scripts/run_baseline.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
NET = os.path.join(SIM_ROOT, "network", "grid3x3.net.xml")
DEMAND_DIR = os.path.join(SIM_ROOT, "demand")
OUTPUTS_DIR = os.path.join(SIM_ROOT, "outputs")

SIM_BEGIN = 0
SIM_END = 3600
SCENARIOS = ["low", "medium", "rush"]


def sumo_bin() -> str:
    import sumo

    path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo.exe")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(sumo.__file__), "bin", "sumo")
    return path


def run_scenario(name: str):
    out_dir = os.path.join(OUTPUTS_DIR, name)
    os.makedirs(out_dir, exist_ok=True)
    route_file = os.path.join(DEMAND_DIR, f"{name}.rou.xml")

    cmd = [
        sumo_bin(),
        "-n", NET,
        "-r", route_file,
        "-b", str(SIM_BEGIN),
        "-e", str(SIM_END),
        "--tripinfo-output", os.path.join(out_dir, "tripinfo.xml"),
        "--queue-output", os.path.join(out_dir, "queue.xml"),
        "--queue-output.period", "10",
        "--statistic-output", os.path.join(out_dir, "stats.xml"),
        "--summary-output", os.path.join(out_dir, "summary.xml"),
        "--no-step-log",
        "--duration-log.disable",
    ]
    print(f"[{name}] Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        sys.exit(f"[{name}] sumo exited with code {result.returncode}")

    for fname in ("tripinfo.xml", "queue.xml", "stats.xml", "summary.xml"):
        path = os.path.join(out_dir, fname)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            sys.exit(f"[{name}] Expected non-empty output file: {path}")
    print(f"[{name}] OK -> {out_dir}")


if __name__ == "__main__":
    for scenario in SCENARIOS:
        run_scenario(scenario)
    print("All baseline runs completed.")
