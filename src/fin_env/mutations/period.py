"""PERIOD_CUTOFF (error) and TWIN_BOUNDARY_TZ (legitimate look-alike)."""
from __future__ import annotations

from datetime import timedelta

from ..books.posting import invoice_rows
from ..books.state import BookState, Invoice, LedgerRow, LineItem
from ..rng import DetRng
from ..timeutil import (fmt_offset, fmt_ts, parse_offset, parse_ts, period_label)
from ..books.clean import _amount, _due
from .base import (Mutator, add_invoice, add_rows, day_of, new_row_ids, op_add, period_bounds, record)
from datetime import datetime


class PeriodCutoff(Mutator):
    kind = "PERIOD_CUTOFF"
    is_error = True
    issue_type = "period_cutoff"

    def eligible(self, s: BookState):
        _, pe = period_bounds(s)
        return sorted((i.iid,) for i in s.invoices
                      if day_of(i.issued_at, s) > pe and i.iid not in s.rows_by_invoice)

    def apply(self, s, target, rng: DetRng):
        inv = s.inv_by_iid[target[0]]
        _, pe = period_bounds(s)
        d0 = day_of(inv.issued_at, s)
        shift = rng.randint((d0 - pe).days, 3)        # moves the posting back inside the period
        ts = fmt_ts(parse_ts(inv.issued_at) - timedelta(days=shift))
        ids = new_row_ids(s, 2)
        moved = Invoice(inv.iid, inv.doc_iid, inv.entity_iid, ts, inv.due_at, inv.currency, inv.total_minor,
                        inv.line_items)
        rows = invoice_rows(s.fx_index, s.base, s.tz, moved, (ids[0], ids[1]))
        # the rate stays the one of the invoice issue date: only the posting date is wrong
        amt = s.fx_index.convert_at(inv.total_minor, inv.currency, s.base, d0.isoformat())
        rows = [LedgerRow(r.iid, ts, r.account, r.debit_minor and amt, r.credit_minor and amt, r.currency,
                          r.entity_iid, r.invoice_iid, None) for r in rows]
        s2 = add_rows(s, rows)
        rec = record(self.kind, True, self.issue_type, {"shift_days": shift}, target,
                     [op_add(r) for r in rows], (inv.iid,), amt, s.base, [(inv.doc_iid, rows[1].iid)])
        return s2, rec


class TwinBoundaryTz(Mutator):
    kind = "TWIN_BOUNDARY_TZ"
    is_error = False

    def eligible(self, s: BookState):
        ents = sorted({i.entity_iid for i in s.invoices})
        return [(e,) for e in ents]

    def apply(self, s, target, rng: DetRng):
        _, pe = period_bounds(s)
        home = parse_offset(s.tz).utcoffset(None).total_seconds() // 60
        local_h, local_m = rng.randint(21, 23), rng.randint(0, 55)
        ks = [k for k in range(3, 10) if -12 * 60 <= home + 60 * k <= 14 * 60]
        k = rng.choice(ks)
        local = datetime(pe.year, pe.month, pe.day, local_h, local_m, 0, tzinfo=parse_offset(s.tz))
        issued = fmt_ts(local.astimezone(parse_offset(fmt_offset(int(home) + 60 * k))))
        ccy = s.base if not rng.chance(1, 3) or len(s.manifest["currency_exponents"]) < 2 else rng.choice(
            sorted(c for c in s.manifest["currency_exponents"] if c != s.base))
        label = period_label(pe)
        qty, unit = rng.randint(1, 3), _amount(rng, ccy, 3)
        nid = s.next_iid("i", [i.iid for i in s.invoices])
        did = s.next_iid("d", [i.doc_iid for i in s.invoices] + [p.doc_iid for p in s.payments])
        inv = Invoice(nid, did, target[0], issued, _due(issued), ccy, qty * unit,
                      (LineItem("SRV-CNS", "Consulting", label, qty, unit),))
        s2 = add_invoice(s, inv)
        ids = new_row_ids(s2, 2)
        rows = invoice_rows(s2.fx_index, s2.base, s2.tz, inv, (ids[0], ids[1]))
        s2 = add_rows(s2, rows)
        feature = f"issued_at {issued} = {fmt_ts(local)} in the manifest timezone"
        rec = record(self.kind, False, None, {"against": ["period_cutoff"], "distinguishing_feature": feature},
                     target, [op_add(inv)] + [op_add(r) for r in rows], (inv.iid,), 0, s.base,
                     [(inv.doc_iid, rows[1].iid)])
        return s2, rec
