"""Double-entry postings for invoices and payments (shared by the clean builder and mutators)."""
from __future__ import annotations

from .state import FxIndex, Invoice, LedgerRow, Payment, local_day


def invoice_rows(fxi: FxIndex, base: str, tz: str, inv: Invoice, ids: tuple[str, str]) -> list[LedgerRow]:
    """Dr 1200 AR / Cr 4000 Revenue, converted at the issue-date rate (policy)."""
    amt = fxi.convert_at(inv.total_minor, inv.currency, base, local_day(inv.issued_at, tz))
    return [
        LedgerRow(ids[0], inv.issued_at, "1200", amt, 0, base, inv.entity_iid, inv.iid, None),
        LedgerRow(ids[1], inv.issued_at, "4000", 0, amt, base, inv.entity_iid, inv.iid, None),
    ]


def payment_rows(fxi: FxIndex, base: str, tz: str, pay: Payment, entity_iid: str,
                 ids: tuple[str, str]) -> list[LedgerRow]:
    """Receipt: Dr 1000 Cash / Cr 1200 AR. Refund (negative amount): Dr 1200 / Cr 1000."""
    ref = pay.invoice_refs[0]
    day = local_day(pay.timestamp, tz)
    amt = fxi.convert_at(abs(ref.amount_minor), pay.currency, base, day)
    if ref.amount_minor >= 0:
        cash, ar = (amt, 0), (0, amt)
    else:
        cash, ar = (0, amt), (amt, 0)
    return [
        LedgerRow(ids[0], pay.timestamp, "1000", cash[0], cash[1], base, entity_iid, ref.invoice_iid, pay.iid),
        LedgerRow(ids[1], pay.timestamp, "1200", ar[0], ar[1], base, entity_iid, ref.invoice_iid, pay.iid),
    ]
