"""Terminal reward: clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1), computed exactly in Decimal."""
from __future__ import annotations

import json
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

STEP_PENALTY = Decimal("0.002")
_Q = Decimal("0.000000000001")


def prf(tp: int, fp: int, fn: int) -> tuple[Decimal, Decimal, Decimal]:
    """(precision, recall, f1). Zero denominators -> 0; both empty -> F1 = 1."""
    with localcontext() as ctx:
        ctx.prec = 28
        p = Decimal(tp) / Decimal(tp + fp) if tp + fp else Decimal(0)
        r = Decimal(tp) / Decimal(tp + fn) if tp + fn else Decimal(0)
        if tp + fp + fn == 0:
            f1 = Decimal(1)
        else:
            f1 = Decimal(2 * tp) / Decimal(2 * tp + fp + fn)
    return p, r, f1


def terminal_reward(tp: int, fp: int, fn: int, inspection_steps: int) -> Decimal:
    _, _, f1 = prf(tp, fp, fn)
    raw = 2 * f1 - 1 - STEP_PENALTY * inspection_steps
    clipped = max(Decimal(-1), min(Decimal(1), raw))
    return clipped.quantize(_Q, rounding=ROUND_HALF_EVEN)


def structural_reward() -> Decimal:
    return Decimal(-1).quantize(_Q)


def to_json_number(value: Decimal) -> float:
    """Boundary conversion: the only float in the system (rewards, never money)."""
    return json.loads(format(value, "f")) + 0.0
