"""Module B invariants I01-I17 (our implementation of the six D-conditions)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from .. import canon, leak, publicio
from ..books.state import ACCOUNTS, ISSUE_TYPES, BookState
from ..money import is_int
from ..mutations.truth import derive_truth  # truth is DERIVED here only to compare with the file
from ..serialize import state_to_raw
from ..timeutil import TS_RE, parse_ts, period_of
from ..tools import PublicTools
from . import detectors


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    d_condition: int | None
    detail: str
    refs: tuple[str, ...] = ()
    data: dict = field(default_factory=dict)


@dataclass
class Ctx:
    clean: BookState
    pub: BookState | None = None
    dirty_mem: BookState | None = None
    raw: dict | None = None
    recs: list = field(default_factory=list)
    truth: dict | None = None
    id_map: dict = field(default_factory=dict)
    public_dir: Path | None = None
    seed: int | None = None

    @property
    def errors(self):
        return [r for r in self.recs if r.is_error]

    @property
    def twins(self):
        return [r for r in self.recs if not r.is_error]

    def pa(self, rec):
        """public ids of a record's affected iids"""
        return tuple(self.id_map.get(x, x) for x in rec.affected_iids)


def _res(cid, ok, d, detail, refs=(), **data):
    return CheckResult(cid, bool(ok), d, detail, tuple(refs), data)


def _sums(s: BookState) -> tuple[int, int]:
    return sum(r.debit_minor for r in s.ledger), sum(r.credit_minor for r in s.ledger)


def _cur(s: BookState) -> str:
    return s.manifest["period_start"][:7]


# ---- I01-I06: clean book --------------------------------------------------------------
def i01(c: Ctx):
    dc, cc = _sums(c.clean)
    data = {"dr_clean": dc, "cr_clean": cc}
    ok = dc == cc
    if c.pub is not None:
        dd, cd = _sums(c.pub)
        data.update(dr_dirty=dd, cr_dirty=cd)
        ok = ok and dd == cd
    return _res("I01", ok, 1, f"sum Dr={data['dr_clean']} Cr={data['cr_clean']} (clean)"
                + (f", Dr={data['dr_dirty']} Cr={data['cr_dirty']} (dirty)" if c.pub is not None else ""), **data)


def i02(c: Ctx):
    s, bad = c.clean, []
    cur = _cur(s)
    for inv in s.invoices:
        rows = [r for r in s.rows_by_invoice.get(inv.iid, []) if r.payment_iid is None]
        if period_of(inv.issued_at, s.tz) == cur:
            exp = s.fx_index.convert_at(inv.total_minor, inv.currency, s.base,
                                        _day(inv.issued_at, s))
            dr = sum(r.debit_minor for r in rows if r.account == "1200")
            cr = sum(r.credit_minor for r in rows if r.account == "4000")
            if dr != exp or cr != exp:
                bad.append(inv.iid)
        elif rows:
            bad.append(inv.iid)
    return _res("I02", not bad, 1, f"{len(s.invoices)} invoices checked, {len(bad)} bad", bad)


def _day(ts: str, s: BookState) -> str:
    from ..timeutil import local_date
    return local_date(ts, s.tz).isoformat()


def i03(c: Ctx):
    s, bad = c.clean, []
    for p in s.payments:
        rows = s.rows_by_payment.get(p.iid, [])
        for ref in p.invoice_refs or ():
            exp = s.fx_index.convert_at(ref.amount_minor, p.currency, s.base, _day(p.timestamp, s))
            got = sum(r.credit_minor for r in rows if r.account == "1200" and r.invoice_iid == ref.invoice_iid)
            if got != exp:
                bad.append(p.iid)
    susp = [r.iid for r in s.ledger if r.account == "2900"]
    return _res("I03", not bad and not susp, 1, f"{len(s.payments)} payments, {len(bad)} bad, "
                f"2900 rows={len(susp)}", bad + susp)


def i04(c: Ctx):
    seen: dict[tuple, str] = {}
    dups = []
    for i in c.clean.invoices:
        key = (i.entity_iid, i.total_minor, i.currency, tuple(sorted(li.service_period for li in i.line_items)))
        if key in seen:
            dups.append(i.iid)
        seen[key] = i.iid
    return _res("I04", not dups, 1, f"{len(dups)} duplicate pairs in the clean book", dups)


def i05(c: Ctx):
    s, bad = c.clean, []
    cur = _cur(s)
    for r in s.ledger:
        doc_ts = None
        if r.payment_iid:
            doc_ts = s.pay_by_iid[r.payment_iid].timestamp
        elif r.invoice_iid:
            doc_ts = s.inv_by_iid[r.invoice_iid].issued_at
        if doc_ts is not None and (period_of(doc_ts, s.tz) == cur) != (period_of(r.timestamp, s.tz) == cur):
            bad.append(r.iid)
    return _res("I05", not bad, 1, f"{len(bad)} rows posted in a different period than their document", bad)


def i06(c: Ctx):
    s, bad = c.clean, []
    for r in s.ledger:
        if r.invoice_iid is None and r.payment_iid is None:
            continue
        if r.payment_iid:
            p = s.pay_by_iid[r.payment_iid]
            ccy, amt, ts = p.currency, p.invoice_refs[0].amount_minor, p.timestamp
        else:
            i = s.inv_by_iid[r.invoice_iid]
            ccy, amt, ts = i.currency, i.total_minor, i.issued_at
        if ccy != s.base and max(r.debit_minor, r.credit_minor) != s.fx_index.convert_at(amt, ccy, s.base, _day(ts, s)):
            bad.append(r.iid)
    return _res("I06", not bad, 1, f"{len(bad)} foreign-currency rows differ from round(amount*rate)", bad)


# ---- I07-I12: errors, evidence, twins, side effects -------------------------------------
def i07(c: Ctx):
    bad, rows = [], []
    for e in c.errors:
        d = detectors.detect(e.issue_type, c.pub, c.pa(e))
        k = detectors.detect(e.issue_type, c.clean, e.affected_iids)
        rows.append({"mutation_id": e.mutation_id, "detect_clean": k, "detect_dirty": d,
                     "expected": e.expected_amount_minor})
        if not (d == e.expected_amount_minor > 0 and k == 0):
            bad.append(e.mutation_id)
    return _res("I07", not bad, 2, "; ".join(f"{r['mutation_id']}: detect(clean)={r['detect_clean']}, "
                f"detect(dirty)={r['detect_dirty']}" for r in rows) or "no errors", bad, rows=rows)


def _call(tools: PublicTools, ident: str) -> bool:
    if ident.startswith("DOC-"):
        act = {"action": "get_document", "doc_id": ident}
    elif ident.startswith("ROW-"):
        act = {"action": "get_record", "table": "ledger", "id": ident}
    elif ident.startswith("FX:"):
        act = {"action": "get_record", "table": "fx", "id": ident}
    elif ident.startswith("INV-"):
        act = {"action": "get_record", "table": "invoices", "id": ident}
    else:
        act = {"action": "get_record", "table": "payments", "id": ident}
    return tools.dispatch(act)[1] is None


def i08(c: Ctx):
    tools = PublicTools(c.public_dir)
    bad = []
    for r in c.recs:
        for es in r.evidence_sets:
            if not all(_call(tools, c.id_map.get(x, x)) for x in es.members):
                bad.append(r.mutation_id)
    return _res("I08", not bad, 4, f"evidence reachable through env tools for {len(c.recs)} records", bad)


def _restrict(pub: BookState, members: set[str]) -> BookState:
    return BookState(tuple(r for r in pub.ledger if r.iid in members),
                     tuple(i for i in pub.invoices if i.doc_iid in members),
                     tuple(p for p in pub.payments if p.doc_iid in members),
                     tuple(f for f in pub.fx if f.key in members), pub.manifest, pub.policy)


def i09(c: Ctx):
    bad = []
    for e in c.errors:
        for es in e.evidence_sets:
            sub = _restrict(c.pub, {c.id_map.get(x, x) for x in es.members})
            if detectors.detect(e.issue_type, sub, c.pa(e)) != e.expected_amount_minor:
                bad.append(e.mutation_id)
    return _res("I09", not bad, 2, f"{sum(len(e.evidence_sets) for e in c.errors)} evidence sets recomputed "
                "from their own records only", sorted(set(bad)))


def i10(c: Ctx):
    t, bad = c.truth, []
    if t != derive_truth(c.recs, c.id_map, t["episode_id"]):
        bad.append("truth-differs-from-records")
    keys = [(i["type"], tuple(i["affected_ids"])) for i in t["issues"]]
    if len(set(keys)) != len(keys):
        bad.append("indistinguishable-issues")
    twin_sets = {tuple(sorted(c.pa(w))) for w in c.twins}
    for i in t["issues"]:
        if i["type"] not in ISSUE_TYPES or i["affected_ids"] != sorted(set(i["affected_ids"])):
            bad.append(i["issue_id"])
        if tuple(i["affected_ids"]) in twin_sets or not i["evidence_sets"] or i["expected_amount_minor"] <= 0:
            bad.append(i["issue_id"])
        if any(len(es) > 10 or len(es) == 0 for es in i["evidence_sets"]):
            bad.append(i["issue_id"])
    if len(t["issues"]) != len(c.errors):
        bad.append("count")
    return _res("I10", not bad, 3, f"{len(t['issues'])} issues derived from {len(c.errors)} error records", bad)


def i11(c: Ctx):
    bad = []
    for w in c.twins:
        feat = w.params.get("distinguishing_feature")
        if not isinstance(feat, str) or not feat:
            bad.append(w.mutation_id)
        for typ in w.params.get("against", []):
            if detectors.detect(typ, c.pub, c.pa(w)) != 0:
                bad.append(w.mutation_id)
    return _res("I11", not bad, 3, f"{len(c.twins)} look-alikes: every detector gives 0", sorted(set(bad)))


def _table_maps(raw: dict) -> dict:
    return {"ledger": {r["row_id"]: r for r in raw["ledger"]},
            "invoices": {r["invoice_id"]: r for r in raw["invoices"]},
            "payments": {r["payment_id"]: r for r in raw["payments"]},
            "fx": {(r["date"], r["source_currency"], r["target_currency"]):
                   {k: v for k, v in r.items() if k != "key"} for r in raw["fx"]}}


def i12(c: Ctx):
    a, b = _table_maps(state_to_raw(c.clean, c.id_map)), _table_maps(c.raw)
    touched = {(op.table, c.id_map.get(op.iid, op.iid)) for r in c.recs for op in r.diff}
    outside = 0
    for table in a:
        for key in set(a[table]) | set(b[table]):
            if a[table].get(key) != b[table].get(key) and (table, key) not in touched:
                outside += 1
    expected = sorted((e.issue_type, tuple(sorted(c.pa(e))), e.expected_amount_minor) for e in c.errors)
    found = detectors.scan_book(c.pub)
    ok = outside == 0 and found == expected
    return _res("I12", ok, 6, f"{outside} changes outside diff; global scan finds {len(found)} discrepancies "
                f"(expected {len(expected)})", [] if ok else ["scan" if found != expected else "diff"],
                outside_diff_changes=outside, scan_found=len(found))


# ---- I13-I17: format, consistency, leaks, sizes ---------------------------------------------
_RATE = re.compile(r"^\d+\.\d+$")


def i13(c: Ctx):
    raw, bad = c.raw, []
    m = raw["manifest"]
    for k in ("schema_version", "episode_id", "base_currency", "period_start", "period_end", "timezone",
              "rounding", "counts"):
        if k not in m:
            bad.append("manifest." + k)
    for r in raw["ledger"]:
        if not (is_int(r["debit_minor"]) and is_int(r["credit_minor"])) or not TS_RE.match(r["timestamp"]) \
                or r["account"] not in ACCOUNTS:
            bad.append(r["row_id"])
        for k in ("entity_id", "invoice_id", "payment_id"):
            if r[k] is not None and not isinstance(r[k], str):
                bad.append(r["row_id"])
    for i in raw["invoices"]:
        if not is_int(i["total_minor"]) or not TS_RE.match(i["issued_at"]) or not TS_RE.match(i["due_at"]):
            bad.append(i["invoice_id"])
        if i["total_minor"] != sum(li["qty"] * li["unit_minor"] for li in i["line_items"]):
            bad.append(i["invoice_id"])
    for p in raw["payments"]:
        refs = p["invoice_refs"]
        if not is_int(p["amount_minor"]) or not TS_RE.match(p["timestamp"]) or not (
                refs is None or all(is_int(r["amount_minor"]) for r in refs)):
            bad.append(p["payment_id"])
    for f in raw["fx"]:
        if not _RATE.match(f["rate"]):
            bad.append(f["key"])
    if c.dirty_mem is not None:
        mem = state_to_raw(c.dirty_mem, c.id_map)
        for t in ("ledger", "invoices", "payments", "fx"):
            if sorted(canon.dumps(x) for x in mem[t]) != sorted(canon.dumps({k: v for k, v in x.items() if k != "key"})
                                                                 for x in raw[t]):
                bad.append("roundtrip:" + t)
    return _res("I13", not bad, 5, f"schemas and disk round-trip checked, {len(bad)} problems", bad)


def i14(c: Ctx):
    raw, bad = c.raw, []
    m = raw["manifest"]["counts"]
    if m != {"ledger": len(raw["ledger"]), "invoices": len(raw["invoices"]), "payments": len(raw["payments"]),
             "fx": len(raw["fx"]), "documents": len(raw["invoices"]) + len(raw["payments"])}:
        bad.append("counts")
    ids = publicio.known_ids(raw)
    inv_ids = {i["invoice_id"] for i in raw["invoices"]}
    pay_ids = {p["payment_id"] for p in raw["payments"]}
    for r in raw["ledger"]:
        if (r["invoice_id"] and r["invoice_id"] not in inv_ids) or (r["payment_id"] and r["payment_id"] not in pay_ids):
            bad.append(r["row_id"])
    for p in raw["payments"]:
        for ref in p["invoice_refs"] or ():
            if ref["invoice_id"] not in inv_ids:
                bad.append(p["payment_id"])
    return _res("I14", not bad, 5, f"counts match, all references resolve ({len(ids)} ids)", bad)


def i15(c: Ctx):
    raw, s, bad = c.raw, c.pub, []
    ids = [r["row_id"] for r in raw["ledger"]] + [i["invoice_id"] for i in raw["invoices"]] + \
          [p["payment_id"] for p in raw["payments"]] + [i["doc_id"] for i in raw["invoices"]] + \
          [p["doc_id"] for p in raw["payments"]]
    if len(ids) != len(set(ids)):
        bad.append("duplicate-ids")
    for i in raw["invoices"]:
        if parse_ts(i["due_at"]) < parse_ts(i["issued_at"]):
            bad.append(i["invoice_id"])
    invs = {i["invoice_id"]: i for i in raw["invoices"]}
    for p in raw["payments"]:
        refs = p["invoice_refs"] or []
        if abs(sum(r["amount_minor"] for r in refs)) > abs(p["amount_minor"]):
            bad.append(p["payment_id"])
        if any(invs[r["invoice_id"]]["currency"] != p["currency"] for r in refs):
            bad.append(p["payment_id"])
        if p["currency"] != s.base:
            try:
                s.fx_index.lookup(p["currency"], s.base, _day(p["timestamp"], s))
            except KeyError:
                bad.append(p["payment_id"])
    for i in raw["invoices"]:
        if i["currency"] != s.base:
            try:
                s.fx_index.lookup(i["currency"], s.base, _day(i["issued_at"], s))
            except KeyError:
                bad.append(i["invoice_id"])
    for r in raw["ledger"]:
        if r["debit_minor"] < 0 or r["credit_minor"] < 0 or (r["debit_minor"] and r["credit_minor"]):
            bad.append(r["row_id"])
    return _res("I15", not bad, 6, f"ids unique, dates ordered, refs within amounts, rates available; "
                f"{len(bad)} contradictions", bad)


def i16(c: Ctx):
    tokens = leak.seed_tokens(c.seed) if c.seed is not None else ()
    hits = []
    for name in publicio.PUBLIC_FILES:
        text = (c.public_dir / name).read_text(encoding="utf-8")
        for h in leak.find_leaks(text, tokens):
            hits.append(f"{name}:{h}")
        words = set(re.findall(r"[A-Za-z0-9]+", text))
        if words & set(c.id_map):
            hits.append(f"{name}:iid")
    return _res("I16", not hits, None, f"{len(hits)} forbidden substrings in public files", hits)


def i17(c: Ctx):
    raw, bad = c.raw, []
    n_rows, n_docs = len(raw["ledger"]), len(raw["invoices"]) + len(raw["payments"])
    if not 200 <= n_rows <= 2000:
        bad.append(f"ledger={n_rows}")
    if not 20 <= n_docs <= 200:
        bad.append(f"documents={n_docs}")
    if len(c.errors) > 12 or len(c.truth["issues"]) > 30:
        bad.append("errors")
    if any(len(es) > 10 for i in c.truth["issues"] for es in i["evidence_sets"]):
        bad.append("evidence")
    if not c.errors and len(c.twins) < 3:
        bad.append("clean episode needs >= 3 look-alikes")
    return _res("I17", not bad, None, f"ledger={n_rows} documents={n_docs} errors={len(c.errors)} "
                f"look-alikes={len(c.twins)}", bad)


CLEAN_CHECKS = (i01, i02, i03, i04, i05, i06)
EPISODE_CHECKS = (i01, i02, i03, i04, i05, i06, i07, i08, i09, i10, i11, i12, i13, i14, i15, i16, i17)
