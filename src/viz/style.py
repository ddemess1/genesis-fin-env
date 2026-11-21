"""Shared visual language: Okabe-Ito palette, money/reward/time formatting, diverging reward scale.

Formatting only. viz never recomputes numbers that the audit or self-check already produced.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from fin_env.money import EXP

FONT = "DejaVu Sans Mono, Menlo, monospace"
CHAR_W = 7          # px per character in the monospace font at 12 px
TEXT, HEAD = 12, 14

GREY, ORANGE, VERMILION, BLUE, GREEN, PURPLE = "#999999", "#E69F00", "#D55E00", "#0072B2", "#009E73", "#CC79A7"
CHANGED_BG = "#FBE3D6"
INK = "#222222"
THIN = " "      # narrow no-break space: thousands separator
MINUS = "−"

# Node classes -> (fill, stroke, stroke width, dash)
CLASSES = {
    "clean": ("#FFFFFF", GREY, 1, None),
    "mut": ("#FCEBC8", ORANGE, 1, None),
    "err": (CHANGED_BG, VERMILION, 2, None),
    "twin": ("#FFFFFF", BLUE, 1, "4 3"),
    "ev": ("#E0F2EC", GREEN, 1, None),
    "truth": ("#F5E3EE", PURPLE, 1, None),
}

# 9 anchors of the reward scale, r = -1 ... +1 in steps of 0.25 (RdBu-like; luminance chosen so that
# the number printed on every anchor has contrast >= 4.5:1 with the better of white / #222222).
RDBU = ("#B2182B", "#C0392B", "#E8836B", "#F6B8A0", "#F7F7F7", "#A9CDE6", "#6FA8D6", "#2F6EB0", "#2166AC")


def fmt_money(minor: int, ccy: str, with_ccy: bool = True) -> str:
    exp = EXP[ccy]
    sign = MINUS if minor < 0 else ""
    major, frac = divmod(abs(minor), 10 ** exp)
    text = f"{major:,}".replace(",", THIN)
    if exp:
        text += f".{frac:0{exp}d}"
    return f"{sign}{text}{' ' + ccy if with_ccy else ''}"


def fmt_reward(value) -> str:
    """+0.98 / -1.00 (always signed, true minus sign), banker's rounding."""
    d = Decimal(repr(value)) if not isinstance(value, Decimal) else value
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return f"{'+' if q >= 0 else MINUS}{abs(q):.2f}"


def fmt_ts(ts: str) -> str:
    """2026-10-10T10:52:00+05:00 -> 2026-10-10T10:52+05:00"""
    return ts[:16] + ts[19:] if len(ts) >= 25 and ts[16] == ":" else ts


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)


def reward_color(r: Decimal) -> str:
    """Integer RGB interpolation over the 9 anchors (no floats)."""
    pos = (max(Decimal(-1), min(Decimal(1), r)) + 1) * 4          # 0 .. 8
    lo = int(pos)
    lo = min(lo, 7)
    frac_num = int((pos - lo) * 1000)                               # 0 .. 1000
    a, b = _rgb(RDBU[lo]), _rgb(RDBU[lo + 1])
    mixed = tuple((a[i] * (1000 - frac_num) + b[i] * frac_num) // 1000 for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def _lin(c: int) -> Decimal:
    x = Decimal(c) / 255
    return x / Decimal("12.92") if x <= Decimal("0.03928") else ((x + Decimal("0.055")) / Decimal("1.055")) ** Decimal("2.4")


def luminance(hex_color: str) -> Decimal:
    r, g, b = _rgb(hex_color)
    return Decimal("0.2126") * _lin(r) + Decimal("0.7152") * _lin(g) + Decimal("0.0722") * _lin(b)


def contrast(c1: str, c2: str) -> Decimal:
    a, b = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (a + Decimal("0.05")) / (b + Decimal("0.05"))


def text_color_on(bg: str) -> str:
    return "#FFFFFF" if contrast("#FFFFFF", bg) >= contrast(INK, bg) else INK


def trunc_id(ident: str, limit: int = 16) -> str:
    """IDs longer than 16 characters: first 8 + ellipsis + last 4 (full id goes into <title>)."""
    return ident if len(ident) <= limit else f"{ident[:8]}…{ident[-4:]}"
