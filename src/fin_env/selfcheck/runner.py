"""verify_clean / verify_episode: run all invariants, never stop at the first failure."""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from .. import publicio
from ..books.state import BookState, MutationRecord
from ..serialize import load_public_state, raw_to_state
from .invariants import CLEAN_CHECKS, EPISODE_CHECKS, CheckResult, Ctx


@dataclass(frozen=True)
class CheckReport:
    episode_id: str
    ok: bool
    results: tuple[CheckResult, ...]
    duration_ms: int


class EpisodeInvalid(Exception):
    def __init__(self, report: CheckReport, seed=None):
        self.report = report
        failed = ", ".join(f"{r.check_id}({','.join(r.refs[:3]) or '-'})" for r in report.results if not r.passed)
        super().__init__(f"seed={seed}, failed: {failed}")


def _run(checks, ctx: Ctx, episode_id: str) -> CheckReport:
    t0 = time.monotonic()
    results = []
    for fn in checks:
        try:
            results.append(fn(ctx))
        except Exception:  # a crashing invariant is a failed invariant
            results.append(CheckResult(fn.__name__.upper(), False, None,
                                       traceback.format_exc(limit=2).replace("\n", " | ")))
    ms = int((time.monotonic() - t0) * 1000)
    return CheckReport(episode_id, all(r.passed for r in results), tuple(results), ms)


def verify_clean(clean: BookState) -> CheckReport:
    return _run(CLEAN_CHECKS, Ctx(clean=clean), clean.manifest.get("episode_id", "clean"))


def verify_episode(clean: BookState, dirty: BookState, recs: list[MutationRecord], truth: dict,
                   public_dir: Path, id_map: dict, seed: int | None = None) -> CheckReport:
    raw = publicio.load_raw(public_dir)
    ctx = Ctx(clean=clean, pub=raw_to_state(raw), dirty_mem=dirty, raw=raw, recs=recs, truth=truth,
              id_map=id_map, public_dir=Path(public_dir), seed=seed)
    return _run(EPISODE_CHECKS, ctx, truth["episode_id"])


__all__ = ["CheckReport", "EpisodeInvalid", "verify_clean", "verify_episode", "load_public_state"]
