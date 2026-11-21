"""Leak scanner used by I16, C20, trajectory writer and viz tests."""
from __future__ import annotations

import re

WORDS = ("truth", "provenance", "sealed", "mutation", "issue_id", "seed", "canary", "selfcheck")
KINDS = (
    "DUPLICATE_INVOICE", "MISSING_ALLOCATION", "PARTIAL_ALLOCATION", "WRONG_FX",
    "PERIOD_CUTOFF", "TWIN_", "INT1", "INT2",
)
_INTERNAL_ID = re.compile(r"(?<![A-Za-z0-9_])[iprdeg]\d{2,}(?![A-Za-z0-9])")
_MUT_ID = re.compile(r"(?<![A-Za-z0-9])m\d{4}(?![A-Za-z0-9])")


def find_leaks(text: str, extra_tokens: tuple[str, ...] = ()) -> list[str]:
    """Return a list of forbidden substrings found in text (empty = clean)."""
    found: list[str] = []
    low = text.lower()
    for w in WORDS:
        if w in low:
            found.append(w)
    for k in KINDS:
        # not preceded by an alphanumeric or '-': public ids (ROW-INT2XX) are random base32 and may contain it
        if re.search(r"(?<![A-Za-z0-9-])" + re.escape(k), text):
            found.append(k)
    if _INTERNAL_ID.search(text):
        found.append("internal-id")
    if _MUT_ID.search(text):
        found.append("mutation-id")
    for tok in extra_tokens:
        if tok and re.search(r"(?<![0-9A-Za-z])" + re.escape(tok) + r"(?![0-9A-Za-z])", text):
            found.append("token:" + tok)
    return found


def seed_tokens(seed: int) -> tuple[str, ...]:
    """Decimal/hex spellings of the seed. Spellings shorter than 8 characters are skipped: they collide
    with ordinary numbers (qty=1, a round amount such as 100000) and say nothing about a leak. Low-entropy
    seeds are covered by the 'seed' word scan and by the long-seed probe in audit check C20."""
    return tuple(t for t in (str(seed), hex(seed), format(seed, "x")) if len(t) >= 8)
