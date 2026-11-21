"""Shared audit plumbing: suite loading, episode store (always regenerated), env helpers."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from fin_env import canon, publicio
from fin_env.env import FinAuditEnv
from fin_env.generator import generate_episode
from fin_env.leak import seed_tokens

REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_SUITE = REPO / "configs" / "audit_suite.json"


@dataclass
class Store:
    """The 20 audit episodes, regenerated from (seed, config) at the start of every audit."""
    suite: dict
    cache_dir: Path
    fast: bool = False
    roots: dict[str, Path] = field(default_factory=dict)

    @classmethod
    def build(cls, suite_path: Path, cache_dir: Path, fast: bool = False) -> "Store":
        suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        store = cls(suite, cache_dir, fast)
        for e in suite["episodes"]:
            store.roots[e["id"]] = generate_episode(e["seed"], e["config"], cache_dir, split="audit")
        return store

    def entry(self, dk: str) -> dict:
        return next(e for e in self.suite["episodes"] if e["id"] == dk)

    def root(self, dk: str) -> Path:
        return self.roots[dk]

    def seed(self, dk: str) -> int:
        return self.entry(dk)["seed"]

    def tokens(self, dk: str) -> tuple[str, ...]:
        return seed_tokens(self.seed(dk))

    def raw(self, dk: str) -> dict:
        return publicio.load_raw(self.root(dk) / "public")

    def truth(self, dk: str) -> dict:
        return canon.read_json(self.root(dk) / "sealed" / "truth.json")

    def group(self, dk: str) -> str:
        return self.entry(dk)["group"]

    def ids(self) -> list[str]:
        return [e["id"] for e in self.suite["episodes"]]


def new_env(store: Store, dk: str, mode: str = "open", evaluator: str = "inproc", **cfg):
    env = FinAuditEnv(evaluator_mode=evaluator)
    obs, info = env.reset(None, {"episode_dir": str(store.root(dk)), "mode": mode, **cfg})
    return env, obs, info


def calc_step(env, expr: str = "1+1"):
    return env.step({"action": "calculator", "expression": expr})


def submit_action(store: Store, dk: str, findings) -> dict:
    return {"action": "submit", "findings": {"episode_id": store.truth(dk)["episode_id"], "findings": findings}}


def oracle_findings(store: Store, dk: str, evidence_index: int = 0) -> list[dict]:
    return [{"type": i["type"], "affected_ids": list(i["affected_ids"]),
             "claimed_amount_minor": i["expected_amount_minor"], "currency": i["currency"],
             "evidence_ids": list(i["evidence_sets"][evidence_index]), "explanation": "recomputed from evidence"}
            for i in store.truth(dk)["issues"]]


def play(store: Store, dk: str, findings, inspections: int = 10, mode: str = "open"):
    """Spend `inspections` steps, submit `findings`. Returns (env, last step tuple)."""
    env, _, _ = new_env(store, dk, mode)
    for _ in range(inspections):
        calc_step(env)
    return env, env.step(submit_action(store, dk, findings))
