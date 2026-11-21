"""`python -m demo.attack --kind dup|ccy|amount+1|flag_all|no_evidence [--episode episodes/dev/ep_xxx]`

Takes the oracle's correct answer for an OPEN episode, applies one corruption and prints two lines:
the honest reward vs the attack reward, and TP/FP/FN. Refuses closed episodes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fin_env import canon
from fin_env.env import FinAuditEnv
from fin_env.policies.flag_all import FlagAllPolicy
from fin_env.runner import run_policy
from viz.style import fmt_reward

KINDS = ("dup", "ccy", "amount+1", "flag_all", "no_evidence")


def pick_episode(split_dir: Path) -> Path:
    for e in canon.read_json(split_dir / "index.json")["episodes"]:
        root = split_dir / e["episode_id"]
        if canon.read_json(root / "sealed" / "truth.json")["issues"]:
            return root
    raise SystemExit("no episode with errors found")


def oracle_findings(root: Path) -> tuple[list[dict], str]:
    truth = canon.read_json(root / "sealed" / "truth.json")
    return [{"type": i["type"], "affected_ids": list(i["affected_ids"]), "claimed_amount_minor": i["expected_amount_minor"],
             "currency": i["currency"], "evidence_ids": list(i["evidence_sets"][0]), "explanation": "recomputed from evidence"}
            for i in truth["issues"]], truth["episode_id"]


def corrupt(kind: str, findings: list[dict]) -> list[dict]:
    f = [dict(x) for x in findings]
    if kind == "dup":
        return f + [dict(f[0])]
    if kind == "ccy":
        f[0]["currency"] = "USD" if f[0]["currency"] != "USD" else "EUR"
    elif kind == "amount+1":
        f[0]["claimed_amount_minor"] += 1
    elif kind == "no_evidence":
        f[0]["evidence_ids"] = []
    return f


def submit_run(root: Path, findings: list[dict], eid: str, steps: int = 10) -> tuple[float, dict]:
    env = FinAuditEnv(evaluator_mode="inproc")
    env.reset(None, {"episode_dir": str(root), "mode": "open"})
    for _ in range(steps):
        env.step({"action": "calculator", "expression": "1+1"})
    _, reward, *_ = env.step({"action": "submit", "findings": {"episode_id": eid, "findings": findings}})
    return reward, env.evaluation_result()


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m demo.attack")
    ap.add_argument("--kind", choices=KINDS, required=True)
    ap.add_argument("--episode", type=Path, default=None)
    ap.add_argument("--split-dir", type=Path, default=Path("episodes/dev"))
    a = ap.parse_args(argv)
    root = a.episode or pick_episode(a.split_dir)
    prov = canon.read_json(root / "sealed" / "provenance.json")
    if prov["split"] == "closed":
        raise SystemExit("demo.attack works only on open train/dev episodes")
    findings, eid = oracle_findings(root)
    honest, hev = submit_run(root, findings, eid)
    if a.kind == "flag_all":
        res = run_policy(FlagAllPolicy(), root)
        attack, aev = res.reward, res.evaluation
    else:
        attack, aev = submit_run(root, corrupt(a.kind, findings), eid)
    print(f"эпизод {eid} · атака {a.kind}")
    print(f"честный: {fmt_reward(honest)} · атака: {fmt_reward(attack)}")
    print(f"честный TP/FP/FN = {hev['tp']}/{hev['fp']}/{hev['fn']} · атака TP/FP/FN = {aev['tp']}/{aev['fp']}/{aev['fn']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
