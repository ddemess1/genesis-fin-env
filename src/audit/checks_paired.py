"""P01-P20: paired checks. P01-P05 reorder (D01-D05), P06-P10 rename_ids (D06-D10), P11-P20 both (D11-D20).

Per pair: (1) repeating seed+actions gives byte-identical files and trajectory; (2) the oracle on the transformed
episode equals the original after the inverse mapping; (3) TP/FP/FN/P/R/F1/reward/steps are equal;
(4) I08 (evidence reachable) and I16 (no leaks) hold on the new variant.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from fin_env import canon, publicio
from fin_env.generator import generate_episode
from fin_env.leak import find_leaks
from fin_env.policies.oracle import OraclePolicy
from fin_env.rng import DetRng
from fin_env.runner import run_policy
from fin_env.selfcheck.invariants import _call
from fin_env.tools import PublicTools

from .common import Store
from .transforms import variant

CHECKS: dict = {}


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "eval_log.jsonl":
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def traj_hash(res) -> str:
    return hashlib.sha256("".join(canon.dumps(x) + "\n" for x in res.trajectory).encode()).hexdigest()


def submitted(res) -> list[dict]:
    last = res.trajectory[-1]["action"]
    return last["findings"]["findings"]


def paired(st: Store, dk: str, do_reorder: bool, do_rename: bool):
    root, seed, cfg = st.root(dk), st.seed(dk), st.entry(dk)["config"]
    problems = []
    # (1) determinism: regenerate from (seed, config) and replay the policy
    with tempfile.TemporaryDirectory(prefix="fin-pair-") as d:
        again = generate_episode(seed, cfg, Path(d), split="audit")
        if tree_hash(again) != tree_hash(root):
            problems.append("regenerated episode differs byte-wise")
    r1 = run_policy(OraclePolicy(root / "sealed"), root, seed=seed)
    r1b = run_policy(OraclePolicy(root / "sealed"), root, seed=seed)
    if traj_hash(r1) != traj_hash(r1b):
        problems.append("trajectory sha256 differs on replay")
    # transformed variant
    vroot, mapping = variant(root, DetRng(seed).child("paired", dk), do_reorder, do_rename,
                             st.cache_dir / "paired" / dk)
    inv = {new: old for old, new in mapping.items()}
    if do_rename:
        if any(old.split("-")[0] != new.split("-")[0] or old == new for old, new in mapping.items()):
            problems.append("rename broke prefixes or kept an id")
    r2 = run_policy(OraclePolicy(vroot / "sealed"), vroot, seed=seed)
    # (2) oracle answer equals the original after the inverse mapping
    truth = st.truth(dk)
    ok_sets = {(i["type"], tuple(i["affected_ids"]), i["expected_amount_minor"], i["currency"]):
               [frozenset(es) for es in i["evidence_sets"]] for i in truth["issues"]}
    back = []
    for f in submitted(r2):
        key = (f["type"], tuple(sorted(inv.get(x, x) for x in f["affected_ids"])), f["claimed_amount_minor"], f["currency"])
        ev = frozenset(inv.get(x, x) for x in f["evidence_ids"])
        if key not in ok_sets or ev not in ok_sets[key]:
            problems.append("oracle answer differs after inverse mapping")
        back.append(key)
    if sorted(back) != sorted((f["type"], tuple(f["affected_ids"]), f["claimed_amount_minor"], f["currency"])
                              for f in submitted(r1)):
        problems.append("set of oracle findings differs")
    # (3) identical metrics at the same number of steps
    e1, e2 = r1.evaluation, r2.evaluation
    for k in ("tp", "fp", "fn", "precision", "recall", "f1", "reward", "inspection_steps"):
        if e1[k] != e2[k]:
            problems.append(f"metric {k}: {e1[k]} != {e2[k]}")
    # (4) I08 + I16 on the new variant
    tools = PublicTools(vroot / "public")
    vt = canon.read_json(vroot / "sealed" / "truth.json")
    if not all(_call(tools, x) for i in vt["issues"] for es in i["evidence_sets"] for x in es):
        problems.append("I08: evidence not reachable in the variant")
    leaks = []
    for name in publicio.PUBLIC_FILES:
        leaks += find_leaks((vroot / "public" / name).read_text(encoding="utf-8"), st.tokens(dk))
    if leaks:
        problems.append(f"I16: {sorted(set(leaks))}")
    mode = "reorder" if (do_reorder and not do_rename) else "rename" if (do_rename and not do_reorder) else "reorder+rename"
    return not problems, f"{mode}: reward {e1['reward']} == {e2['reward']}; " + ("; ".join(problems) or "all four conditions hold")


def _make(k: int):
    dk = f"D{k:02d}"
    do_reorder, do_rename = k <= 5 or k >= 11, k >= 6
    return lambda st: paired(st, dk, do_reorder, do_rename)


for _k in range(1, 21):
    _mode = "reorder" if _k <= 5 else "rename_ids" if _k <= 10 else "reorder + rename_ids"
    CHECKS[f"P{_k:02d}"] = (f"D{_k:02d}: {_mode}", _make(_k))
