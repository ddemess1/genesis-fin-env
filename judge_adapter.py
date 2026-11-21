"""Adapter for the jury harness: generate_episode(seed, config, output_dir), make_env(), score_episode(...).

Modes of FinAuditEnv.reset(seed, config): mode="closed" + episode_dir (+ team_config, ignored) loads a
pre-generated episode; mode="train" generates an open episode from seed + team_config.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fin_env.env import FinAuditEnv  # noqa: E402
from fin_env.evaluator import LocalEvaluator  # noqa: E402
from fin_env.generator import fill_defaults  # noqa: E402
from fin_env.generator import generate_episode as _generate  # noqa: E402


def generate_episode(seed: int, config: dict | None, output_dir) -> Path:
    """Write public/ and sealed/ directly into output_dir (it becomes the episode_dir). Returns output_dir."""
    out = Path(output_dir)
    with tempfile.TemporaryDirectory(prefix="fin-env-gen-") as tmp:
        root = _generate(seed, fill_defaults(config), Path(tmp), split="closed")
        out.mkdir(parents=True, exist_ok=True)
        for part in ("public", "sealed"):
            if (out / part).exists():
                shutil.rmtree(out / part)
            shutil.copytree(root / part, out / part)
    return out


def make_env() -> FinAuditEnv:
    return FinAuditEnv(evaluator_mode="process")


def score_episode(episode_dir, findings, inspection_steps: int) -> dict:
    """Evaluator-side scoring with the shared matcher and reward. Metrics are None on a structural error."""
    root = Path(episode_dir)
    res = LocalEvaluator(root / "sealed", root / "public").evaluate(findings, inspection_steps)
    bad = res["structural_error"] is not None
    from decimal import Decimal
    from fin_env.reward import to_json_number
    return {"reward": to_json_number(Decimal(res["reward"])), "structural_error": res["structural_error"],
            **{k: (None if bad else (res[k] if k in ("tp", "fp", "fn") else res[k]))
               for k in ("tp", "fp", "fn", "precision", "recall", "f1")}}
