"""Assignment 6, Part C: each measured run's outcome, from the tracker (checks/FORMATS.md, 14.7).

    python eval/results_06.py

Writes results/runs_06.jsonl, one line per finished measured run: a vendor's model, on a
fixtures/tasks6 task, by the agent, split or splus way. A pass is eval/check_task.py's,
read from the tracker; tokens and wall-clock are the run_end line's. Never a model's words.

Also writes results/summary_06.json: per arm and kind of task, the fields reports/LAB_06.json
takes (section 14.8), the multiplier, the constants, and S-plus's budget and spend beside
arm M's, task by task.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.check_task import check_task  # noqa: E402
from harness.formats import ARMS, UNFINISHED  # noqa: E402
from harness.runner import is_free, is_trace  # noqa: E402
from harness.tasks import load_tasks  # noqa: E402
from harness.trace import read_trace  # noqa: E402
from harness.tracker import Tracker  # noqa: E402

SWEEPS = 3


def measured_runs(tasks: dict) -> list[dict]:
    """Every finished run on the task set, by an arm's way, on a vendor's model."""
    out = []
    for path in sorted((ROOT / "runs").glob("*.jsonl")):
        if not is_trace(path):
            continue
        records = read_trace(path)
        start = records[0] if records and records[0].get("type") == "run_start" else None
        if not start or start.get("task") not in tasks or start.get("way") not in ARMS:
            continue
        if is_free(start.get("backend") or ""):
            continue
        ends = {r.get("terminal_reason") for r in records if r.get("type") == "end"}
        if records[-1].get("type") != "run_end" or ends & set(UNFINISHED):
            continue
        out.append({"start": start, "end": records[-1]})
    return out


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict]) -> dict:
    """The fields section 14.8 names, computed the way the checker recomputes them."""
    out = {}
    for kind in ("single", "batch"):
        mine = [r for r in rows if r["kind"] == kind]
        per_task, sweeps = {}, {}
        for r in mine:
            per_task[r["task"]] = per_task.get(r["task"], 0) + int(r["passed"])
            sweeps[r["sweep"]] = sweeps.get(r["sweep"], 0) + int(r["passed"])
        out[kind] = {"runs": len(mine), "passes": sum(int(r["passed"]) for r in mine),
                     "per_task": dict(sorted(per_task.items())),
                     "sweep_min": min(sweeps.values()) if sweeps else 0,
                     "sweep_max": max(sweeps.values()) if sweeps else 0,
                     "all_three": sum(1 for v in per_task.values() if v >= SWEEPS),
                     "mean_tokens": round(mean(r["tokens"] for r in mine)),
                     "mean_wall_s": round(mean(r["wall_s"] for r in mine), 1),
                     "issue_parts": [sum(sum(r["parts"].values()) for r in mine),
                                     sum(len(r["parts"]) for r in mine)]}
    return out


def main() -> int:
    tasks = {t.id: t for t in load_tasks(ROOT / "fixtures" / "tasks6")}
    tracker = Tracker(ROOT, flaky=False, readback_fail=False)
    rows, constants = [], set()
    for run in measured_runs(tasks):
        start, end = run["start"], run["end"]
        checked = check_task(start["run_id"], tasks[start["task"]], tracker=tracker)
        constants.add(json.dumps(start.get("constants"), sort_keys=True))
        rows.append({"run_id": start["run_id"], "arm": ARMS[start["way"]], "way": start["way"],
                     "task": start["task"], "kind": start["kind"], "sweep": start["sweep"],
                     "passed": checked["passed"], "parts": {str(k): v for k, v in checked["parts"].items()},
                     "tokens": int(end["totals"]["total_tokens"]), "wall_s": float(end["elapsed_s"]),
                     "budget": start.get("budget"), "started_at": start.get("started_at")})
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    with (out / "runs_06.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps({k: v for k, v in r.items() if k not in ("budget", "started_at")}) + "\n")

    arms = {arm: summarize([r for r in rows if r["arm"] == arm]) for arm in ("S", "M", "S_plus")}
    multiplier = {k: (round(arms["M"][k]["mean_tokens"] / arms["S"][k]["mean_tokens"], 2)
                      if arms["S"][k]["mean_tokens"] and arms["M"][k]["mean_tokens"] else None)
                  for k in ("single", "batch")}
    match = {}
    for tid in tasks:
        m = [r["tokens"] for r in rows if r["arm"] == "M" and r["task"] == tid]
        sp = [r for r in rows if r["arm"] == "S_plus" and r["task"] == tid]
        if m or sp:
            match[tid] = {"M_mean_tokens": round(mean(m)), "S_plus_budget": sorted({r["budget"] for r in sp}),
                          "S_plus_mean_tokens": round(mean(r["tokens"] for r in sp)),
                          "S_plus_over_M": round(mean(r["tokens"] for r in sp) / mean(m), 2) if m and sp else None}
    summary = {"arms": arms, "multiplier": multiplier, "splus_vs_m": match,
               "constants": [json.loads(c) for c in sorted(constants)]}
    (out / "summary_06.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(f"{len(rows)} finished measured runs -> results/runs_06.jsonl; summary -> results/summary_06.json")
    for arm in ("S", "M", "S_plus"):
        for kind in ("single", "batch"):
            a = arms[arm][kind]
            if a["runs"]:
                print(f"  {arm:<6} {kind:<6} passes {a['passes']}/{a['runs']} (sweeps {a['sweep_min']}-{a['sweep_max']}, "
                      f"all three {a['all_three']}), issues {a['issue_parts'][0]}/{a['issue_parts'][1]}, "
                      f"mean {a['mean_tokens']:,} tokens, {a['mean_wall_s']} s")
    print(f"  multiplier M/S: {multiplier}")
    if len(constants) > 1:
        print(f"  WARNING: the runs carry {len(constants)} different sets of constants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
