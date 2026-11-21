"""Money and FX: integer minor units, Decimal rates built from strings only."""
from __future__ import annotations

import re
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

# Fixed exponent table (not locale dependent).
EXP: dict[str, int] = {"KZT": 2, "USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
ROUNDING_NAME = "ROUND_HALF_EVEN"
ROUNDING = ROUND_HALF_EVEN
RATE_RE = re.compile(r"^\d+\.\d+$")
RATE_QUANT = Decimal("0.000001")


def parse_rate(text: str) -> Decimal:
    """Rates are decimal strings like '471.250000'; anything else is rejected."""
    if not isinstance(text, str) or not RATE_RE.match(text):
        raise ValueError("bad rate string")
    return Decimal(text)


def fmt_rate(rate: Decimal) -> str:
    return format(rate.quantize(RATE_QUANT), "f")


def convert(minor: int, src: str, tgt: str, rate: Decimal) -> int:
    """(Decimal(minor) * rate * 10**(exp_t - exp_s)).quantize(1, HALF_EVEN)."""
    if src == tgt:
        return minor
    with localcontext() as ctx:
        ctx.prec = 28
        value = Decimal(minor) * rate * (Decimal(10) ** (EXP[tgt] - EXP[src]))
        return int(value.quantize(Decimal(1), rounding=ROUNDING))


def round_div(n: int, d: int) -> int:
    """Integer n/d rounded half-to-even (d > 0)."""
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 == 1):
        q += 1
    return q


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
