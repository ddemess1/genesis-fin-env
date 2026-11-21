"""Run the four baseline policies on open episodes and write trajectories.jsonl + a metrics summary.

`python -m fin_env.baselines --episodes episodes/train episodes/dev --out trajectories.jsonl`
The run is in OPEN mode (train/dev only). Trajectories contain only the case's fields and are leak-checked.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import canon
from .policies import registry
from .runner import run_policy, write_trajectories


def episode_roots(split_dir: Path) -> list[Path]:
    index = canon.read_json(split_dir / "index.json")
    return [split_dir / e["episode_id"] for e in index["episodes"]]


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m fin_env.baselines")
    ap.add_argument("--episodes", type=Path, nargs="+", default=[Path("episodes/train"), Path("episodes/dev")])
    ap.add_argument("--out", type=Path, default=Path("trajectories.jsonl"))
    ap.add_argument("--summary", type=Path, default=Path("reports/baselines.json"))
    a = ap.parse_args(argv)
    results, rows = [], []
    for split_dir in a.episodes:
        groups = {e["episode_id"]: e["group"] for e in canon.read_json(split_dir / "index.json")["episodes"]}
        for root in episode_roots(split_dir):
            seed = canon.read_json(root / "sealed" / "provenance.json")["seed"]
            for name in registry.available():
                res = run_policy(registry.make(name, root, seed=seed), root, seed=seed)
                results.append(res)
                ev = res.evaluation
                rows.append({"split": split_dir.name, "policy": name, "episode_id": res.episode_id,
                             "group": groups[root.name], "reward": res.reward, "tp": ev["tp"], "fp": ev["fp"],
                             "fn": ev["fn"], "inspection_steps": res.inspection_steps, "time_ms": res.time_ms,
                             "truncated": res.truncated})
    write_trajectories(a.out, results)
    a.summary.parent.mkdir(parents=True, exist_ok=True)
    canon.write_json(a.summary, {"runs": rows})
    lines = sum(len(r.trajectory) for r in results)
    print(f"{len(results)} runs, {lines} trajectory lines -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
