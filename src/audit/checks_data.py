"""D01-D20: data and ground-truth checks on the 20 audit episodes.

Every D-check = module B passed (sealed/selfcheck.json, 17/17) + an INDEPENDENT global scan of the
public files reproduces exactly the truth + the oracle gets the maximum + group-specific conditions.
"""
from __future__ import annotations

from decimal import Decimal

from fin_env import canon
from fin_env.books.state import FxIndex
from fin_env.money import convert, parse_rate
from fin_env.policies.oracle import OraclePolicy
from fin_env.runner import run_policy
from fin_env.selfcheck.detectors import scan_book
from fin_env.serialize import load_public_state
from fin_env.timeutil import local_date, period_of

from .common import Store

CHECKS: dict = {}
TITLES = {
    "D01": "clean book + subscription look-alike", "D02": "clean book + split-payment look-alike",
    "D03": "clean book + refund look-alike", "D04": "clean book + weekend-FX look-alike",
    "D05": "clean book + timezone-boundary look-alike", "D06": "1 duplicate invoice + subscription look-alike",
    "D07": "2 duplicate invoices + look-alike", "D08": "3 duplicate invoices, other base currency",
    "D09": "missing allocation", "D10": "partial allocation", "D11": "missing + partial + split-payment look-alike",
    "D12": "wrong FX date", "D13": "wrong FX rate + weekend look-alike", "D14": "period cutoff, tz +05:00",
    "D15": "period cutoff, tz -04:00", "D16": "INT1 (partial payment in foreign currency at the boundary)",
    "D17": "INT1, other base currency", "D18": "2 x INT1", "D19": "INT1 + 2 x INT2 + background errors up to 12",
    "D20": "INT1 x2 + INT2 + background errors",
}
WANTED_TWIN = {"D01": "TWIN_SUBSCRIPTION", "D02": "TWIN_SPLIT_PAYMENT", "D03": "TWIN_REFUND",
               "D04": "TWIN_WEEKEND_FX", "D05": "TWIN_BOUNDARY_TZ"}


def prov_of(st: Store, dk: str) -> dict:
    return canon.read_json(st.root(dk) / "sealed" / "provenance.json")


def kinds(prov: dict) -> list[str]:
    return [m["kind"] for m in prov["mutations"]]


def common(st: Store, dk: str) -> tuple[bool, str]:
    root = st.root(dk)
    sc = canon.read_json(root / "sealed" / "selfcheck.json")
    sc_ok = sc["ok"] and len(sc["results"]) == 17 and all(r["passed"] for r in sc["results"])
    truth = st.truth(dk)
    found = scan_book(load_public_state(root / "public"))
    want = sorted((i["type"], tuple(i["affected_ids"]), i["expected_amount_minor"]) for i in truth["issues"])
    scan_ok = found == want
    res = run_policy(OraclePolicy(root / "sealed"), root, seed=st.seed(dk), check_leaks=True)
    oracle_ok = Decimal(res.evaluation["f1"]) == 1 and res.evaluation["fp"] == 0
    return sc_ok and scan_ok and oracle_ok, f"selfcheck={'17/17' if sc_ok else 'FAIL'} scan==truth:{scan_ok} " \
        f"oracle F1={res.evaluation['f1']} reward={res.reward}"


def _clean(st, dk):
    prov, truth = prov_of(st, dk), st.truth(dk)
    ks = kinds(prov)
    twins = [k for k in ks if k.startswith("TWIN_")]
    ok = truth["issues"] == [] and len(twins) >= 3 and WANTED_TWIN[dk] in ks and all(
        not m["is_error"] for m in prov["mutations"])
    return ok, f"truth empty, look-alikes={twins}"


def _dups(st, dk):
    prov, truth = prov_of(st, dk), st.truth(dk)
    n = st.entry(dk)["config"]["errors"]["DUPLICATE_INVOICE"]
    ks = kinds(prov)
    types = [i["type"] for i in truth["issues"]]
    ok = ks.count("DUPLICATE_INVOICE") == n >= 1 and "TWIN_SUBSCRIPTION" in ks and types == ["duplicate_invoice"] * n
    twin = [m for m in prov["mutations"] if m["kind"] == "TWIN_SUBSCRIPTION"][0]
    twin_ids = sorted(prov["id_map"][x] for x in twin["affected_iids"])
    ok = ok and all(i["affected_ids"] != twin_ids for i in truth["issues"])
    return ok, f"{n} duplicates in truth, subscription look-alike present and absent from truth"


def _alloc(st, dk):
    prov, truth, raw = prov_of(st, dk), st.truth(dk), st.raw(dk)
    pays = {p["payment_id"]: p for p in raw["payments"]}
    for i in truth["issues"]:
        pay = pays[next(x for x in i["affected_ids"] if x in pays)]
        ref = pay["invoice_refs"][0]["amount_minor"]
        if i["currency"] != pay["currency"] or not 0 < i["expected_amount_minor"] <= ref:
            return False, "amount/currency not in payment terms"
    want = {"D09": {"MISSING_ALLOCATION"}, "D10": {"PARTIAL_ALLOCATION"},
            "D11": {"MISSING_ALLOCATION", "PARTIAL_ALLOCATION", "TWIN_SPLIT_PAYMENT"}}[dk]
    return want <= set(kinds(prov)), f"kinds={sorted(set(kinds(prov)))}"


def _fx(st, dk):
    truth, raw = st.truth(dk), st.raw(dk)
    base, tz = raw["manifest"]["base_currency"], raw["manifest"]["timezone"]
    rates = FxIndex([__import__("fin_env.books.state", fromlist=["FxRate"]).FxRate(
        r["date"], r["source_currency"], r["target_currency"], parse_rate(r["rate"])) for r in raw["fx"]])
    pays = {p["payment_id"]: p for p in raw["payments"]}
    cash = {}
    for r in raw["ledger"]:
        if r["account"] == "1000" and r["payment_id"]:
            cash[r["payment_id"]] = cash.get(r["payment_id"], 0) + r["debit_minor"] - r["credit_minor"]
    for i in truth["issues"]:
        p = pays[i["affected_ids"][0]]
        exp = convert(abs(p["amount_minor"]), p["currency"], base,
                      rates.lookup(p["currency"], base, local_date(p["timestamp"], tz).isoformat()).rate)
        if i["currency"] != base or abs(abs(cash[p["payment_id"]]) - exp) != i["expected_amount_minor"]:
            return False, "amount differs from the policy recomputation"
    return len(truth["issues"]) >= 1, f"{len(truth['issues'])} fx issues recomputed from raw rows by policy"


def _period(st, dk):
    prov, truth, raw = prov_of(st, dk), st.truth(dk), st.raw(dk)
    tz, cur = raw["manifest"]["timezone"], raw["manifest"]["period_start"][:7]
    invs = {i["invoice_id"]: i for i in raw["invoices"]}
    for i in truth["issues"]:
        inv = invs[i["affected_ids"][0]]
        if period_of(inv["issued_at"], tz) == cur:
            return False, "cutoff invoice is inside the period"
    twin = [invs[prov["id_map"][m["affected_iids"][0]]] for m in prov["mutations"] if m["kind"] == "TWIN_BOUNDARY_TZ"]
    ok = twin and all(period_of(t["issued_at"], tz) == cur and t["issued_at"][:7] != cur for t in twin)
    return bool(ok) and len(truth["issues"]) >= 1, f"tz={tz}: look-alike looks like next month by eye, is in-period by manifest tz"


def _interaction(st, dk):
    prov, truth = prov_of(st, dk), st.truth(dk)
    groups: dict[str, list[dict]] = {}
    for m in prov["mutations"]:
        if m["group_id"]:
            groups.setdefault(m["group_id"], []).append(m)
    cfg = st.entry(dk)["config"]["interactions"]
    by_id = {i["mutation_id"]: i for i in truth["issues"]}
    ok = len(groups) == sum(cfg.values()) and all(
        len(g) == 2 and all(x["mutation_id"] in by_id and x["is_error"] for x in g) for g in groups.values())
    ok = ok and all(by_id[x["mutation_id"]]["expected_amount_minor"] == x["expected_amount_minor"]
                    for g in groups.values() for x in g)
    return ok, f"{len(groups)} interacting groups, both issues of each in truth with their own sums"


SPECIFIC = {**{k: _clean for k in ("D01", "D02", "D03", "D04", "D05")},
            **{k: _dups for k in ("D06", "D07", "D08")}, **{k: _alloc for k in ("D09", "D10", "D11")},
            **{k: _fx for k in ("D12", "D13")}, **{k: _period for k in ("D14", "D15")},
            **{k: _interaction for k in ("D16", "D17", "D18", "D19", "D20")}}


def _make(dk: str):
    def run(st: Store):
        ok1, d1 = common(st, dk)
        ok2, d2 = SPECIFIC[dk](st, dk)
        return ok1 and ok2, f"{d1}; {d2}"
    return run


for _dk, _title in TITLES.items():
    CHECKS[_dk] = (_title, _make(_dk))
