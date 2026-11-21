"""MISSING/PARTIAL_ALLOCATION (errors) and TWIN_SPLIT_PAYMENT / TWIN_TRUE_PARTIAL / TWIN_REFUND."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from ..books.posting import invoice_rows, payment_rows
from ..books.state import BookState, InvoiceRef, LedgerRow, Payment
from ..money import round_div
from ..rng import DetRng
from ..timeutil import fmt_ts, make_ts
from .base import (MutationSkip, Mutator, add_payments, add_rows, current_period, day_of, new_row_ids, op_add,
                   op_modify, period_bounds, record, replace_row)
from ..timeutil import period_of


def _clean_receipts(s: BookState) -> list[Payment]:
    """In-period single-ref positive payments whose ledger rows are intact (1200 credit, no 2900)."""
    cur = current_period(s)
    out = []
    for p in s.payments:
        if not p.invoice_refs or len(p.invoice_refs) != 1 or p.invoice_refs[0].amount_minor <= 0:
            continue
        if period_of(p.timestamp, s.tz) != cur:
            continue
        rows = s.rows_by_payment.get(p.iid, [])
        if any(r.account == "2900" for r in rows) or not any(r.account == "1200" and r.credit_minor > 0 for r in rows):
            continue
        out.append(p)
    return out


class _Allocation(Mutator):
    is_error = True
    issue_type = "payment_allocation"

    def eligible(self, s):
        return sorted((p.iid,) for p in _clean_receipts(s) if p.invoice_refs[0].amount_minor >= 1000)

    def _ar_row(self, s, pid: str) -> LedgerRow:
        return next(r for r in s.rows_by_payment[pid] if r.account == "1200" and r.credit_minor > 0)


class MissingAllocation(_Allocation):
    kind = "MISSING_ALLOCATION"

    def apply(self, s, target, rng: DetRng):
        pay = s.pay_by_iid[target[0]]
        ref = pay.invoice_refs[0]
        ar = self._ar_row(s, pay.iid)
        after = replace(ar, account="2900")
        s2 = replace_row(s, ar.iid, account="2900")
        rec = record(self.kind, True, self.issue_type, {"allocated_share_pct": 0}, target,
                     [op_modify(ar, after)], (ref.invoice_iid, pay.iid), ref.amount_minor, pay.currency,
                     [(pay.doc_iid, ar.iid)])
        return s2, rec


class PartialAllocation(_Allocation):
    kind = "PARTIAL_ALLOCATION"

    def apply(self, s, target, rng: DetRng):
        pay = s.pay_by_iid[target[0]]
        ref = pay.invoice_refs[0]
        ar = self._ar_row(s, pay.iid)
        pct = rng.randint(30, 80)
        day = day_of(pay.timestamp, s).isoformat()
        start = ref.amount_minor * pct // 100
        # The unallocated part must be recoverable from the ledger (round(A * 2900 / (1200 + 2900))).
        # For currencies worth < 1 base minor unit the base amounts are coarse, so nudge the split
        # to the nearest value for which the round trip is exact.
        for nudge in (0, 1, -1, 2, -2, 3, -3, 5, -5, 8, -8, 13, -13, 21, -21, 34, -34, 55, -55):
            alloc = start + nudge
            if not 0 < alloc < ref.amount_minor:
                continue
            posted = s.fx_index.convert_at(alloc, pay.currency, s.base, day)
            remainder = ar.credit_minor - posted
            unalloc = ref.amount_minor - alloc
            if posted > 0 and remainder > 0 and round_div(posted * ref.amount_minor, ar.credit_minor) == alloc:
                break
        else:
            raise MutationSkip()  # no split of this payment is exactly recoverable from the ledger
        after = replace(ar, credit_minor=posted)
        susp = LedgerRow(new_row_ids(s, 1)[0], ar.timestamp, "2900", 0, remainder, ar.currency, ar.entity_iid,
                         ar.invoice_iid, ar.payment_iid)
        s2 = add_rows(replace_row(s, ar.iid, credit_minor=posted), [susp])
        rec = record(self.kind, True, self.issue_type, {"allocated_share_pct": pct}, target,
                     [op_modify(ar, after), op_add(susp)], (ref.invoice_iid, pay.iid), unalloc, pay.currency,
                     [(pay.doc_iid, ar.iid, susp.iid)])
        return s2, rec


# ---- legitimate look-alikes ------------------------------------------------------------
def _unpaid(s: BookState, foreign_only: bool = False):
    paid = {r.invoice_iid for p in s.payments for r in (p.invoice_refs or ())}
    cur = current_period(s)
    _, pe = period_bounds(s)
    out = []
    for i in s.invoices:
        if i.iid in paid or period_of(i.issued_at, s.tz) != cur:
            continue
        if day_of(i.issued_at, s) > pe - timedelta(days=2):
            continue
        if foreign_only and i.currency == s.base:
            continue
        out.append(i)
    return out


def _new_payment(s: BookState, inv, amount: int, day, hh: int, mm: int):
    """Create a payment + its postings on `day` (manifest tz). Returns (state, payment, rows)."""
    pid = s.next_iid("p", [p.iid for p in s.payments])
    did = s.next_iid("d", [i.doc_iid for i in s.invoices] + [p.doc_iid for p in s.payments])
    pay = Payment(pid, did, make_ts(day, hh, mm, s.tz), inv.currency, amount, (InvoiceRef(inv.iid, amount),))
    s2 = add_payments(s, [pay])
    ids = new_row_ids(s2, 2)
    rows = payment_rows(s2.fx_index, s2.base, s2.tz, pay, inv.entity_iid, (ids[0], ids[1]))
    return add_rows(s2, rows), pay, rows


class TwinSplitPayment(Mutator):
    kind = "TWIN_SPLIT_PAYMENT"
    is_error = False

    def eligible(self, s):
        return sorted((i.iid,) for i in _unpaid(s) if i.total_minor >= 1000)

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        _, pe = period_bounds(s)
        room = (pe - day_of(inv.issued_at, s)).days
        a1 = inv.total_minor * rng.randint(35, 60) // 100
        full = rng.chance(1, 2)
        a2 = inv.total_minor - a1 if full else (inv.total_minor - a1) * rng.randint(40, 80) // 100
        d1 = rng.randint(1, room - 1)
        d2 = rng.randint(d1, room)
        h1, h2 = rng.randint(9, 13), rng.randint(14, 19)
        base_day = day_of(inv.issued_at, s)
        s2, p1, r1 = _new_payment(s, inv, a1, base_day + timedelta(days=d1), h1, rng.randint(0, 59))
        s3, p2, r2 = _new_payment(s2, inv, a2, base_day + timedelta(days=d2), h2, rng.randint(0, 59))
        diff = [op_add(p1)] + [op_add(r) for r in r1] + [op_add(p2)] + [op_add(r) for r in r2]
        rec = record(self.kind, False, None,
                     {"against": ["payment_allocation"], "fully_paid": full,
                      "distinguishing_feature": "every ref fully posted to 1200, 2900 = 0 (two receipts on one invoice)"},
                     target, diff, (inv.iid, p1.iid, p2.iid), 0, inv.currency,
                     [(p1.doc_iid, p2.doc_iid)])
        return s3, rec


class TwinTruePartial(Mutator):
    kind = "TWIN_TRUE_PARTIAL"
    is_error = False

    def eligible(self, s):
        return sorted((i.iid,) for i in _unpaid(s) if i.total_minor >= 1000)

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        _, pe = period_bounds(s)
        room = (pe - day_of(inv.issued_at, s)).days
        pct = rng.randint(30, 80)
        amount = inv.total_minor * pct // 100
        day = day_of(inv.issued_at, s) + timedelta(days=rng.randint(1, room - 1))
        s2, pay, rows = _new_payment(s, inv, amount, day, rng.randint(9, 19), rng.randint(0, 59))
        rec = record(self.kind, False, None,
                     {"against": ["payment_allocation"], "paid_share_pct": pct,
                      "distinguishing_feature": "ref.amount < invoice total and 1200 = ref.amount (2900 = 0)"},
                     target, [op_add(pay)] + [op_add(r) for r in rows], (inv.iid, pay.iid), 0, inv.currency,
                     [(pay.doc_iid,)])
        return s2, rec


class TwinRefund(Mutator):
    kind = "TWIN_REFUND"
    is_error = False

    def eligible(self, s):
        _, pe = period_bounds(s)
        return sorted((p.iid,) for p in _clean_receipts(s)
                      if day_of(p.timestamp, s) <= pe - timedelta(days=1) and p.invoice_refs[0].amount_minor >= 1000)

    def apply(self, s, target, rng: DetRng):
        pay = s.pay_by_iid[target[0]]
        ref = pay.invoice_refs[0]
        inv = s.inv_by_iid[ref.invoice_iid]
        _, pe = period_bounds(s)
        room = (pe - day_of(pay.timestamp, s)).days
        pct = rng.randint(20, 100)
        amount = ref.amount_minor * pct // 100
        day = day_of(pay.timestamp, s) + timedelta(days=rng.randint(1, room))
        pid = s.next_iid("p", [p.iid for p in s.payments])
        did = s.next_iid("d", [i.doc_iid for i in s.invoices] + [p.doc_iid for p in s.payments])
        refund = Payment(pid, did, make_ts(day, rng.randint(9, 19), rng.randint(0, 59), s.tz), pay.currency,
                         -amount, (InvoiceRef(inv.iid, -amount),))
        s2 = add_payments(s, [refund])
        ids = new_row_ids(s2, 2)
        rows = payment_rows(s2.fx_index, s2.base, s2.tz, refund, inv.entity_iid, (ids[0], ids[1]))
        s2 = add_rows(s2, rows)
        rec = record(self.kind, False, None,
                     {"against": ["duplicate_invoice", "payment_allocation"], "refund_pct": pct,
                      "distinguishing_feature": "amount_minor < 0 in the payment document (refund)"},
                     target, [op_add(refund)] + [op_add(r) for r in rows], (inv.iid, refund.iid), 0, pay.currency,
                     [(refund.doc_iid,)])
        return s2, rec


class TwinWeekendFx(Mutator):
    kind = "TWIN_WEEKEND_FX"
    is_error = False

    def _weekends(self, s, inv):
        _, pe = period_bounds(s)
        d = day_of(inv.issued_at, s) + timedelta(days=1)
        out = []
        while d <= pe:
            if d.weekday() >= 5:
                out.append(d)
            d += timedelta(days=1)
        return out

    def eligible(self, s):
        return sorted((i.iid,) for i in _unpaid(s, foreign_only=True) if self._weekends(s, i))

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        day = rng.choice(self._weekends(s, inv))
        s2, pay, rows = _new_payment(s, inv, inv.total_minor, day, rng.randint(10, 16), rng.randint(0, 59))
        used = s2.fx_index.lookup(inv.currency, s.base, day.isoformat()).date
        rec = record(self.kind, False, None,
                     {"against": ["fx_conversion"], "payment_date": day.isoformat(), "rate_date": used,
                      "distinguishing_feature": "no fx row for the weekend date; policy uses the latest rate on or before it"},
                     target, [op_add(pay)] + [op_add(r) for r in rows], (pay.iid,), 0, inv.currency,
                     [(pay.doc_iid,)])
        return s2, rec


class TwinOverpayment(Mutator):
    kind = "TWIN_OVERPAYMENT"
    is_error = False

    def eligible(self, s):
        return sorted((i.iid,) for i in _unpaid(s) if i.total_minor >= 10000)

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        _, pe = period_bounds(s)
        room = (pe - day_of(inv.issued_at, s)).days
        extra = inv.total_minor * rng.randint(5, 30) // 100
        amount = inv.total_minor + extra
        pid = s.next_iid("p", [p.iid for p in s.payments])
        did = s.next_iid("d", [i.doc_iid for i in s.invoices] + [p.doc_iid for p in s.payments])
        day = day_of(inv.issued_at, s) + timedelta(days=rng.randint(1, room - 1))
        pay = Payment(pid, did, make_ts(day, rng.randint(9, 19), rng.randint(0, 59), s.tz), inv.currency, amount,
                      (InvoiceRef(inv.iid, inv.total_minor),))
        s2 = add_payments(s, [pay])
        fxi, d = s2.fx_index, day.isoformat()
        cash = fxi.convert_at(amount, inv.currency, s.base, d)
        ar = fxi.convert_at(inv.total_minor, inv.currency, s.base, d)
        # the shortfall formula of the detector must see exactly the ref (rounding guard)
        if cash - ar <= 0 or round_div(ar * amount, cash) != inv.total_minor:
            raise MutationSkip()
        ids = new_row_ids(s2, 3)
        rows = [LedgerRow(ids[0], pay.timestamp, "1000", cash, 0, s.base, inv.entity_iid, inv.iid, pid),
                LedgerRow(ids[1], pay.timestamp, "1200", 0, ar, s.base, inv.entity_iid, inv.iid, pid),
                LedgerRow(ids[2], pay.timestamp, "2900", 0, cash - ar, s.base, inv.entity_iid, inv.iid, pid)]
        s2 = add_rows(s2, rows)
        rec = record(self.kind, False, None,
                     {"against": ["payment_allocation"], "overpay_pct": extra * 100 // inv.total_minor,
                      "distinguishing_feature": "payment amount > ref.amount: ref fully in 1200, only the excess is an advance in 2900"},
                     target, [op_add(pay)] + [op_add(r) for r in rows], (inv.iid, pay.iid), 0, inv.currency,
                     [(pay.doc_iid, rows[2].iid)])
        return s2, rec
