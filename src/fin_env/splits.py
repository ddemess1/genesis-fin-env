"""Generate the open train/dev episodes: `python -m fin_env.splits --config configs/splits.json --out episodes`."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import canon
from .generator import generate_episode


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m fin_env.splits")
    ap.add_argument("--config", type=Path, default=Path("configs/splits.json"))
    ap.add_argument("--out", type=Path, default=Path("episodes"))
    a = ap.parse_args(argv)
    spec = canon.read_json(a.config)
    for split in ("train", "dev"):
        out = a.out / split
        if out.exists():
            shutil.rmtree(out)
        index = []
        for e in spec[split]:
            root = generate_episode(e["seed"], e["config"], out, split)
            index.append({"episode_id": root.name, "group": e["group"]})
            print(f"{split} seed={e['seed']} -> {root.name} ({e['group']})")
        canon.write_json(out / "index.json", {"split": split, "episodes": index})
    return 0


if __name__ == "__main__":
    sys.exit(main())
