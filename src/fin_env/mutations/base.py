"""Mutation framework: pure functions over BookState that emit MutationRecords."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from ..books.state import (BookState, DiffOp, EvidenceSet, Invoice, LedgerRow, MutationRecord, Payment,
                           snapshot)
from ..rng import DetRng
from ..selfcheck import detectors
from ..timeutil import local_date, period_label


class MutationSkip(Exception):
    """apply() found this target unusable (e.g. zero discrepancy after rounding): try the next one."""


class Mutator:
    kind: str = ""
    is_error: bool = True
    issue_type: str | None = None

    def eligible(self, s: BookState) -> list[tuple[str, ...]]:
        raise NotImplementedError

    def apply(self, s: BookState, target: tuple[str, ...], rng: DetRng) -> tuple[BookState, MutationRecord]:
        raise NotImplementedError

    def detect(self, s: BookState, affected: tuple[str, ...]) -> int:
        """Delegates to the independent detector (selfcheck.detectors)."""
        return detectors.detect(self.issue_type, s, affected) if self.issue_type else 0


# ---- state helpers ----------------------------------------------------------------
def period_bounds(s: BookState) -> tuple[date, date]:
    return date.fromisoformat(s.manifest["period_start"]), date.fromisoformat(s.manifest["period_end"])


def current_period(s: BookState) -> str:
    return period_label(period_bounds(s)[0])


def day_of(ts: str, s: BookState) -> date:
    return local_date(ts, s.tz)


def add_rows(s: BookState, rows: list[LedgerRow]) -> BookState:
    return replace(s, ledger=s.ledger + tuple(rows))


def add_invoice(s: BookState, inv: Invoice) -> BookState:
    return replace(s, invoices=s.invoices + (inv,))


def add_payments(s: BookState, pays: list[Payment]) -> BookState:
    return replace(s, payments=s.payments + tuple(pays))


def replace_row(s: BookState, iid: str, **changes) -> BookState:
    return replace(s, ledger=tuple(replace(r, **changes) if r.iid == iid else r for r in s.ledger))


def new_row_ids(s: BookState, n: int) -> list[str]:
    base = max([int(r.iid[1:]) for r in s.ledger if r.iid[1:].isdigit()] or [0])
    return [f"r{base + k + 1:04d}" for k in range(n)]


def op_add(obj) -> DiffOp:
    from ..books.state import table_of
    return DiffOp("add", table_of(obj), obj.iid, None, snapshot(obj))


def op_modify(before, after) -> DiffOp:
    from ..books.state import table_of
    return DiffOp("modify", table_of(after), after.iid, snapshot(before), snapshot(after))


def fx_key_for(s: BookState, ccy: str, day: str) -> str:
    return s.fx_index.lookup(ccy, s.base, day).key


def record(kind: str, is_error: bool, issue_type: str | None, params: dict, target: tuple[str, ...],
           diff: list[DiffOp], affected: tuple[str, ...], expected: int, currency: str,
           evidence: list[tuple[str, ...]]) -> MutationRecord:
    if is_error and expected <= 0:
        raise MutationSkip()
    return MutationRecord(
        mutation_id="", kind=kind, is_error=is_error, issue_type=issue_type, params=params,
        target_iids=tuple(target), diff=tuple(diff), affected_iids=tuple(affected),
        expected_amount_minor=expected, currency=currency,
        evidence_sets=tuple(EvidenceSet(tuple(sorted(e))) for e in evidence), group_id=None)
