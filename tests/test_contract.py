"""Contract tests: reset/step, tools, limits, errors, closed mode, matcher, reward, canary."""
import json
import random
import time
from decimal import Decimal

import pytest

from fin_env import canon, publicio
from fin_env.env import FinAuditEnv
from fin_env.generator import generate_episode
from fin_env.leak import find_leaks
from fin_env.matcher import StructureError, match, validate_structure
from fin_env.reward import prf, terminal_reward

CFG = {"errors": {"DUPLICATE_INVOICE": 1}, "twins": {"TWIN_SUBSCRIPTION": 1}}


@pytest.fixture(scope="module")
def ep(tmp_path_factory):
    return generate_episode(4217, CFG, tmp_path_factory.mktemp("eps"))


@pytest.fixture(scope="module")
def clean_ep(tmp_path_factory):
    return generate_episode(4218, {"twins": {"TWIN_SUBSCRIPTION": 1, "TWIN_REFUND": 1, "TWIN_BOUNDARY_TZ": 1}},
                            tmp_path_factory.mktemp("eps2"))


def truth_of(root):
    return canon.read_json(root / "sealed" / "truth.json")


def good_finding(root, k=0):
    i = truth_of(root)["issues"][k]
    return {"type": i["type"], "affected_ids": list(reversed(i["affected_ids"])),
            "claimed_amount_minor": i["expected_amount_minor"], "currency": i["currency"],
            "evidence_ids": list(i["evidence_sets"][0]), "explanation": "recomputed"}


def mk(ep, mode="open", **extra):
    env = FinAuditEnv(evaluator_mode="inproc")
    obs, info = env.reset(None, {"episode_dir": str(ep), "mode": mode, **extra})
    return env, obs, info


def sub(root, findings):
    return {"action": "submit", "findings": {"episode_id": truth_of(root)["episode_id"], "findings": findings}}


def calc(env, expr="1+1"):
    return env.step({"action": "calculator", "expression": expr})


# ---- C01-C20 style checks -------------------------------------------------------------------
def test_first_observation(ep):
    env, obs, info = mk(ep)
    json.dumps(obs), json.dumps(info)
    assert set(obs) == {"task", "manifest", "policy", "steps_left"} and obs["steps_left"] == 100
    assert find_leaks(json.dumps(obs)) == []
    counts = obs["manifest"]["counts"]
    raw = publicio.load_raw(ep / "public")
    assert counts == {"ledger": len(raw["ledger"]), "invoices": len(raw["invoices"]),
                      "payments": len(raw["payments"]), "fx": len(raw["fx"]),
                      "documents": len(raw["invoices"]) + len(raw["payments"])}


def test_pagination_complete_and_stable(ep):
    env, obs, _ = mk(ep)
    total = obs["manifest"]["counts"]["ledger"]
    seen, cursor = [], None
    while True:
        o, *_ = env.step({"action": "list_records", "table": "ledger", "cursor": cursor, "limit": 50})
        res = o["result"]
        assert len(res["records"]) <= 50
        seen += [r["row_id"] for r in res["records"]]
        cursor = res["next_cursor"]
        if cursor is None:
            break
    raw = publicio.load_raw(ep / "public")
    assert seen == [r["row_id"] for r in raw["ledger"]] and len(set(seen)) == total
    c = env.step({"action": "list_records", "table": "ledger", "limit": 50})[0]["result"]["next_cursor"]
    a = env.step({"action": "list_records", "table": "ledger", "cursor": c, "limit": 50})[0]["result"]
    b = env.step({"action": "list_records", "table": "ledger", "cursor": c, "limit": 50})[0]["result"]
    assert a == b


def test_limit_51_is_error_and_costs_a_step(ep):
    env, _, _ = mk(ep)
    o, r, t, tr, info = env.step({"action": "list_records", "table": "ledger", "limit": 51})
    assert o["error"]["code"] == "BAD_ARGS" and o["steps_left"] == 99 and not t and not tr


def test_get_record_and_document(ep):
    env, _, _ = mk(ep)
    raw = publicio.load_raw(ep / "public")
    inv, pay, fx = raw["invoices"][0], raw["payments"][0], raw["fx"][0]
    assert env.step({"action": "get_record", "table": "invoices", "id": inv["invoice_id"]})[0]["result"]["record"] == inv
    assert env.step({"action": "get_document", "doc_id": pay["doc_id"]})[0]["result"]["document"] == pay
    assert env.step({"action": "get_record", "table": "fx", "id": fx["key"]})[0]["result"]["record"]["rate"] == fx["rate"]


def test_calculator(ep):
    env, _, _ = mk(ep)
    assert calc(env, "0.1+0.2")[0]["result"]["value"] == "0.3"
    assert calc(env, "(2+3)*4/8")[0]["result"]["value"] == "2.5"
    for bad in ("__import__('os')", "open('x')", "2**10**10", "1/0", "a+1", "", "1+" * 150):
        assert calc(env, bad)[0]["error"]["code"] == "CALC_ERROR", bad
    assert calc(env, 5)[0]["error"]["code"] == "BAD_ARGS"


def test_unknown_id_action_args_cost_steps(ep):
    env, _, _ = mk(ep)
    assert env.step({"action": "get_record", "table": "ledger", "id": "ROW-NOPE"})[0]["error"]["code"] == "UNKNOWN_ID"
    assert env.step({"action": "shell", "cmd": "ls"})[0]["error"]["code"] == "BAD_ACTION"
    assert env.step({"action": "get_record", "table": 5, "id": []})[0]["error"]["code"] == "BAD_ARGS"
    o = env.step({"action": "get_document", "doc_id": "../sealed/truth.json"})[0]
    assert o["error"]["code"] == "UNKNOWN_ID" and o["steps_left"] == 96


def test_fuzz_never_raises_and_never_leaks(ep):
    env, _, _ = mk(ep)
    rnd = random.Random(7)
    junk = [None, 1, "x", [], {}, {"action": 5}, {"action": "list_records"},
            {"action": "list_records", "table": "ledger", "limit": -1},
            {"action": "get_record", "table": "../..", "id": "C:\\x"}, {"action": "calculator", "expression": "9" * 500}]
    for _ in range(200):
        o, r, t, tr, info = env.step(rnd.choice(junk))
        assert find_leaks(json.dumps(o) + json.dumps(info)) == []
        if t or tr:
            break


def test_submit_terminates_then_errors(ep):
    env, _, _ = mk(ep)
    o, r, t, tr, info = env.step(sub(ep, [good_finding(ep)]))
    assert t and not tr and r == 1.0 and info["metrics"]["tp"] == 1
    o2, r2, t2, tr2, _ = env.step({"action": "calculator", "expression": "1+1"})
    assert o2["error"]["code"] == "EPISODE_DONE" and r2 == 0.0 and t2
    assert env.step(sub(ep, []))[1] == 0.0  # repeated submit does not change the first reward
    assert env.evaluation_result()["tp"] == 1


def test_submit_at_step_100_is_accepted(ep):
    env, _, _ = mk(ep)
    for _ in range(99):
        calc(env)
    o, r, t, tr, _ = env.step(sub(ep, [good_finding(ep)]))
    assert t and not tr and r == pytest.approx(1 - 0.198)


def test_100_inspections_truncate_with_empty_findings(ep, clean_ep):
    env, _, _ = mk(ep)
    for _ in range(100):
        o, r, t, tr, _ = calc(env)
    assert tr and not t and r == -1.0
    assert env.evaluation_result()["tp"] == 0 and env.evaluation_result()["fn"] == 1
    env2, _, _ = mk(clean_ep)
    for _ in range(100):
        o, r, t, tr, _ = calc(env2)
    assert tr and r == pytest.approx(0.8)  # empty answer on a clean book, but 100 steps were spent


def test_time_limit_truncates(ep):
    env, _, _ = mk(ep, time_limit_s=0.05)
    time.sleep(0.12)
    o, r, t, tr, _ = calc(env)
    assert tr and not t


def test_closed_mode_has_no_rewards_or_diagnostics(ep):
    env, _, _ = mk(ep, mode="closed")
    o, r, t, tr, info = env.step(sub(ep, [good_finding(ep)]))
    assert t and r == 0.0 and info == {"steps_left": 99}
    assert env.evaluation_result()["tp"] == 1  # available to the harness after the end


def test_process_evaluator_matches_inproc(ep):
    env = FinAuditEnv(evaluator_mode="process")
    env.reset(None, {"episode_dir": str(ep)})
    o, r, t, tr, info = env.step(sub(ep, [good_finding(ep)]))
    env.close()
    assert t and r == 1.0


def test_canary_never_reaches_observations(ep, tmp_path):
    import shutil
    root = tmp_path / "canary"
    shutil.copytree(ep, root)
    t = truth_of(root)
    t["issues"][0]["canary"] = "CANARY-7f3e"
    canon.write_json(root / "sealed" / "truth.json", t)
    prov = canon.read_json(root / "sealed" / "provenance.json")
    prov["canary"] = "CANARY-7f3e"
    canon.write_json(root / "sealed" / "provenance.json", prov)
    rnd = random.Random(1)
    raw = publicio.load_raw(root / "public")
    ids = sorted(publicio.known_ids(raw))
    steps = 0
    while steps < 1000:
        env, obs, _ = mk(root)
        assert "CANARY" not in json.dumps(obs)
        for _ in range(100):
            action = rnd.choice([
                {"action": "list_records", "table": rnd.choice(["ledger", "invoices", "payments", "fx", "x"]), "limit": 50},
                {"action": "get_record", "table": rnd.choice(["ledger", "invoices", "payments", "fx"]), "id": rnd.choice(ids)},
                {"action": "get_document", "doc_id": rnd.choice(ids)}, {"action": "get_document", "doc_id": "sealed/truth.json"},
                {"action": "calculator", "expression": "1+1"}, {"action": "nope"}])
            o, r, t, tr, info = env.step(action)
            steps += 1
            assert "CANARY" not in json.dumps(o) + json.dumps(info)
            if t or tr:
                break


# ---- matcher / reward ------------------------------------------------------------------------
ISSUE = {"issue_id": "iss_01", "type": "duplicate_invoice", "affected_ids": ["INV-AAAAAA", "INV-BBBBBB"],
         "expected_amount_minor": 125000000, "currency": "KZT", "amount_tolerance_minor": 0,
         "evidence_sets": [["DOC-AAAAAA", "DOC-BBBBBB"], ["DOC-AAAAAA", "ROW-000003"]]}
KNOWN = {"DOC-AAAAAA", "DOC-BBBBBB", "ROW-000003", "INV-AAAAAA", "INV-BBBBBB"}
GOOD = {"type": "duplicate_invoice", "affected_ids": ["INV-BBBBBB", "INV-AAAAAA"], "claimed_amount_minor": 125000000,
        "currency": "KZT", "evidence_ids": ["DOC-AAAAAA", "DOC-BBBBBB"], "explanation": "same entity, total, period"}


def variant(**kw):
    return {**GOOD, **kw}


def run(findings):
    return match(findings, [ISSUE], KNOWN)


def test_matcher_exactness():
    assert run([GOOD])["tp"] == 1
    for bad in (variant(type="fx_conversion"), variant(claimed_amount_minor=125000001), variant(currency="usd"),
                variant(currency="USD"), variant(affected_ids=["INV-AAAAAA"]),
                variant(affected_ids=["INV-AAAAAA", "INV-BBBBBB", "INV-X"]), variant(evidence_ids=[]),
                variant(evidence_ids=["DOC-AAAAAA"]),
                variant(evidence_ids=["DOC-AAAAAA", "DOC-BBBBBB", "DOC-ZZZZZZ"]),
                variant(affected_ids=["INV-AAAAAA ", "INV-BBBBBB"]),
                variant(affected_ids=["inv-aaaaaa", "INV-BBBBBB"])):
        m = run([bad])
        assert (m["tp"], m["fp"], m["fn"]) == (0, 1, 1), bad
    assert run([variant(evidence_ids=["DOC-AAAAAA", "DOC-BBBBBB", "ROW-000003"])])["tp"] == 1


def test_duplicates_are_fp_and_matching_is_maximum():
    m = run([GOOD, dict(GOOD)])
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 0)
    two = [dict(ISSUE, issue_id="a"), dict(ISSUE, issue_id="b", evidence_sets=[["DOC-AAAAAA"]])]
    f1, f2 = GOOD, variant(evidence_ids=["DOC-AAAAAA"])
    assert match([f1, f2], two, KNOWN)["tp"] == match([f2, f1], two, KNOWN)["tp"] == 2


def test_structure_violations():
    for bad in ([GOOD] * 31, [variant(evidence_ids=["DOC-AAAAAA"] * 11)], [variant(explanation="x" * 1001)],
                [variant(claimed_amount_minor="100")], [variant(claimed_amount_minor=True)],
                [variant(claimed_amount_minor=100.0)], [variant(affected_ids="INV-AAAAAA")], ["not a dict"],
                {"findings": "x"}, 5, {"episode_id": "other", "findings": []}):
        with pytest.raises(StructureError):
            validate_structure(bad, "ep_fixture")
    assert len(validate_structure([variant(explanation="é" * 1000)])) == 1  # code points, not bytes


def test_structure_violation_gives_minus_one(ep):
    env, _, _ = mk(ep)
    o, r, t, tr, info = env.step(sub(ep, [good_finding(ep)] * 31))
    assert t and r == -1.0


def test_reward_rules():
    assert terminal_reward(1, 0, 0, 10) == Decimal("0.98")
    assert terminal_reward(0, 0, 1, 10) == Decimal("-1")
    assert terminal_reward(0, 0, 0, 10) == Decimal("0.98")
    assert terminal_reward(0, 1, 0, 10) == Decimal("-1")
    assert terminal_reward(1, 1, 0, 10) < terminal_reward(1, 0, 0, 10)
    assert terminal_reward(0, 30, 12, 6) < 0
    assert terminal_reward(1, 0, 0, 10) - terminal_reward(1, 0, 0, 50) == Decimal("0.08")
    assert prf(0, 0, 0)[2] == 1 and prf(0, 3, 0)[2] == 0


# ---- jury-page conventions ------------------------------------------------------------------------
def test_affected_ids_are_a_set():
    assert run([variant(affected_ids=["INV-BBBBBB", "INV-AAAAAA", "INV-AAAAAA"])])["tp"] == 1


def test_submit_answers_accepted_and_structural_error_is_bounded(ep):
    env, _, _ = mk(ep)
    o, r, t, tr, _ = env.step(sub(ep, [good_finding(ep)]))
    assert o["result"] == {"accepted": True} and o["error"] is None
    env2, _, _ = mk(ep)
    o, r, t, tr, info = env2.step(sub(ep, [good_finding(ep)] * 31))
    assert t and r == -1.0 and o["error"]["code"] == "BAD_ARGS" and info["metrics"] is None


def test_judge_adapter_roundtrip(tmp_path):
    import judge_adapter as ja
    d = ja.generate_episode(77, {"errors": {"DUPLICATE_INVOICE": 1}, "twins": {"TWIN_SUBSCRIPTION": 1}}, tmp_path / "e")
    env = ja.make_env()
    obs, _ = env.reset(None, {"mode": "closed", "episode_dir": str(d), "team_config": {}})
    truth = canon.read_json(d / "sealed" / "truth.json")
    i = truth["issues"][0]
    f = [{"type": i["type"], "affected_ids": i["affected_ids"], "claimed_amount_minor": i["expected_amount_minor"],
          "currency": i["currency"], "evidence_ids": i["evidence_sets"][0], "explanation": "x"}]
    assert env.step({"action": "submit", "findings": {"episode_id": truth["episode_id"], "findings": f}})[1] == 0.0
    env.close()
    s = ja.score_episode(d, f, 10)
    assert s["reward"] == pytest.approx(0.98) and s["tp"] == 1
    bad = ja.score_episode(d, [f[0]] * 31, 0)
    assert bad["reward"] == -1.0 and bad["tp"] is None
    train = ja.make_env()
    train.reset(5, {"mode": "train", "team_config": {}, "cache_dir": str(tmp_path / "c")})
    train.close()
