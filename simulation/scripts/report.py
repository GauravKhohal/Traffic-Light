"""Parse SUMO's per-scenario output files (tripinfo, queue, stats) and write
a metrics summary CSV + short markdown report.

Run from anywhere with the project venv active:
    python simulation/scripts/report.py
"""
import os
import sys
import xml.etree.ElementTree as ET

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
OUTPUTS_DIR = os.path.join(SIM_ROOT, "outputs")
RESULTS_DIR = os.path.join(SIM_ROOT, "results")

SIM_DURATION_HOURS = 3600 / 3600
SCENARIOS = ["low", "medium", "rush"]


def scenario_metrics(name: str) -> dict:
    out_dir = os.path.join(OUTPUTS_DIR, name)

    trip_root = ET.parse(os.path.join(out_dir, "tripinfo.xml")).getroot()
    waiting_times = [float(t.get("waitingTime")) for t in trip_root.findall("tripinfo")]
    if not waiting_times:
        sys.exit(f"[{name}] No completed trips found in tripinfo.xml")
    avg_wait = sum(waiting_times) / len(waiting_times)
    max_wait = max(waiting_times)
    throughput = len(waiting_times) / SIM_DURATION_HOURS  # vehicles/hour

    queue_root = ET.parse(os.path.join(out_dir, "queue.xml")).getroot()
    queue_lengths = [
        float(lane.get("queueing_length_experimental"))
        for data in queue_root.findall("data")
        for lane in data.findall("./lanes/lane")
    ]
    avg_queue = sum(queue_lengths) / len(queue_lengths) if queue_lengths else 0.0
    max_queue = max(queue_lengths) if queue_lengths else 0.0

    return {
        "scenario": name,
        "vehicles_completed": len(waiting_times),
        "avg_wait_s": round(avg_wait, 2),
        "max_wait_s": round(max_wait, 2),
        "avg_queue_m": round(avg_queue, 2),
        "max_queue_m": round(max_queue, 2),
        "throughput_veh_per_hour": round(throughput, 1),
    }


def write_report(df: pd.DataFrame):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    csv_path = os.path.join(RESULTS_DIR, "metrics_summary.csv")
    df.to_csv(csv_path, index=False)

    md_path = os.path.join(RESULTS_DIR, "phase1_report.md")
    lines = [
        "# Phase 1 Report: Fixed-Time Baseline (3x3 grid, 30s green / 4s yellow / 2s all-red)",
        "",
        "One-hour (3600s) simulation per demand scenario. Queue length is a "
        "network-wide aggregate (avg/max across all lanes and 10s samples); "
        "per-route breakdowns come in later phases alongside the adaptive controller.",
        "",
        df.to_markdown(index=False),
        "",
    ]

    wait_ok = df["avg_wait_s"].is_monotonic_increasing
    queue_ok = df["avg_queue_m"].is_monotonic_increasing
    ordering_note = (
        "Average waiting time and average queue length both increase "
        "monotonically from low to medium to rush demand, as expected."
        if wait_ok and queue_ok
        else "NOTE: expected monotonic low < medium < rush ordering did not "
        "fully hold - inspect metrics_summary.csv."
    )
    lines.append(ordering_note)
    lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    rows = [scenario_metrics(name) for name in SCENARIOS]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    write_report(df)
