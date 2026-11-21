"""One-command check: tests -> generate open episodes -> baselines/trajectories -> audit -> viz.

`python scripts/check.py [--fast]`  (also: `make check`). Exit code is non-zero on the first failing stage.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(title: str, *cmd: str) -> None:
    print(f"\n=== {title}", flush=True)
    t0 = time.monotonic()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": "0", "PYTHONIOENCODING": "utf-8"}
    code = subprocess.call([sys.executable, *cmd], cwd=ROOT, env=env)
    print(f"--- {title}: exit {code} in {time.monotonic() - t0:.0f} s", flush=True)
    if code not in (0,):
        sys.exit(code)


def main() -> None:
    fast = ["--fast"] if "--fast" in sys.argv else []
    run("tests", "-m", "pytest", "-q")
    run("generate train/dev episodes", "-m", "fin_env.splits")
    run("baselines + trajectories.jsonl", "-m", "fin_env.baselines")
    run("self-audit (80 checks)", "-m", "audit", *fast)
    run("viz (matrix, diff cards, causal graphs)", "-m", "viz", "--episodes", "episodes/train", "episodes/dev")


if __name__ == "__main__":
    main()
