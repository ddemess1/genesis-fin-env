"""The four organizer-style policies, in the fixed display order used by reports and the matrix."""
from __future__ import annotations

from pathlib import Path

ORDER = ("oracle", "reconcile", "random", "flag_all")
LABELS = {"oracle": "oracle", "reconcile": "простая сверка", "random": "случайная", "flag_all": "пометить всё"}


def available() -> list[str]:
    out = ["oracle", "flag_all"]
    try:
        from . import reconcile  # noqa: F401
        out.append("reconcile")
    except ImportError:
        pass
    try:
        from . import random_explorer  # noqa: F401
        out.append("random")
    except ImportError:
        pass
    return [n for n in ORDER if n in out]


def make(name: str, episode_root: Path, seed: int = 0):
    """Instantiate a policy for one episode. Only the oracle touches sealed/ (evaluator-side)."""
    if name == "oracle":
        from .oracle import OraclePolicy
        return OraclePolicy(Path(episode_root) / "sealed")
    if name == "flag_all":
        from .flag_all import FlagAllPolicy
        return FlagAllPolicy()
    if name == "reconcile":
        from .reconcile import ReconcilePolicy
        return ReconcilePolicy()
    if name == "random":
        from .random_explorer import RandomExplorer
        return RandomExplorer(seed)
    raise KeyError(name)
