"""Module B detectors: INDEPENDENT recomputation of each discrepancy from the records.

This module must not import anything from fin_env.mutations (enforced by a test). It only
sees a BookState (internal ids for the clean book, public ids for the book re-read from
disk) and an `affected` tuple of ids, and recomputes the discrepancy in minor units.
"""
from __future__ import annotations

import bisect

from ..books.state import BookState, Invoice, Payment
from ..money import convert, round_div
from ..timeutil import local_date, parse_ts, period_of


def _rate(s: BookState, src: str, tgt: str, day: str):
    """Policy rule: latest rate dated on or before `day` (None if there is none)."""
    cache = s.__dict__.setdefault("_det_rates", {})
    key = (src, tgt)
    if key not in cache:
        rows = sorted((r.date, r.rate) for r in s.fx if r.source == src and r.target == tgt)
        cache[key] = ([d for d, _ in rows], [r for _, r in rows])
    dates, rates = cache[key]
    i = bisect.bisect_right(dates, day) - 1
    return rates[i] if i >= 0 else None


def _line_key(inv: Invoice) -> tuple:
    return tuple(sorted((li.sku, li.description, li.service_period, li.qty, li.unit_minor)
                        for li in inv.line_items))


def _dup_key(inv: Invoice) -> tuple:
    return (inv.entity_iid, inv.currency, inv.total_minor, _line_key(inv))


def detect_duplicate(s: BookState, affected: tuple[str, ...]) -> int:
    invs = [s.inv_by_iid[i] for i in affected if i in s.inv_by_iid]
    if len(affected) != 2 or len(invs) != 2:
        return 0
    a, b = invs
    if _dup_key(a) != _dup_key(b):
        return 0
    ta, tb = parse_ts(a.issued_at), parse_ts(b.issued_at)
    if ta == tb:
        return 0
    return (b if tb > ta else a).total_minor


def detect_allocation(s: BookState, affected: tuple[str, ...]) -> int:
    """Part of each ref (payment currency) that did not reach account 1200."""
    total = 0
    for pid in affected:
        pay = s.pay_by_iid.get(pid)
        if pay is None or not pay.invoice_refs or len(pay.invoice_refs) != 1:
            continue
        ref = pay.invoice_refs[0].amount_minor
        if ref <= 0:
            continue
        rows = s.rows_by_payment.get(pid, [])
        ar = sum(r.credit_minor for r in rows if r.account == "1200")
        susp = sum(r.credit_minor for r in rows if r.account == "2900")
        if susp > 0 and ar + susp > 0:
            # payment-currency equivalent of what reached 1200; an excess of the payment over the ref
            # (advance in 2900) is legitimate, only a shortfall against the ref is a discrepancy
            posted = round_div(ar * abs(pay.amount_minor), ar + susp)
            total += max(0, ref - posted)
    return total


def detect_fx(s: BookState, affected: tuple[str, ...]) -> int:
    """|posted cash - correct conversion| in base currency for foreign-currency payments."""
    total = 0
    for pid in affected:
        pay = s.pay_by_iid.get(pid)
        if pay is None or pay.currency == s.base:
            continue
        rate = _rate(s, pay.currency, s.base, local_date(pay.timestamp, s.tz).isoformat())
        rows = [r for r in s.rows_by_payment.get(pid, []) if r.account == "1000"]
        if rate is None or not rows:
            continue
        posted = abs(sum(r.debit_minor - r.credit_minor for r in rows))
        expected = convert(abs(pay.amount_minor), pay.currency, s.base, rate)
        total += abs(posted - expected)
    return total


def detect_cutoff(s: BookState, affected: tuple[str, ...]) -> int:
    """Revenue posted in the current period for an invoice that belongs to another period."""
    current = s.manifest["period_start"][:7]
    total = 0
    for iid in affected:
        inv = s.inv_by_iid.get(iid)
        if inv is None or period_of(inv.issued_at, s.tz) == current:
            continue
        total += sum(r.credit_minor for r in s.rows_by_invoice.get(iid, [])
                     if r.account == "4000" and period_of(r.timestamp, s.tz) == current)
    return total


DETECTORS = {
    "duplicate_invoice": detect_duplicate,
    "payment_allocation": detect_allocation,
    "fx_conversion": detect_fx,
    "period_cutoff": detect_cutoff,
}


def detect(issue_type: str, s: BookState, affected: tuple[str, ...]) -> int:
    return DETECTORS[issue_type](s, tuple(affected))


def scan_book(s: BookState) -> list[tuple[str, tuple[str, ...], int]]:
    """Global independent scan: every discrepancy any detector finds in the book."""
    found: list[tuple[str, tuple[str, ...], int]] = []
    groups: dict[tuple, list[Invoice]] = {}
    for inv in s.invoices:
        groups.setdefault(_dup_key(inv), []).append(inv)
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda i: (parse_ts(i.issued_at), i.iid))
        for later in members[1:]:
            amount = detect_duplicate(s, (members[0].iid, later.iid))
            if amount:
                found.append(("duplicate_invoice", tuple(sorted((members[0].iid, later.iid))), amount))
    for pay in s.payments:
        amount = detect_allocation(s, (pay.iid,))
        if amount and pay.invoice_refs:
            found.append(("payment_allocation", tuple(sorted((pay.invoice_refs[0].invoice_iid, pay.iid))), amount))
        amount = detect_fx(s, (pay.iid,))
        if amount:
            found.append(("fx_conversion", (pay.iid,), amount))
    for inv in s.invoices:
        amount = detect_cutoff(s, (inv.iid,))
        if amount:
            found.append(("period_cutoff", (inv.iid,), amount))
    return sorted(found)
