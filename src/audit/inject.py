"""--inject-bug: deliberately broken code paths, to prove the audit is not always green.

leak  : observations carry a debug field that points at the sealed truth        -> C20 (and the leak scans)
dup   : the matcher counts duplicate findings as true positives                  -> M05 (and the matrix assertion)
order : the generator shuffles tables with an unseeded RNG (non-determinism)     -> P-block repeat checks, D determinism
"""
from __future__ import annotations

import random
from contextlib import contextmanager

BUGS = ("leak", "dup", "order")


@contextmanager
def inject(bug: str | None):
    if bug is None:
        yield
        return
    if bug not in BUGS:
        raise SystemExit(f"unknown bug {bug!r}; choose one of {BUGS}")
    from fin_env import evaluator, generator
    from fin_env.env import FinAuditEnv
    from fin_env.matcher import is_match
    saved = (FinAuditEnv._obs, evaluator.match, generator.write_public)
    if bug == "leak":
        orig = FinAuditEnv._obs

        def leaky(self, result=None, error=None):
            obs = orig(self, result, error)
            obs["debug"] = {"truth_path": "episodes/dev/sealed/truth.json"}
            return obs
        FinAuditEnv._obs = leaky
    elif bug == "dup":
        def greedy(findings, issues, known):
            tp = sum(1 for f in findings if any(is_match(f, i, known) for i in issues))
            return {"tp": tp, "fp": len(findings) - tp, "fn": max(0, len(issues) - tp), "matched": []}
        evaluator.match = greedy
    else:
        real = generator.write_public

        class _Unseeded:
            def shuffle(self, items):
                random.shuffle(items)
        generator.write_public = lambda s, m, rng, d, e: real(s, m, _Unseeded(), d, e)
    try:
        yield
    finally:
        FinAuditEnv._obs, evaluator.match, generator.write_public = saved
