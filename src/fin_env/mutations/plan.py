"""plan_mutations / apply_plan: fixed order = twins, single errors, interactions (INT1, INT2)."""
from __future__ import annotations

from dataclasses import dataclass, replace

from ..books.clean import ERROR_KINDS, INTERACTION_KINDS, TWIN_KINDS, GenerationError, normalize_cfg
from ..books.state import BookState, MutationRecord
from ..rng import DetRng
from .allocation import (MissingAllocation, PartialAllocation, TwinOverpayment, TwinRefund, TwinSplitPayment, TwinTruePartial,
                         TwinWeekendFx)
from .base import MutationSkip, Mutator, day_of, period_bounds
from .duplicate import DuplicateInvoice, DuplicateNextPeriod, TwinSubscription
from .fx_date import WrongFxDate, WrongFxDateNext, WrongFxRate
from .period import PeriodCutoff, TwinBoundaryTz

MUTATORS: dict[str, Mutator] = {
    "DUPLICATE_INVOICE": DuplicateInvoice(), "MISSING_ALLOCATION": MissingAllocation(),
    "PARTIAL_ALLOCATION": PartialAllocation(), "WRONG_FX_DATE": WrongFxDate(), "WRONG_FX_RATE": WrongFxRate(),
    "PERIOD_CUTOFF": PeriodCutoff(), "TWIN_SUBSCRIPTION": TwinSubscription(),
    "TWIN_SPLIT_PAYMENT": TwinSplitPayment(), "TWIN_TRUE_PARTIAL": TwinTruePartial(),
    "TWIN_REFUND": TwinRefund(), "TWIN_WEEKEND_FX": TwinWeekendFx(), "TWIN_OVERPAYMENT": TwinOverpayment(), "TWIN_BOUNDARY_TZ": TwinBoundaryTz(),
}


@dataclass(frozen=True)
class PlanItem:
    kind: str
    group_id: str | None = None


def plan_mutations(cfg: dict, rng: DetRng | None = None) -> list[PlanItem]:
    cfg = normalize_cfg(cfg)
    items: list[PlanItem] = []
    for kind in TWIN_KINDS:
        items += [PlanItem(kind)] * cfg["twins"].get(kind, 0)
    for kind in ERROR_KINDS:
        items += [PlanItem(kind)] * cfg["errors"].get(kind, 0)
    g = 0
    for kind in INTERACTION_KINDS:
        for _ in range(cfg["interactions"].get(kind, 0)):
            g += 1
            items.append(PlanItem(kind, f"g{g:02d}"))
    return items


def _ids(s: BookState, ids) -> set[str]:
    return {i for i in ids if i in s.inv_by_iid or i in s.pay_by_iid}


def _touch(s: BookState, rec: MutationRecord) -> set[str]:
    ids = set(rec.target_iids) | set(rec.affected_iids) | {d.iid for d in rec.diff if d.table in ("invoices", "payments")}
    return _ids(s, ids)


def _single(s, kind, rng, touched):
    m = MUTATORS[kind]
    cands = [c for c in m.eligible(s) if not set(c) & touched]
    while cands:
        target = rng.choice(cands)
        try:
            s2, rec = m.apply(s, target, rng)
            return s2, [rec]
        except MutationSkip:
            cands.remove(target)
    raise GenerationError(f"no eligible target for {kind}")


def _int1(s, rng, touched):
    alloc = MissingAllocation() if rng.chance(1, 2) else PartialAllocation()
    fxm = WrongFxDateNext()
    _, pe = period_bounds(s)
    fx_ok = set(fxm.eligible(s))
    cands = [c for c in alloc.eligible(s)
             if c in fx_ok and not set(c) & touched and day_of(s.pay_by_iid[c[0]].timestamp, s) == pe]
    while cands:
        target = rng.choice(cands)
        try:
            s1, r1 = alloc.apply(s, target, rng)
            s2, r2 = fxm.apply(s1, target, rng)
            return s2, [r1, r2]
        except MutationSkip:
            cands.remove(target)
    raise GenerationError("no eligible target for INT1")


def _int2(s, rng, touched):
    dup, cut = DuplicateNextPeriod(), PeriodCutoff()
    cands = [c for c in dup.eligible(s) if not set(c) & touched]
    while cands:
        target = rng.choice(cands)
        try:
            s1, r1 = dup.apply(s, target, rng)
            s2, r2 = cut.apply(s1, (r1.affected_iids[1],), rng)
            return s2, [r1, r2]
        except MutationSkip:
            cands.remove(target)
    raise GenerationError("no eligible target for INT2")


def apply_plan(s: BookState, plan: list[PlanItem], rng: DetRng) -> tuple[BookState, list[MutationRecord]]:
    recs: list[MutationRecord] = []
    touched: set[str] = set()
    for i, item in enumerate(plan):
        mrng = rng.child("mut", i)
        if item.kind == "INT1":
            s, new = _int1(s, mrng, touched)
        elif item.kind == "INT2":
            s, new = _int2(s, mrng, touched)
        else:
            s, new = _single(s, item.kind, mrng, touched)
        for rec in new:
            rec = replace(rec, mutation_id=f"m{len(recs) + 1:04d}", group_id=item.group_id)
            touched |= _touch(s, rec)
            recs.append(rec)
    return s, recs
