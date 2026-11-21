"""M01-M20: matcher / reward reliability checks on predefined answers (over D06 = errors, D01 = clean)."""
from __future__ import annotations

import itertools
from decimal import Decimal

from fin_env.matcher import match
from fin_env.policies.flag_all import FlagAllPolicy
from fin_env.runner import run_policy

from .common import Store, calc_step, new_env, oracle_findings, play, submit_action

CHECKS: dict = {}
BAD, CLEAN = "D06", "D01"
OTHER_TYPE = {"duplicate_invoice": "fx_conversion", "payment_allocation": "period_cutoff",
              "fx_conversion": "duplicate_invoice", "period_cutoff": "payment_allocation"}


def check(cid, title):
    def deco(fn):
        CHECKS[cid] = (title, fn)
        return fn
    return deco


def run(st: Store, dk: str, findings, steps: int = 10):
    env, last = play(st, dk, findings, steps)
    ev = env.evaluation_result()
    return {**ev, "r": Decimal(ev["reward"]), "last": last}


def fp_fn(res, n_issues=1):
    return res["tp"] == 0 and res["fp"] >= 1 and res["fn"] == n_issues


def mutate(st: Store, **change):
    f = oracle_findings(st, BAD)
    f[0] = {**f[0], **change}
    return f


@check("M01", "full correct answer with evidence, 10 steps -> 0.98")
def m01(st):
    r = run(st, BAD, oracle_findings(st, BAD))
    return r["r"] == Decimal("0.98") and r["fp"] == 0 and r["fn"] == 0, f"reward={r['reward']} tp={r['tp']}"


@check("M02", "silence on an erroneous book is strictly worse than M01 (about -1)")
def m02(st):
    r = run(st, BAD, [])
    return r["r"] < Decimal("0.98") and r["r"] <= Decimal("-0.9"), f"reward={r['reward']}"


@check("M03", "silence on a clean book -> 0.98")
def m03(st):
    r = run(st, CLEAN, [])
    return r["r"] == Decimal("0.98"), f"reward={r['reward']}"


@check("M04", "false accusation on a clean book is worse than silence, F1 = 0")
def m04(st):
    raw = st.raw(CLEAN)
    inv = raw["invoices"][0]
    f = [{"type": "duplicate_invoice", "affected_ids": sorted([inv["invoice_id"], raw["invoices"][1]["invoice_id"]]),
          "claimed_amount_minor": inv["total_minor"], "currency": inv["currency"], "evidence_ids": [inv["doc_id"]],
          "explanation": "looks similar"}]
    r = run(st, CLEAN, f)
    return r["r"] < Decimal("0.98") and Decimal(r["f1"]) == 0 and r["fp"] == 1, f"reward={r['reward']} f1={r['f1']}"


@check("M05", "correct answer plus its duplicate: FP +1 and lower reward")
def m05(st):
    good = oracle_findings(st, BAD)
    r = run(st, BAD, good + [dict(good[0])])
    base = run(st, BAD, good)
    return r["fp"] == 1 and r["tp"] == base["tp"] and r["r"] < base["r"], f"{r['reward']} < {base['reward']}"


@check("M06", "'flag everything' (30 findings) gives a negative reward")
def m06(st):
    res = run_policy(FlagAllPolicy(), st.root(BAD))
    return res.reward < 0 and res.evaluation["fp"] >= 10, f"reward={res.reward} fp={res.evaluation['fp']}"


@check("M07", "wrong type -> FP + FN")
def m07(st):
    t = st.truth(BAD)["issues"][0]["type"]
    r = run(st, BAD, mutate(st, type=OTHER_TYPE[t]))
    return fp_fn(r), f"tp={r['tp']} fp={r['fp']} fn={r['fn']}"


@check("M08", "amount off by one minor unit -> FP + FN (tolerance 0)")
def m08(st):
    amt = st.truth(BAD)["issues"][0]["expected_amount_minor"]
    a, b = run(st, BAD, mutate(st, claimed_amount_minor=amt + 1)), run(st, BAD, mutate(st, claimed_amount_minor=amt - 1))
    return fp_fn(a) and fp_fn(b), f"+1: {a['tp']}/{a['fp']}/{a['fn']}  -1: {b['tp']}/{b['fp']}/{b['fn']}"


@check("M09", "foreign currency or lower-case code -> FP + FN")
def m09(st):
    ccy = st.truth(BAD)["issues"][0]["currency"]
    other = "USD" if ccy != "USD" else "EUR"
    a, b = run(st, BAD, mutate(st, currency=other)), run(st, BAD, mutate(st, currency=ccy.lower()))
    return fp_fn(a) and fp_fn(b), f"other={other} lower={ccy.lower()}"


@check("M10", "affected_ids subset or superset -> FP + FN")
def m10(st):
    ids = st.truth(BAD)["issues"][0]["affected_ids"]
    extra = st.raw(BAD)["payments"][0]["payment_id"]
    a, b = run(st, BAD, mutate(st, affected_ids=ids[:1])), run(st, BAD, mutate(st, affected_ids=ids + [extra]))
    return fp_fn(a) and fp_fn(b), "subset and superset rejected"


@check("M11", "no evidence or an incomplete evidence set -> FP + FN")
def m11(st):
    ev = st.truth(BAD)["issues"][0]["evidence_sets"][0]
    a, b = run(st, BAD, mutate(st, evidence_ids=[])), run(st, BAD, mutate(st, evidence_ids=ev[:-1]))
    return fp_fn(a) and fp_fn(b), "empty and incomplete evidence rejected"


@check("M12", "evidence superset: accepted when every id exists, FP if one does not")
def m12(st):
    ev = st.truth(BAD)["issues"][0]["evidence_sets"][0]
    spare = next(r["row_id"] for r in st.raw(BAD)["ledger"] if r["row_id"] not in ev)
    ok = run(st, BAD, mutate(st, evidence_ids=ev + [spare]))
    bad = run(st, BAD, mutate(st, evidence_ids=ev + ["ROW-ZZZZZZ"]))
    return ok["tp"] == 1 and fp_fn(bad), f"existing: tp={ok['tp']}  unknown id: tp={bad['tp']}"


@check("M13", "ID with a space or different case -> FP + FN")
def m13(st):
    ids = st.truth(BAD)["issues"][0]["affected_ids"]
    a = run(st, BAD, mutate(st, affected_ids=[ids[0] + " "] + ids[1:]))
    b = run(st, BAD, mutate(st, affected_ids=[ids[0].lower()] + ids[1:]))
    return fp_fn(a) and fp_fn(b), "exact string comparison"


@check("M14", "31 findings -> reward -1")
def m14(st):
    r = run(st, BAD, oracle_findings(st, BAD) * 31)
    return r["r"] == Decimal(-1) and r["structural_error"] == "TOO_MANY_FINDINGS", f"reward={r['reward']}"


@check("M15", "11 evidence ids -> reward -1")
def m15(st):
    r = run(st, BAD, mutate(st, evidence_ids=[f"ROW-{k:06d}" for k in range(11)]))
    return r["r"] == Decimal(-1) and r["structural_error"] == "TOO_MANY_EVIDENCE", f"reward={r['reward']}"


@check("M16", "explanation of 1001 code points -> -1 (1000 is accepted)")
def m16(st):
    over = run(st, BAD, mutate(st, explanation="é" * 1001))
    edge = run(st, BAD, mutate(st, explanation="é" * 1000))
    return over["r"] == Decimal(-1) and edge["tp"] == 1, f"1001 -> {over['reward']}, 1000 -> tp={edge['tp']}"


@check("M17", "amount as '100', true or 100.0 -> -1")
def m17(st):
    rs = [run(st, BAD, mutate(st, claimed_amount_minor=v)) for v in ("100", True, 100.0)]
    return all(r["r"] == Decimal(-1) and r["structural_error"] for r in rs), "string, bool and float rejected"


@check("M18", "second submit is an error and does not change the first reward")
def m18(st):
    env, _, _ = new_env(st, BAD)
    first = env.step(submit_action(st, BAD, oracle_findings(st, BAD)))
    before = env.evaluation_result()
    o, r, t, tr, info = env.step(submit_action(st, BAD, []))
    return (o["error"] or {}).get("code") == "EPISODE_DONE" and r == 0.0 and env.evaluation_result() == before \
        and first[1] > 0.9, "EPISODE_DONE, reward unchanged"


@check("M19", "the same answer at 10 and at 50 steps differs by exactly 0.08")
def m19(st):
    a = run(st, BAD, oracle_findings(st, BAD), 10)
    b = run(st, BAD, oracle_findings(st, BAD), 50)
    return a["r"] - b["r"] == Decimal("0.08"), f"{a['reward']} - {b['reward']}"


@check("M20", "ambiguous matching (2 findings <-> 2 issues, cross candidates): maximum matching, order independent")
def m20(st):
    def issue(k, evidence):
        return {"issue_id": f"iss_{k}", "type": "duplicate_invoice", "affected_ids": ["INV-A", "INV-B"],
                "expected_amount_minor": 5, "currency": "KZT", "evidence_sets": [evidence]}
    issues = [issue(1, ["DOC-1"]), issue(2, ["DOC-2"])]
    known = {"DOC-1", "DOC-2", "DOC-3", "INV-A", "INV-B"}

    def f(evidence):
        return {"type": "duplicate_invoice", "affected_ids": ["INV-B", "INV-A"], "claimed_amount_minor": 5,
                "currency": "KZT", "evidence_ids": evidence, "explanation": ""}
    findings = [f(["DOC-1", "DOC-2"]), f(["DOC-1"]), f(["DOC-3"])]   # the first matches both issues
    outcomes = {(m["tp"], m["fp"], m["fn"], tuple(m["matched"])) for p in itertools.permutations(findings[:2])
                for m in [match(list(p), issues, known)]}
    three = {match(list(p), issues, known)["tp"] for p in itertools.permutations(findings)}
    return len(outcomes) == 1 and next(iter(outcomes))[0] == 2 and three == {2}, f"outcomes={len(outcomes)} tp={three}"
