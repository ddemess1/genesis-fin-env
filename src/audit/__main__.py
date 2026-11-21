"""`python -m audit [--fast] [--block B] [--inject-bug leak|dup|order]`  exit: 0 ok, 1 failures, 3 blocking."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .common import DEFAULT_SUITE, REPO
from .inject import BUGS
from .report import render_console, render_json, render_markdown
from .runner import BLOCK_MODULES, run_all


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m audit")
    ap.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    ap.add_argument("--out", type=Path, default=REPO / "reports")
    ap.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "genesis-fin-env-audit")
    ap.add_argument("--fast", action="store_true", help="C18 uses a 2 s limit instead of 60 s")
    ap.add_argument("--block", choices=list(BLOCK_MODULES) + ["all"], default="all")
    ap.add_argument("--inject-bug", choices=BUGS, default=None)
    ap.add_argument("--no-diagnostics", action="store_true")
    a = ap.parse_args(argv)
    blocks = tuple(BLOCK_MODULES) if a.block == "all" else (a.block,)
    report = run_all(a.suite, a.cache, a.fast, blocks, a.inject_bug, not a.no_diagnostics)
    print(render_console(report))
    if a.inject_bug is None:
        render_json(report, a.out / "audit.json")
        render_markdown(report, a.out / "audit.md")
    else:  # never overwrite the real report with a deliberately broken run
        render_json(report, a.out / f"audit.inject-{a.inject_bug}.json")
        render_markdown(report, a.out / f"audit.inject-{a.inject_bug}.md")
    if report.score["blocking"]:
        return 3
    return 0 if all(c.passed for c in report.checks) else 1


if __name__ == "__main__":
    sys.exit(main())
