"""run_block / run_all: execute the check blocks, run the four policies, assemble the report."""
from __future__ import annotations

import hashlib
import importlib
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from fin_env import canon
from fin_env.policies import registry
from fin_env.runner import run_policy
from fin_env.version import code_version

from .common import DEFAULT_SUITE, REPO, Store
from .inject import inject
from .report import AuditCheck, AuditReport, score

BLOCK_MODULES = {"contract": "checks_contract", "data": "checks_data", "reward": "checks_reward",
                 "paired": "checks_paired"}
BLOCKING_IDS = {"C01", "C02", "C20"}


def _load(block: str):
    try:
        return importlib.import_module(f"audit.{BLOCK_MODULES[block]}")
    except ModuleNotFoundError as exc:
        if exc.name == f"audit.{BLOCK_MODULES[block]}":
            return None
        raise


def _run_one(block: str, cid: str, title: str, fn, store: Store) -> AuditCheck:
    t0 = time.monotonic()
    crashed = False
    try:
        passed, detail = fn(store)
    except Exception:  # a crashing check is a failed check; the audit goes on
        passed, crashed = False, True
        detail = "EXCEPTION " + traceback.format_exc(limit=3).replace("\n", " | ")
    ms = int((time.monotonic() - t0) * 1000)
    blocking = (not passed) and (cid in BLOCKING_IDS or (crashed and block == "contract"))
    return AuditCheck(cid, block, title, bool(passed), blocking, ms, detail)


def run_block(block: str, store: Store) -> list[AuditCheck]:
    mod = _load(block)
    if mod is None:
        return []
    items = sorted(mod.CHECKS.items())
    if block == "contract":  # C18 waits for the time limit: run it in parallel with the rest
        slow = [it for it in items if it[0] == "C18"]
        rest = [it for it in items if it[0] != "C18"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            futures = [pool.submit(_run_one, block, cid, t, fn, store) for cid, (t, fn) in slow]
            done = [_run_one(block, cid, t, fn, store) for cid, (t, fn) in rest]
            done += [f.result() for f in futures]
        return sorted(done, key=lambda c: c.check_id)
    return [_run_one(block, cid, t, fn, store) for cid, (t, fn) in items]


def run_policies(store: Store) -> dict:
    runs = []
    for dk in store.ids():
        root = store.root(dk)
        for name in registry.available():
            pol = registry.make(name, root, seed=store.seed(dk))
            try:
                r = run_policy(pol, root, seed=store.seed(dk), check_leaks=False)
            except Exception as exc:  # noqa: BLE001
                runs.append({"policy": name, "audit_id": dk, "error": type(exc).__name__})
                continue
            ev = r.evaluation
            runs.append({"policy": name, "audit_id": dk, "episode_id": r.episode_id, "group": store.group(dk),
                         "reward": r.reward, "tp": ev["tp"], "fp": ev["fp"], "fn": ev["fn"],
                         "inspection_steps": r.inspection_steps, "time_ms": r.time_ms, "truncated": r.truncated})
    summary = []
    for name in registry.available():
        rows = [r for r in runs if r["policy"] == name and "reward" in r]
        if not rows:
            continue
        mean = sum(Decimal(repr(r["reward"])) for r in rows) / len(rows)
        summary.append({"policy": name, "n": len(rows), "mean_reward": format(mean.quantize(Decimal("0.01")), "f")})
    return {"runs": runs, "summary": summary, "policies": registry.available()}


def _versions(suite_path: Path, suite: dict) -> dict:
    deps = REPO / "requirements.lock"
    return {"code_version": code_version(), "config_version": "v1", "suite_version": suite.get("suite_version", "?"),
            "config_hash": canon.sha256_bytes(Path(suite_path).read_bytes())[:12],
            "deps_hash": canon.sha256_bytes(deps.read_bytes())[:12] if deps.exists() else "none",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}"}


def run_all(suite_path: Path = DEFAULT_SUITE, cache_dir: Path | None = None, fast: bool = False,
            blocks: tuple[str, ...] = tuple(BLOCK_MODULES), bug: str | None = None,
            diagnostics: bool = True) -> AuditReport:
    t0 = time.monotonic()
    cache_dir = cache_dir or Path(tempfile.gettempdir()) / "genesis-fin-env-audit"
    with inject(bug):
        store = Store.build(Path(suite_path), Path(cache_dir), fast)
        checks: list[AuditCheck] = []
        for block in blocks:
            checks += run_block(block, store)
        diag = run_policies(store) if diagnostics else {"runs": [], "summary": [], "policies": []}
    notes = [f"inject-bug={bug}"] if bug else []
    if fast:
        notes.append("--fast: лимит времени в C18 заменён на 2 с")
    return AuditReport(_versions(suite_path, store.suite), tuple(checks), diag, score(checks),
                       int(time.monotonic() - t0), tuple(notes))
