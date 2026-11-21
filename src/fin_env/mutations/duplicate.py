"""DUPLICATE_INVOICE (error) and TWIN_SUBSCRIPTION (legitimate look-alike)."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from ..books.posting import invoice_rows
from ..books.state import BookState, Invoice, LineItem
from ..rng import DetRng
from ..timeutil import fmt_ts, next_period_label, parse_ts, period_label
from .base import (MutationSkip, Mutator, add_invoice, add_rows, current_period, day_of, new_row_ids, op_add,
                   period_bounds, record)


def _shifted(inv: Invoice, days: int, minutes: int) -> tuple[str, str]:
    dt = parse_ts(inv.issued_at) + timedelta(days=days, minutes=minutes)
    due = parse_ts(inv.due_at) + timedelta(days=days, minutes=minutes)
    return fmt_ts(dt), fmt_ts(due)


def _in_period(s: BookState, inv: Invoice) -> bool:
    return period_label(day_of(inv.issued_at, s)) == current_period(s)


def _clone(s: BookState, inv: Invoice, days: int, minutes: int, items=None) -> tuple[BookState, Invoice, list]:
    issued, due = _shifted(inv, days, minutes)
    nid = s.next_iid("i", [i.iid for i in s.invoices])
    did = s.next_iid("d", [i.doc_iid for i in s.invoices] + [p.doc_iid for p in s.payments])
    clone = Invoice(nid, did, inv.entity_iid, issued, due, inv.currency, inv.total_minor,
                    items if items is not None else inv.line_items)
    s2 = add_invoice(s, clone)
    rows = []
    ps, pe = period_bounds(s)
    if ps <= day_of(clone.issued_at, s) <= pe:
        ids = new_row_ids(s2, 2)
        rows = invoice_rows(s2.fx_index, s2.base, s2.tz, clone, (ids[0], ids[1]))
        s2 = add_rows(s2, rows)
    return s2, clone, rows


class DuplicateInvoice(Mutator):
    kind = "DUPLICATE_INVOICE"
    is_error = True
    issue_type = "duplicate_invoice"
    next_period = False

    def eligible(self, s: BookState) -> list[tuple[str, ...]]:
        _, pe = period_bounds(s)
        return sorted((i.iid,) for i in s.invoices
                      if _in_period(s, i) and day_of(i.issued_at, s) <= pe - timedelta(days=4))

    def _shift(self, s: BookState, inv: Invoice, rng: DetRng) -> tuple[int, int]:
        return rng.randint(0, 3), rng.randint(1, 600)

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        days, minutes = self._shift(s, inv, rng)
        s2, clone, rows = _clone(s, inv, days, minutes)
        ev = [(inv.doc_iid, clone.doc_iid)]
        diff = [op_add(clone)] + [op_add(r) for r in rows]
        rec = record(self.kind, True, self.issue_type,
                     {"shift_days": days, "shift_minutes": minutes, "next_period": self.next_period},
                     target, diff, (inv.iid, clone.iid), clone.total_minor, clone.currency, ev)
        return s2, rec


class DuplicateNextPeriod(DuplicateInvoice):
    """INT2 component: the clone is issued in the next period (inside the +3 day window)."""
    next_period = True

    def eligible(self, s):
        _, pe = period_bounds(s)
        return sorted((i.iid,) for i in s.invoices
                      if _in_period(s, i) and day_of(i.issued_at, s) >= pe - timedelta(days=2))

    def _shift(self, s, inv, rng):
        _, pe = period_bounds(s)
        d0 = day_of(inv.issued_at, s)
        lo = (pe + timedelta(days=1) - d0).days          # first day of the next period
        hi = min(3, (pe + timedelta(days=3) - d0).days)  # inside the +3 day window
        return rng.randint(lo, hi), rng.randint(1, 120)


class TwinSubscription(Mutator):
    kind = "TWIN_SUBSCRIPTION"
    is_error = False
    issue_type = None

    def eligible(self, s):
        _, pe = period_bounds(s)
        return sorted((i.iid,) for i in s.invoices
                      if _in_period(s, i) and day_of(i.issued_at, s) + timedelta(days=28) <= pe)

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        _, pe = period_bounds(s)
        room = (pe - day_of(inv.issued_at, s)).days
        days = rng.randint(28, min(31, room))
        minutes = rng.randint(0, 90)
        issued = parse_ts(inv.issued_at) + timedelta(days=days, minutes=minutes)
        if day_of(fmt_ts(issued), s) > pe:
            minutes = 0
        old_sp = inv.line_items[0].service_period
        new_sp = next_period_label(old_sp)
        items = tuple(LineItem(li.sku, li.description, new_sp, li.qty, li.unit_minor) for li in inv.line_items)
        s2, clone, rows = _clone(s, inv, days, minutes, items)
        diff = [op_add(clone)] + [op_add(r) for r in rows]
        rec = record(self.kind, False, None,
                     {"shift_days": days, "shift_minutes": minutes, "against": ["duplicate_invoice"],
                      "distinguishing_feature": f"service_period {old_sp} → {new_sp}"},
                     target, diff, (inv.iid, clone.iid), 0, inv.currency, [(inv.doc_iid, clone.doc_iid)])
        return s2, rec
