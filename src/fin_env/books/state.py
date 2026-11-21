"""Immutable book state (internal IDs). Module A data structures."""
from __future__ import annotations

import bisect
from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal
from functools import cached_property
from typing import Literal

from ..money import convert, fmt_rate, parse_rate
from ..timeutil import local_date

IssueType = Literal["duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff"]
ISSUE_TYPES = ("duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff")
Table = Literal["ledger", "invoices", "payments", "fx"]

ACCOUNTS = {"1000": "Cash", "1200": "Accounts receivable", "2900": "Suspense (unallocated receipts)",
            "4000": "Revenue", "6100": "Operating expenses", "7900": "FX gain/loss"}


@dataclass(frozen=True)
class LedgerRow:
    iid: str
    timestamp: str
    account: str
    debit_minor: int
    credit_minor: int
    currency: str
    entity_iid: str | None
    invoice_iid: str | None
    payment_iid: str | None


@dataclass(frozen=True)
class LineItem:
    sku: str
    description: str
    service_period: str
    qty: int
    unit_minor: int


@dataclass(frozen=True)
class Invoice:
    iid: str
    doc_iid: str
    entity_iid: str
    issued_at: str
    due_at: str
    currency: str
    total_minor: int
    line_items: tuple[LineItem, ...]


@dataclass(frozen=True)
class InvoiceRef:
    invoice_iid: str
    amount_minor: int


@dataclass(frozen=True)
class Payment:
    iid: str
    doc_iid: str
    timestamp: str
    currency: str
    amount_minor: int
    invoice_refs: tuple[InvoiceRef, ...] | None


@dataclass(frozen=True)
class FxRate:
    date: str
    source: str
    target: str
    rate: Decimal

    @property
    def key(self) -> str:
        return f"FX:{self.date}:{self.source}:{self.target}"


@dataclass(frozen=True)
class BookState:
    ledger: tuple[LedgerRow, ...]
    invoices: tuple[Invoice, ...]
    payments: tuple[Payment, ...]
    fx: tuple[FxRate, ...]
    manifest: dict
    policy: dict

    # ---- cached lookups ----------------------------------------------------
    @cached_property
    def inv_by_iid(self) -> dict[str, Invoice]:
        return {i.iid: i for i in self.invoices}

    @cached_property
    def pay_by_iid(self) -> dict[str, Payment]:
        return {p.iid: p for p in self.payments}

    @cached_property
    def row_by_iid(self) -> dict[str, LedgerRow]:
        return {r.iid: r for r in self.ledger}

    @cached_property
    def rows_by_invoice(self) -> dict[str, list[LedgerRow]]:
        out: dict[str, list[LedgerRow]] = {}
        for r in self.ledger:
            if r.invoice_iid is not None:
                out.setdefault(r.invoice_iid, []).append(r)
        return out

    @cached_property
    def rows_by_payment(self) -> dict[str, list[LedgerRow]]:
        out: dict[str, list[LedgerRow]] = {}
        for r in self.ledger:
            if r.payment_iid is not None:
                out.setdefault(r.payment_iid, []).append(r)
        return out

    @cached_property
    def fx_index(self) -> "FxIndex":
        return FxIndex(self.fx)

    # ---- convenience ---------------------------------------------------------
    @property
    def base(self) -> str:
        return self.manifest["base_currency"]

    @property
    def tz(self) -> str:
        return self.manifest["timezone"]

    def next_iid(self, prefix: str, existing) -> str:
        top = 0
        for x in existing:
            if x.startswith(prefix) and x[len(prefix):].isdigit():
                top = max(top, int(x[len(prefix):]))
        return f"{prefix}{top + 1:04d}"


class FxIndex:
    """Rate lookup under the policy rule: latest rate dated on or before the given date."""

    def __init__(self, rates):
        self._dates: dict[tuple[str, str], list[str]] = {}
        self._rates: dict[tuple[str, str], list[FxRate]] = {}
        for r in sorted(rates, key=lambda x: (x.source, x.target, x.date)):
            self._dates.setdefault((r.source, r.target), []).append(r.date)
            self._rates.setdefault((r.source, r.target), []).append(r)

    def lookup(self, src: str, tgt: str, date: str) -> FxRate:
        dates = self._dates.get((src, tgt))
        if not dates:
            raise KeyError("no rates")
        i = bisect.bisect_right(dates, date) - 1
        if i < 0:
            raise KeyError("no rate on or before date")
        return self._rates[(src, tgt)][i]

    def convert_at(self, minor: int, src: str, tgt: str, date: str) -> int:
        if src == tgt:
            return minor
        return convert(minor, src, tgt, self.lookup(src, tgt, date).rate)


# ---- snapshots (internal IDs) -------------------------------------------------
def snapshot(obj) -> dict:
    d = asdict(obj)
    if isinstance(obj, FxRate):
        d["rate"] = fmt_rate(obj.rate)
    return d


def table_of(obj) -> str:
    return {LedgerRow: "ledger", Invoice: "invoices", Payment: "payments", FxRate: "fx"}[type(obj)]


def local_day(ts: str, tz: str) -> str:
    return local_date(ts, tz).isoformat()


def fx_from_strings(date: str, src: str, tgt: str, rate: str) -> FxRate:
    return FxRate(date, src, tgt, parse_rate(rate))


def with_ledger(s: BookState, rows) -> BookState:
    return replace(s, ledger=tuple(rows))


@dataclass(frozen=True)
class DiffOp:
    op: Literal["add", "modify", "remove"]
    table: Table
    iid: str
    before: dict | None
    after: dict | None


@dataclass(frozen=True)
class EvidenceSet:
    members: tuple[str, ...]


@dataclass(frozen=True)
class MutationRecord:
    mutation_id: str
    kind: str
    is_error: bool
    issue_type: str | None
    params: dict
    target_iids: tuple[str, ...]
    diff: tuple[DiffOp, ...]
    affected_iids: tuple[str, ...]
    expected_amount_minor: int
    currency: str
    evidence_sets: tuple[EvidenceSet, ...]
    group_id: str | None = None


def record_to_dict(rec: MutationRecord) -> dict:
    return {
        "mutation_id": rec.mutation_id, "kind": rec.kind, "is_error": rec.is_error,
        "issue_type": rec.issue_type, "params": rec.params, "target_iids": list(rec.target_iids),
        "diff": [{"op": d.op, "table": d.table, "iid": d.iid, "before": d.before, "after": d.after}
                 for d in rec.diff],
        "affected_iids": list(rec.affected_iids), "expected_amount_minor": rec.expected_amount_minor,
        "currency": rec.currency, "evidence_sets": [list(e.members) for e in rec.evidence_sets],
        "group_id": rec.group_id,
    }
