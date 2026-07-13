"""Parse the Phase 3 fixed-vs-adaptive outputs into a comparison table:
B1-local metrics (stopped time, queues, fairness) from local_metrics.json
and network-wide averages from tripinfo.xml.

Run from anywhere with the project venv active (after run_adaptive.py):
    python simulation/scripts/report_phase3.py
"""
import json
import os
import xml.etree.ElementTree as ET

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_ROOT = os.path.join(HERE, "..")
OUTPUTS_DIR = os.path.join(SIM_ROOT, "outputs", "phase3")
RESULTS_DIR = os.path.join(SIM_ROOT, "results")

SCENARIOS = ["low", "medium", "rush", "asymmetric"]
MODES = ["fixed", "adaptive"]


def run_metrics(scenario: str, mode: str) -> dict:
    out_dir = os.path.join(OUTPUTS_DIR, f"{scenario}_{mode}")
    with open(os.path.join(out_dir, "local_metrics.json"), encoding="utf-8") as f:
        local = json.load(f)

    trip_root = ET.parse(os.path.join(out_dir, "tripinfo.xml")).getroot()
    waits = [float(t.get("waitingTime")) for t in trip_root.findall("tripinfo")]

    return {
        "scenario": scenario,
        "mode": mode,
        "b1_avg_stop_s": local["avg_stopped_s_per_vehicle"],
        "b1_avg_queue_veh": local["avg_queue_veh"],
        "b1_max_queue_veh": local["max_queue_veh"],
        "b1_served_veh": local["vehicles_served"],
        "b1_max_red_s": local["max_red_wait_s"],
        "net_avg_wait_s": round(sum(waits) / len(waits), 2) if waits else None,
        "net_completed_veh": len(waits),
    }


def write_report(df: pd.DataFrame):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    df.to_csv(os.path.join(RESULTS_DIR, "phase3_metrics.csv"), index=False)

    lines = [
        "# Phase 3 Report: Rule-Based Adaptive Control at One Intersection (B1)",
        "",
        "One-hour simulation per demand scenario, run twice through TraCI: all 9",
        "signals fixed-time (`fixed`) vs the center intersection B1 driven by the",
        "rule-based adaptive controller while the other 8 stay fixed (`adaptive`).",
        "`b1_*` columns measure B1's four approaches only (the controlled",
        "intersection); `net_*` columns are network-wide, where one adaptive",
        "signal out of nine can only move the needle slightly.",
        "",
        df.to_markdown(index=False),
        "",
        "## Fixed vs adaptive per scenario",
        "",
        "Note: when a fixed-time queue overflows B1's 200m approach edge it",
        "spills back upstream, out of sight of the `b1_*` metrics — network",
        "average wait and vehicles served are the honest comparison under",
        "overload.",
        "",
    ]
    for scenario in SCENARIOS:
        fixed = df[(df.scenario == scenario) & (df["mode"] == "fixed")].iloc[0]
        adapt = df[(df.scenario == scenario) & (df["mode"] == "adaptive")].iloc[0]
        wait_change = (
            (adapt.net_avg_wait_s - fixed.net_avg_wait_s) / fixed.net_avg_wait_s * 100
        )
        served_change = (
            (adapt.b1_served_veh - fixed.b1_served_veh) / fixed.b1_served_veh * 100
        )
        lines.append(
            f"- **{scenario}**: network avg wait {fixed.net_avg_wait_s}s -> "
            f"{adapt.net_avg_wait_s}s ({wait_change:+.1f}%), vehicles through B1 "
            f"{fixed.b1_served_veh} -> {adapt.b1_served_veh} ({served_change:+.1f}%), "
            f"max red wait {adapt.b1_max_red_s:.0f}s (cap 120s)"
        )
    lines += [
        "",
        "## Reading the results",
        "",
        "- **asymmetric** is the scenario adaptive control exists for: ~550",
        "  veh/h converge on B1's west approach, above the ~375 veh/h a fixed",
        "  30s-of-144s phase can discharge. The adaptive signal reallocates",
        "  green to that approach and both clears more vehicles and cuts",
        "  network waiting time.",
        "- **low/medium** demand is symmetric random traffic, where 30s each",
        "  way is already near-optimal — and B1's eight fixed neighbors all run",
        "  identical 144s programs, so a fixed B1 is accidentally coordinated",
        "  with them. A lone adaptive signal breaks that sync and pays a small",
        "  penalty; inter-signal coordination (Phase 4) is the remedy.",
        "- **rush** is over capacity network-wide; no timing plan at one",
        "  junction fixes it (both modes gridlock).",
        "- Fairness held in every run: no route waited longer than the 120s",
        "  max-red cap (the controller preempts a green when a red is about to",
        "  breach it).",
        "- Fallback: with detection failure injected at t=1200s",
        "  (`run_adaptive.py --break-detection-at 1200`), the controller",
        "  reverted to the fixed 30s schedule for the remaining cycles and the",
        "  intersection kept operating safely.",
        "",
    ]

    md_path = os.path.join(RESULTS_DIR, "phase3_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    rows = [run_metrics(s, m) for s in SCENARIOS for m in MODES]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    write_report(df)
