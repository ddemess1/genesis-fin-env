"""17 'mutant caught' tests: break an episode by hand, exactly this invariant must fail."""
from dataclasses import replace

import pytest

from conftest import make_ctx, retarget
from fin_env.books.state import EvidenceSet, Invoice, LedgerRow
from fin_env.selfcheck import invariants as inv

BASE_ONLY = {"n_misc": 0, "n_invoices": 8, "twins": {"TWIN_SUBSCRIPTION": 1}}


def test_untouched_episode_passes_everything(ctx):
    failed = [(f.__name__, f(ctx).detail) for f in inv.EPISODE_CHECKS if not f(ctx).passed]
    assert failed == []


def _first_error_ledger_row(ctx):
    for r in ctx.errors:
        for op in r.diff:
            if op.table == "ledger" and op.op == "add":
                return ctx.id_map[op.iid]
    raise AssertionError("no added ledger row")


def test_i01_unbalanced_book(ctx):
    pid = _first_error_ledger_row(ctx)
    ctx.raw["ledger"] = [r for r in ctx.raw["ledger"] if r["row_id"] != pid]
    assert not inv.i01(retarget(ctx)).passed


def test_i02_ar_amount_differs_from_invoice(ctx):
    rows = list(ctx.clean.ledger)
    k = next(i for i, r in enumerate(rows) if r.account == "1200" and r.payment_iid is None and r.invoice_iid)
    rows[k] = replace(rows[k], debit_minor=rows[k].debit_minor + 1)
    ctx.clean = replace(ctx.clean, ledger=tuple(rows))
    assert not inv.i02(ctx).passed


def test_i03_suspense_in_clean_book(ctx):
    extra = LedgerRow("r9999", "2026-10-05T10:00:00+05:00", "2900", 0, 5, "KZT", None, None, None)
    ctx.clean = replace(ctx.clean, ledger=ctx.clean.ledger + (extra,))
    assert not inv.i03(ctx).passed


def test_i04_duplicate_in_clean_book(ctx):
    src = ctx.clean.invoices[0]
    ctx.clean = replace(ctx.clean, invoices=ctx.clean.invoices + (replace(src, iid="i9999", doc_iid="d9999"),))
    assert not inv.i04(ctx).passed


def test_i05_posted_in_other_period(ctx):
    rows = list(ctx.clean.ledger)
    k = next(i for i, r in enumerate(rows) if r.account == "1200" and r.payment_iid is None and r.invoice_iid)
    rows[k] = replace(rows[k], timestamp="2026-11-02T10:00:00+05:00")
    ctx.clean = replace(ctx.clean, ledger=tuple(rows))
    assert not inv.i05(ctx).passed


def test_i06_fx_rounding_off_by_one(ctx):
    rows = list(ctx.clean.ledger)
    foreign = {p.iid for p in ctx.clean.payments if p.currency != ctx.clean.base}
    k = next(i for i, r in enumerate(rows) if r.payment_iid in foreign and r.account == "1000")
    rows[k] = replace(rows[k], debit_minor=rows[k].debit_minor + 1)
    ctx.clean = replace(ctx.clean, ledger=tuple(rows))
    assert not inv.i06(ctx).passed


def test_i07_detect_differs_from_expected(ctx):
    ctx.recs = [replace(r, expected_amount_minor=r.expected_amount_minor + 1) if r is ctx.errors[0] else r
                for r in ctx.recs]
    assert not inv.i07(ctx).passed


def test_i08_evidence_not_reachable(ctx):
    first = ctx.errors[0]
    victim = first.evidence_sets[0].members[0]
    ctx.id_map = {**ctx.id_map, victim: "DOC-ZZZZZZ"}
    assert not inv.i08(ctx).passed


def test_i09_evidence_insufficient(ctx):
    first = ctx.errors[0]
    cut = replace(first, evidence_sets=(EvidenceSet(first.evidence_sets[0].members[:1]),))
    ctx.recs = [cut if r is first else r for r in ctx.recs]
    assert not inv.i09(ctx).passed


def test_i10_truth_has_indistinguishable_issues(ctx):
    issues = ctx.truth["issues"]
    ctx.truth = {"episode_id": ctx.truth["episode_id"], "issues": issues + [dict(issues[0], issue_id="iss_99")]}
    assert not inv.i10(ctx).passed


def test_i11_look_alike_is_a_real_error(ctx):
    twin = next(r for r in ctx.twins if r.kind == "TWIN_SUBSCRIPTION")
    clone = ctx.id_map[twin.affected_iids[1]]
    orig = ctx.id_map[twin.affected_iids[0]]
    sp = next(i for i in ctx.raw["invoices"] if i["invoice_id"] == orig)["line_items"][0]["service_period"]
    for i in ctx.raw["invoices"]:
        if i["invoice_id"] == clone:
            for li in i["line_items"]:
                li["service_period"] = sp
    assert not inv.i11(retarget(ctx)).passed


def test_i12_change_outside_diff(ctx):
    touched = {ctx.id_map.get(op.iid, op.iid) for r in ctx.recs for op in r.diff}
    row = next(r for r in ctx.raw["ledger"] if r["row_id"] not in touched and r["account"] == "6100")
    row["debit_minor"] += 7
    assert not inv.i12(retarget(ctx)).passed


def test_i13_bad_rate_format(ctx):
    ctx.raw["fx"][0]["rate"] = "1e3"
    assert not inv.i13(ctx).passed


def test_i14_manifest_counts_wrong(ctx):
    ctx.raw["manifest"]["counts"]["ledger"] += 1
    assert not inv.i14(ctx).passed


def test_i15_due_before_issue(ctx):
    ctx.raw["invoices"][0]["due_at"] = "2000-01-01T00:00:00+05:00"
    assert not inv.i15(retarget(ctx)).passed


def test_i16_leak_in_public_file(ctx):
    p = ctx.public_dir / "policy.json"
    p.write_text(p.read_text(encoding="utf-8") + " truth", encoding="utf-8")
    assert not inv.i16(ctx).passed


def test_i17_size_limits(tmp_path):
    small, _ = make_ctx(tmp_path, BASE_ONLY)
    assert not inv.i17(small).passed
