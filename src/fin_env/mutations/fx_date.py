"""WRONG_FX_DATE / WRONG_FX_RATE (errors): the cash row is converted with a wrong rate and the
difference is balanced through account 7900 (double entry stays intact)."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from ..books.state import BookState, LedgerRow, Payment
from ..money import convert, fmt_rate
from ..rng import DetRng
from ..timeutil import period_of
from .allocation import _clean_receipts
from .base import (MutationSkip, Mutator, add_rows, current_period, day_of, fx_key_for, new_row_ids, op_add,
                   op_modify, period_bounds, record, replace_row)


def _foreign_payments(s: BookState) -> list[Payment]:
    cur = current_period(s)
    out = []
    for p in s.payments:
        if p.currency == s.base or p.amount_minor <= 0 or not p.invoice_refs:
            continue
        if period_of(p.timestamp, s.tz) != cur:
            continue
        cash = [r for r in s.rows_by_payment.get(p.iid, []) if r.account == "1000"]
        if len(cash) == 1 and cash[0].debit_minor > 0 and not any(
                r.account == "7900" for r in s.rows_by_payment.get(p.iid, [])):
            out.append(p)
    return out


class _WrongFx(Mutator):
    is_error = True
    issue_type = "fx_conversion"

    def candidates(self, s: BookState, pay: Payment) -> list[tuple[str, Decimal]]:
        """Sorted list of (label, wrong rate) giving a non-zero discrepancy."""
        raise NotImplementedError

    def eligible(self, s):
        return sorted((p.iid,) for p in _foreign_payments(s) if self.candidates(s, p))

    def apply(self, s, target, rng: DetRng):
        pay = s.pay_by_iid[target[0]]
        cands = self.candidates(s, pay)
        if not cands:
            raise MutationSkip()
        label, wrong = rng.choice(cands)
        cash = next(r for r in s.rows_by_payment[pay.iid] if r.account == "1000")
        new_cash = convert(pay.amount_minor, pay.currency, s.base, wrong)
        delta = new_cash - cash.debit_minor
        if delta == 0:
            raise MutationSkip()
        ref = pay.invoice_refs[0]
        gl = LedgerRow(new_row_ids(s, 1)[0], cash.timestamp, "7900", max(-delta, 0), max(delta, 0), s.base,
                       cash.entity_iid, cash.invoice_iid, pay.iid)
        after = replace(cash, debit_minor=new_cash)
        s2 = add_rows(replace_row(s, cash.iid, debit_minor=new_cash), [gl])
        key = fx_key_for(s, pay.currency, day_of(pay.timestamp, s).isoformat())
        rec = record(self.kind, True, self.issue_type, self.params(label, wrong), target,
                     [op_modify(cash, after), op_add(gl)], (pay.iid,), abs(delta), s.base,
                     [(pay.doc_iid, key, cash.iid)])
        return s2, rec

    def params(self, label, wrong) -> dict:
        return {"variant": label, "wrong_rate": fmt_rate(wrong)}


class WrongFxDate(_WrongFx):
    kind = "WRONG_FX_DATE"

    def _dates(self, s: BookState, pay: Payment) -> list[tuple[str, date]]:
        pday = day_of(pay.timestamp, s)
        inv = s.inv_by_iid[pay.invoice_refs[0].invoice_iid]
        return [("invoice_date", day_of(inv.issued_at, s)), ("previous_day", pday - timedelta(days=1))]

    def candidates(self, s, pay):
        correct = s.fx_index.lookup(pay.currency, s.base, day_of(pay.timestamp, s).isoformat()).rate
        out = []
        for label, d in self._dates(s, pay):
            try:
                rate = s.fx_index.lookup(pay.currency, s.base, d.isoformat()).rate
            except KeyError:
                continue
            if convert(pay.amount_minor, pay.currency, s.base, rate) != convert(
                    pay.amount_minor, pay.currency, s.base, correct):
                out.append((f"{label}:{d.isoformat()}", rate))
        return sorted(out)


class WrongFxDateNext(WrongFxDate):
    """INT1 component: the rate of the next business day after the payment is used."""

    def _dates(self, s, pay):
        pday = day_of(pay.timestamp, s)
        return [(f"next_day+{k}", pday + timedelta(days=k)) for k in range(1, 6)][:5]

    def candidates(self, s, pay):
        cands = super().candidates(s, pay)
        return cands[:1]  # the nearest following date whose rate differs


class WrongFxRate(_WrongFx):
    kind = "WRONG_FX_RATE"

    def candidates(self, s, pay):
        correct = s.fx_index.lookup(pay.currency, s.base, day_of(pay.timestamp, s).isoformat()).rate
        micro = int(correct * 1_000_000)
        out = []
        variants = [(f"pct{sign}{p}", micro * (100 + sign * p) // 100)
                    for p in (1, 2, 3, 4, 5) for sign in (-1, 1)]
        variants.append(("inverted", 10 ** 12 // micro))
        for label, m in variants:
            if m <= 0:
                continue
            rate = Decimal(f"{m // 10**6}.{m % 10**6:06d}")
            if convert(pay.amount_minor, pay.currency, s.base, rate) != convert(
                    pay.amount_minor, pay.currency, s.base, correct):
                out.append((label, rate))
        return sorted(out)
