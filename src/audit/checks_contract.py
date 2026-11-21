"""C01-C20: contract and isolation checks (our reading of the published jury block)."""
from __future__ import annotations

import json
import random
import tempfile
import time
from pathlib import Path

from fin_env import canon, publicio
from fin_env.generator import generate_episode
from fin_env.leak import find_leaks, seed_tokens
from fin_env.policies.oracle import OraclePolicy
from fin_env.runner import run_policy

from .common import Store, calc_step, new_env, oracle_findings, submit_action

CHECKS: dict = {}
EP, CLEAN = "D06", "D01"
TABLES = ("ledger", "invoices", "payments", "fx")
_ID = {"ledger": "row_id", "invoices": "invoice_id", "payments": "payment_id", "fx": "key"}


def check(cid: str, title: str):
    def deco(fn):
        CHECKS[cid] = (title, fn)
        return fn
    return deco


def page_all(env, table: str, limit: int = 50):
    rows, pages, cursor = [], [], None
    while True:
        obs = env.step({"action": "list_records", "table": table, "cursor": cursor, "limit": limit})[0]
        if obs["error"]:
            return rows, pages, obs["error"]["code"]
        res = obs["result"]
        pages.append(len(res["records"]))
        rows += res["records"]
        cursor = res["next_cursor"]
        if cursor is None:
            return rows, pages, None


@check("C01", "reset returns JSON-serialisable (obs, info)")
def c01(st: Store):
    env, obs, info = new_env(st, EP)
    json.dumps(obs), json.dumps(info)
    return isinstance(obs, dict) and isinstance(info, dict), "obs and info dumped with json.dumps"


@check("C02", "first observation: task, manifest, policy, steps_left=100; no seed/truth")
def c02(st: Store):
    _, obs, _ = new_env(st, EP)
    keys_ok = set(obs) == {"task", "manifest", "policy", "steps_left"} and obs["steps_left"] == 100
    leaks = find_leaks(json.dumps(obs), st.tokens(EP))
    return keys_ok and not leaks, f"keys={sorted(obs)} leaks={leaks}"


@check("C03", "manifest counts equal table lengths")
def c03(st: Store):
    env, obs, _ = new_env(st, EP)
    counts = obs["manifest"]["counts"]
    got = {}
    for t in TABLES:
        rows, _, err = page_all(env, t)
        got[t] = len(rows)
    ok = all(counts[t] == got[t] for t in TABLES) and counts["documents"] == got["invoices"] + got["payments"]
    return ok, f"manifest={counts} paged={got}"


@check("C04", "page limit: limit=51 is BAD_ARGS (step spent), limit=50 returns <= 50 rows")
def c04(st: Store):
    env, _, _ = new_env(st, EP)
    o51 = env.step({"action": "list_records", "table": "ledger", "limit": 51})[0]
    o50 = env.step({"action": "list_records", "table": "ledger", "limit": 50})[0]
    ok = (o51["error"] or {}).get("code") == "BAD_ARGS" and o51["steps_left"] == 99 and \
        o50["error"] is None and len(o50["result"]["records"]) <= 50
    return ok, "rule documented in README: limit > 50 -> BAD_ARGS, never silent truncation"


@check("C05", "cursor traversal returns every row once, in file order")
def c05(st: Store):
    env, _, _ = new_env(st, EP)
    raw = st.raw(EP)
    for t in TABLES:
        rows, pages, err = page_all(env, t)
        ids = [r["id"] if t == "fx" else r[_ID[t]] for r in rows]
        want = [r["key"] if t == "fx" else r[_ID[t]] for r in raw[t]]
        if err or ids != want or len(set(ids)) != len(ids) or max(pages or [0]) > 50:
            return False, f"table {t}: mismatch"
    return True, "4 tables, no gaps, no repeats"


@check("C06", "same cursor twice gives an identical page (also in a fresh reset)")
def c06(st: Store):
    env, _, _ = new_env(st, EP)
    first = env.step({"action": "list_records", "table": "ledger", "limit": 20})[0]["result"]
    cur = first["next_cursor"]
    a = env.step({"action": "list_records", "table": "ledger", "cursor": cur, "limit": 20})[0]["result"]
    b = env.step({"action": "list_records", "table": "ledger", "cursor": cur, "limit": 20})[0]["result"]
    env2, _, _ = new_env(st, EP)
    c = env2.step({"action": "list_records", "table": "ledger", "cursor": cur, "limit": 20})[0]["result"]
    forged = env.step({"action": "list_records", "table": "ledger", "cursor": "c000001000000000000"})[0]["error"]
    return a == b == c and forged is not None, "cursor is an opaque HMAC token of (table, offset)"


@check("C07", "get_record returns the row from the file")
def c07(st: Store):
    env, _, _ = new_env(st, EP)
    raw = st.raw(EP)
    for t in TABLES:
        for row in (raw[t][0], raw[t][-1]):
            ident = row["key"] if t == "fx" else row[_ID[t]]
            rec = env.step({"action": "get_record", "table": t, "id": ident})[0]["result"]["record"]
            expect = {"id": ident, **{k: v for k, v in row.items() if k != "key"}} if t == "fx" else row
            if rec != expect:
                return False, f"{t} {ident}"
    return True, "8 records compared"


@check("C08", "get_document returns the jsonl row")
def c08(st: Store):
    env, _, _ = new_env(st, EP)
    raw = st.raw(EP)
    for row in raw["invoices"][:5] + raw["payments"][:5]:
        doc = env.step({"action": "get_document", "doc_id": row["doc_id"]})[0]["result"]["document"]
        if doc != row:
            return False, row["doc_id"]
    return True, "10 documents compared"


@check("C09", "calculator: 0.1+0.2 = 0.3 (decimal arithmetic)")
def c09(st: Store):
    env, _, _ = new_env(st, EP)
    v = calc_step(env, "0.1+0.2")[0]["result"]["value"]
    w = calc_step(env, "(125000000 - 1) / 4")[0]["result"]["value"]
    return v == "0.3" and w == "31249999.75", f"0.1+0.2={v}"


@check("C10", "calculator rejects code, files and huge powers; the step is spent")
def c10(st: Store):
    env, _, _ = new_env(st, EP)
    bad = ("__import__('os')", "open('x')", "2**10**10", "9" * 31, "1+" * 120, "lambda: 1", "[1]")
    for k, e in enumerate(bad, 1):
        o = calc_step(env, e)[0]
        if (o["error"] or {}).get("code") != "CALC_ERROR" or o["steps_left"] != 100 - k:
            return False, e[:20]
    return True, f"{len(bad)} rejected"


@check("C11", "unknown id -> UNKNOWN_ID, step spent")
def c11(st: Store):
    env, _, _ = new_env(st, EP)
    calls = [{"action": "get_record", "table": t, "id": "NOPE-000000"} for t in TABLES]
    calls.append({"action": "get_document", "doc_id": "DOC-NOPE00"})
    for k, a in enumerate(calls, 1):
        o = env.step(a)[0]
        if (o["error"] or {}).get("code") != "UNKNOWN_ID" or o["steps_left"] != 100 - k:
            return False, str(a)
    return True, f"{len(calls)} lookups"


@check("C12", "unknown action -> BAD_ACTION, step spent")
def c12(st: Store):
    env, _, _ = new_env(st, EP)
    for k, a in enumerate(({"action": "bash"}, {"action": ""}, {"nothing": 1}, None, 7, ["list_records"]), 1):
        o = env.step(a)[0]
        if (o["error"] or {}).get("code") != "BAD_ACTION" or o["steps_left"] != 100 - k:
            return False, repr(a)
    return True, "6 malformed actions"


@check("C13", "wrong argument types -> BAD_ARGS, step spent")
def c13(st: Store):
    env, _, _ = new_env(st, EP)
    bad = [{"action": "list_records", "table": 5}, {"action": "list_records", "table": "ledger", "limit": "a"},
           {"action": "list_records", "table": "ledger", "limit": 0}, {"action": "get_record", "table": "ledger"},
           {"action": "get_record", "table": "ledger", "id": 5}, {"action": "get_document", "doc_id": None},
           {"action": "calculator", "expression": 5}, {"action": "list_records", "table": "ledger", "extra": 1}]
    for k, a in enumerate(bad, 1):
        o = env.step(a)[0]
        if (o["error"] or {}).get("code") != "BAD_ARGS" or o["steps_left"] != 100 - k:
            return False, str(a)
    return True, f"{len(bad)} bad calls"


@check("C14", "200 random junk actions: no exception, no traceback or path in any observation")
def c14(st: Store):
    env, _, _ = new_env(st, EP)
    rnd = random.Random(14)
    junk = [None, 1, 2.5, "x", [], {}, {"action": 5}, {"action": "list_records"}, {"action": "calculator", "expression": "9" * 500},
            {"action": "get_record", "table": "../..", "id": "C:\\Windows"}, {"action": "get_document", "doc_id": "/etc/passwd"},
            {"action": "submit"}, {"action": "list_records", "table": "ledger", "cursor": {"a": 1}},
            {"action": "get_record", "table": "ledger", "id": "x" * 10000}]
    for _ in range(200):
        try:
            o, r, t, tr, info = env.step(rnd.choice(junk))
        except Exception as exc:  # noqa: BLE001
            return False, f"exception {type(exc).__name__}"
        text = json.dumps(o) + json.dumps(info)
        if any(s in text for s in ("Traceback", "File \"", "C:\\", "/home", "/etc")):
            return False, "path or traceback in observation"
        if t or tr:
            break
    return True, "no crash"


@check("C15", "submit ends the episode (terminated=True); later steps are EPISODE_DONE")
def c15(st: Store):
    env, _, _ = new_env(st, EP)
    o, r, t, tr, _ = env.step(submit_action(st, EP, oracle_findings(st, EP)))
    o2, r2, t2, _, _ = calc_step(env)
    return t and not tr and (o2["error"] or {}).get("code") == "EPISODE_DONE" and r2 == 0.0, "terminated, then EPISODE_DONE"


@check("C16", "submit on step 100 (after 99 inspections) is accepted")
def c16(st: Store):
    env, _, _ = new_env(st, EP)
    for _ in range(99):
        calc_step(env)
    o, r, t, tr, info = env.step(submit_action(st, EP, oracle_findings(st, EP)))
    ev = env.evaluation_result()
    return t and not tr and ev["tp"] >= 1 and ev["inspection_steps"] == 99, f"tp={ev['tp']} steps={ev['inspection_steps']}"


@check("C17", "100 inspections without submit -> truncated=True and empty findings")
def c17(st: Store):
    env, _, _ = new_env(st, EP)
    for _ in range(100):
        o, r, t, tr, _ = calc_step(env)
    ev = env.evaluation_result()
    return tr and not t and ev["tp"] == 0 and ev["fp"] == 0, f"truncated={tr} tp={ev['tp']} fp={ev['fp']}"


@check("C18", "time limit: a policy that sleeps past the limit is truncated (61 s; --fast uses 2 s)")
def c18(st: Store):
    limit, nap = (2, 3) if st.fast else (60, 61)
    env, _, _ = new_env(st, EP, time_limit_s=limit)
    calc_step(env)
    time.sleep(nap)
    o, r, t, tr, _ = calc_step(env)
    return tr and not t, f"limit={limit}s slept={nap}s"


@check("C19", "closed mode: every reward is 0 and info == {steps_left}")
def c19(st: Store):
    env, _, _ = new_env(st, EP, mode="closed", evaluator="process")
    rewards, infos = [], []
    for _ in range(5):
        _, r, _, _, info = calc_step(env)
        rewards.append(r)
        infos.append(info)
    o, r, t, tr, info = env.step(submit_action(st, EP, oracle_findings(st, EP)))
    rewards.append(r)
    infos.append(info)
    ev = env.evaluation_result()
    env.close()
    env2, _, _ = new_env(st, EP, mode="closed")
    for _ in range(100):
        _, r2, _, tr2, info2 = calc_step(env2)
        rewards.append(r2)
        infos.append(info2)
    ok = all(x == 0.0 for x in rewards) and all(set(i) == {"steps_left"} for i in infos) and t and ev["tp"] >= 1 and tr2
    return ok, "oracle answer scored by the evaluator but invisible to the policy"


@check("C20", "no leaks in observations, infos, errors, trajectories, paths; traversal attempt fails")
def c20(st: Store):
    root = st.root(EP)
    res = run_policy(OraclePolicy(root / "sealed"), root, mode="open", check_leaks=False)
    env, _, _ = new_env(st, EP)
    probes = [env.step({"action": "get_document", "doc_id": "../sealed/truth.json"})[0],
              env.step({"action": "get_record", "table": "../sealed/truth", "id": "x"})[0],
              env.step({"action": "calculator", "expression": "open('sealed/truth.json')"})[0]]
    blobs = [canon.dumps(line) for line in res.trajectory] + [canon.dumps(p) for p in probes]
    leaks = []
    for b in blobs:
        leaks += find_leaks(b, st.tokens(EP))
        if str(root) in b or "episodes" in b:
            leaks.append("path")
    refused = all(p["error"] is not None and p["result"] is None for p in probes)
    # long-seed probe: a distinctive 12-digit seed must not show up anywhere in public files or trajectories
    probe_seed = 730284615029
    with tempfile.TemporaryDirectory(prefix="fin-c20-") as d:
        probe = generate_episode(probe_seed, {"errors": {"DUPLICATE_INVOICE": 1}, "twins": {"TWIN_SUBSCRIPTION": 1}},
                                 Path(d), split="audit")
        res2 = run_policy(OraclePolicy(probe / "sealed"), probe, mode="open", check_leaks=False)
        texts = [canon.dumps(line) for line in res2.trajectory] + [
            (probe / "public" / n).read_text(encoding="utf-8") for n in publicio.PUBLIC_FILES]
        for b in texts:
            leaks += find_leaks(b, seed_tokens(probe_seed))
    return not leaks and refused, f"{len(blobs) + len(texts)} blobs scanned, leaks={sorted(set(leaks))}"
