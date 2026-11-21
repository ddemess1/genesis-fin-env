"""Module A: build_clean_books(seed, cfg) -> BookState (balanced, internally consistent, error-free)."""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta
from decimal import Decimal

from .. import CONFIG_VERSION, SCHEMA_VERSION
from ..money import EXP, ROUNDING_NAME
from ..rng import DetRng
from ..timeutil import fmt_ts, make_ts, month_range, parse_offset, parse_ts, period_label
from .posting import invoice_rows, payment_rows
from .state import (ACCOUNTS, BookState, FxIndex, FxRate, Invoice, InvoiceRef, LedgerRow, LineItem,
                    Payment)

ERROR_KINDS = ("DUPLICATE_INVOICE", "MISSING_ALLOCATION", "PARTIAL_ALLOCATION", "WRONG_FX_DATE",
               "WRONG_FX_RATE", "PERIOD_CUTOFF")
INTERACTION_KINDS = ("INT1", "INT2")
TWIN_KINDS = ("TWIN_SUBSCRIPTION", "TWIN_SPLIT_PAYMENT", "TWIN_TRUE_PARTIAL", "TWIN_REFUND",
              "TWIN_WEEKEND_FX", "TWIN_BOUNDARY_TZ", "TWIN_OVERPAYMENT")
NEXT_PERIOD_WINDOW_DAYS = 3

CFG_DEFAULTS = {
    "config_version": CONFIG_VERSION, "base_currency": "KZT", "currencies": ["USD", "EUR"],
    "period_start": "2026-10-01", "timezone": "+05:00", "n_invoices": 40, "n_misc": 60,
    "n_entities": 8, "paid_pct": 65, "foreign_pct": 35, "alt_tz_pct": 15,
    "errors": {}, "interactions": {}, "twins": {}, "group": None,
}
# USD value of one unit, in 1e-6 USD (nominal levels; random walks start near these).
_VALUE_MICRO_USD = {"KZT": 2100, "USD": 1_000_000, "EUR": 1_080_000, "JPY": 6700, "KWD": 3_250_000}
_AMOUNT_MAJOR = {"KZT": (60_000, 2_500_000), "USD": (150, 9000), "EUR": (150, 9000),
                 "JPY": (20_000, 1_200_000), "KWD": (50, 2500)}
_SKUS = (("SRV-AUD", "Audit services"), ("SRV-CNS", "Consulting"), ("LIC-ANN", "Software license"),
         ("SUP-MNT", "Maintenance support"), ("TRN-WRK", "Training workshop"), ("HW-DEV", "Hardware device"))
_ALT_OFFSETS = ("+00:00", "+01:00", "+03:00", "+06:00", "+08:00", "-05:00", "+02:00", "+09:00")


class GenerationError(Exception):
    pass


def normalize_cfg(cfg: dict) -> dict:
    out = copy.deepcopy(CFG_DEFAULTS)
    for k, v in (cfg or {}).items():
        out[k] = copy.deepcopy(v)
    base = out["base_currency"]
    if base not in EXP:
        raise GenerationError("unknown base currency")
    out["currencies"] = sorted(c for c in out["currencies"] if c != base)
    for c in out["currencies"]:
        if c not in EXP:
            raise GenerationError("unknown currency")
    ps, pe = month_range(out["period_start"])
    if ps.day != 1 or (pe - ps).days + 1 < 30:
        raise GenerationError("period must be a calendar month of 30-31 days")
    for group, kinds in (("errors", ERROR_KINDS), ("interactions", INTERACTION_KINDS), ("twins", TWIN_KINDS)):
        for k, n in out[group].items():
            if k not in kinds or not isinstance(n, int) or n < 0:
                raise GenerationError(f"bad {group} entry")
    if sum(out["errors"].values()) + 2 * sum(out["interactions"].values()) > 12:
        raise GenerationError("more than 12 errors")
    return out


def requirements(cfg: dict) -> dict[str, int]:
    """Minimum number of invoices per category the clean book must contain."""
    e, i, t = cfg["errors"], cfg["interactions"], cfg["twins"]
    n_fx = e.get("WRONG_FX_DATE", 0) + e.get("WRONG_FX_RATE", 0)
    n_alloc = e.get("MISSING_ALLOCATION", 0) + e.get("PARTIAL_ALLOCATION", 0)

    def need(n: int) -> int:
        return 2 * n + 1 if n else 0
    return {
        "early": need(t.get("TWIN_SUBSCRIPTION", 0)),
        "late": need(i.get("INT2", 0)),
        "int1": need(i.get("INT1", 0)),
        "fxp": need(n_fx),
        "unpf": need(t.get("TWIN_WEEKEND_FX", 0)),
        "unp": need(t.get("TWIN_SPLIT_PAYMENT", 0) + t.get("TWIN_TRUE_PARTIAL", 0) + t.get("TWIN_OVERPAYMENT", 0)),
        "paid": need(n_alloc + t.get("TWIN_REFUND", 0)),
        "next": need(e.get("PERIOD_CUTOFF", 0)),
    }


def build_policy() -> dict:
    return {
        "fx_rate_rule": ("fx.csv rate = units of the base currency per 1 unit of the source currency. "
                         "Invoice postings use the rate of the invoice issue date and payment postings use "
                         "the rate of the payment date, both dates taken in the manifest timezone. If fx.csv "
                         "has no row for that date, use the latest row dated on or before it. Converted "
                         "minor units = round_half_even(amount_minor * rate * 10^(exp_base - exp_source))."),
        "period_rule": ("The reporting period is [period_start, period_end] inclusive in the manifest "
                        "timezone. A document belongs to the period of its issued_at/timestamp converted to "
                        "that timezone, and its ledger rows must be posted in that same period. Documents "
                        "dated up to 3 days after period_end may exist; they are not booked in this period."),
        "next_period_window_days": NEXT_PERIOD_WINDOW_DAYS,
        "rounding": ROUNDING_NAME,
        "accounts": ACCOUNTS,
        "posting": ("Invoice: Dr 1200 / Cr 4000. Payment: Dr 1000 / Cr 1200 for the part allocated to the "
                    "invoice and Cr 2900 for any unallocated part. Refund (negative amount_minor): "
                    "Dr 1200 / Cr 1000. Rate differences: 7900. Other rows: operating expenses."),
        "claims": {
            "duplicate_invoice": "affected_ids = the two invoice ids; amount = total_minor of the later invoice, in the invoice currency",
            "payment_allocation": "affected_ids = [invoice id, payment id]; amount = part of the payment NOT posted to 1200, in the payment currency",
            "fx_conversion": "affected_ids = [payment id]; amount = |posted cash (1000) - correct converted amount|, in the base currency",
            "period_cutoff": "affected_ids = [invoice id]; amount = amount posted to revenue (4000), in the base currency",
        },
        "evidence": ("evidence_ids may be doc ids (DOC-...), ledger row ids (ROW-...) or fx keys "
                     "(FX:<date>:<source>:<target>); at most 10; extra existing ids are allowed."),
    }


def build_manifest(cfg: dict) -> dict:
    ps, pe = month_range(cfg["period_start"])
    used = sorted({cfg["base_currency"], *cfg["currencies"]})
    return {"schema_version": SCHEMA_VERSION, "config_version": cfg["config_version"],
            "base_currency": cfg["base_currency"], "period_start": ps.isoformat(), "period_end": pe.isoformat(),
            "timezone": cfg["timezone"], "rounding": ROUNDING_NAME,
            "currency_exponents": {c: EXP[c] for c in used}}


def _nominal_micro(src: str, tgt: str) -> int:
    return _VALUE_MICRO_USD[src] * 1_000_000 // _VALUE_MICRO_USD[tgt]


def build_fx(rng: DetRng, cfg: dict, ps: date, pe: date) -> list[FxRate]:
    base = cfg["base_currency"]
    rows: list[FxRate] = []
    for ccy in cfg["currencies"]:
        r = _nominal_micro(ccy, base) * (100 + rng.randint(-4, 4)) // 100
        d = ps - timedelta(days=10)
        while d <= pe + timedelta(days=8):
            if d.weekday() < 5:
                step = rng.randint(15, 60) * 100
                r = r * (1_000_000 + (step if rng.chance(1, 2) else -step)) // 1_000_000
                rows.append(FxRate(d.isoformat(), ccy, base, Decimal(f"{r // 10**6}.{r % 10**6:06d}")))
            d += timedelta(days=1)
    return rows


def _amount(rng: DetRng, ccy: str, scale_div: int = 1) -> int:
    lo, hi = _AMOUNT_MAJOR[ccy]
    major = rng.randint(max(1, lo // scale_div), max(2, hi // scale_div))
    exp = EXP[ccy]
    if rng.chance(1, 5):
        major = max(1, major // 100 * 100) if major >= 100 else major
        return major * 10 ** exp
    return major * 10 ** exp + (rng.randint(1, 10 ** exp - 1) if exp > 0 else 0)


def _items(rng: DetRng, ccy: str, period: str) -> tuple[tuple[LineItem, ...], int]:
    items = []
    for _ in range(rng.randint(1, 3)):
        sku, desc = _SKUS[rng.randrange(len(_SKUS))]
        items.append(LineItem(sku, desc, period, rng.randint(1, 4), _amount(rng, ccy, 3)))
    return tuple(items), sum(i.qty * i.unit_minor for i in items)


def _due(issued_at: str) -> str:
    dt = parse_ts(issued_at)
    return fmt_ts((dt + timedelta(days=30)).replace(hour=23, minute=59, second=0))


def _tsfmt(d: date, hh: int, mm: int, tz: str, alt: str | None) -> str:
    dt = datetime(d.year, d.month, d.day, hh, mm, 0, tzinfo=parse_offset(tz))
    return fmt_ts(dt.astimezone(parse_offset(alt)) if alt else dt)


def build_clean_books(seed: int, cfg: dict) -> BookState:
    cfg = normalize_cfg(cfg)
    rng = DetRng(seed).child("clean")
    base, tz = cfg["base_currency"], cfg["timezone"]
    ps, pe = month_range(cfg["period_start"])
    days = (pe - ps).days + 1
    period = period_label(ps)
    fx = build_fx(rng.child("fx"), cfg, ps, pe)
    fxi = FxIndex(fx)
    foreign = cfg["currencies"]
    ents = [f"e{k + 1:02d}" for k in range(cfg["n_entities"])]

    req = requirements(cfg)
    plans: list[str] = []
    for cat in sorted(req):
        plans += [cat] * req[cat]
    n_dup = cfg["errors"].get("DUPLICATE_INVOICE", 0)
    plans += ["next"] * rng.randint(0, 1)
    plans += ["normal"] * max(cfg["n_invoices"] - len(plans), 8 + 2 * n_dup)
    arng = rng.child("invoices")
    arng.shuffle(plans)

    invoices: list[Invoice] = []
    payments: list[Payment] = []
    ledger: list[LedgerRow] = []
    seen: set[tuple] = set()
    counters = {"i": 0, "p": 0, "d": 0, "r": 0}

    def nid(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}{counters[prefix]:04d}"

    def issue_day(cat: str) -> date:
        if cat == "early":
            return ps + timedelta(days=arng.randint(0, days - 29))
        if cat == "late":
            return pe - timedelta(days=arng.randint(0, 2))
        if cat == "int1":
            return pe - timedelta(days=arng.randint(3, 15))
        if cat == "next":
            return pe + timedelta(days=arng.randint(1, NEXT_PERIOD_WINDOW_DAYS))
        if cat in ("unp", "unpf"):
            return ps + timedelta(days=arng.randint(0, 17))
        return ps + timedelta(days=arng.randint(0, days - 4))

    for cat in plans:
        ccy = base
        if foreign and (cat in ("int1", "fxp", "unpf") or arng.chance(cfg["foreign_pct"], 100)):
            ccy = arng.choice(foreign)
        ent = arng.choice(ents)
        d0 = issue_day(cat)
        alt = None
        if cat in ("normal", "fxp", "paid", "unp") and arng.chance(cfg["alt_tz_pct"], 100):
            alt = arng.choice(_ALT_OFFSETS)
        label = period_label(d0)
        for _ in range(30):
            items, total = _items(arng, ccy, label)
            key = (ent, total, ccy, tuple(sorted(i.service_period for i in items)))
            if key not in seen:
                seen.add(key)
                break
        else:
            raise GenerationError("could not build a unique invoice")
        issued = _tsfmt(d0, arng.randint(8, 18), arng.randint(0, 59), tz, alt)
        inv = Invoice(nid("i"), nid("d"), ent, issued, _due(issued), ccy, total, items)
        invoices.append(inv)
        if d0 > pe:
            continue  # next-period document: not booked in this period
        ledger += invoice_rows(fxi, base, tz, inv, (nid("r"), nid("r")))
        # --- payment decision
        if cat in ("unp", "unpf", "next"):
            continue
        if cat == "int1":
            pay_day, hh, mm, palt = pe, arng.randint(8, 22), arng.randint(0, 59), None
        else:
            room = (pe - d0).days - (2 if cat == "paid" else 0)
            pct = 100 if cat in ("fxp", "paid") else cfg["paid_pct"]
            if room < 1 or not arng.chance(pct, 100):
                continue
            pay_day = d0 + timedelta(days=arng.randint(1, min(20, room)))
            hh, mm = arng.randint(9, 20), arng.randint(0, 59)
            palt = alt if (alt and arng.chance(1, 2)) else None
        pts = _tsfmt(pay_day, hh, mm, tz, palt)
        pay = Payment(nid("p"), nid("d"), pts, ccy, total, (InvoiceRef(inv.iid, total),))
        payments.append(pay)
        ledger += payment_rows(fxi, base, tz, pay, ent, (nid("r"), nid("r")))

    # --- documentless postings (rent, payroll, fees): realistic noise, repeated legit amounts
    mrng = rng.child("misc")
    recurring = [_amount(mrng, base, 20) for _ in range(3)]
    n_misc = cfg["n_misc"]
    floor_rows = 220                      # case size range: 200-2000 postings; keep a safety margin
    n_misc = max(n_misc, (floor_rows - len(ledger) + 1) // 2)
    for _ in range(n_misc):
        amt = mrng.choice(recurring) if mrng.chance(2, 5) else _amount(mrng, base, 20)
        ts = _tsfmt(ps + timedelta(days=mrng.randint(0, days - 1)), mrng.randint(8, 19), mrng.randint(0, 59), tz, None)
        ledger.append(LedgerRow(nid("r"), ts, "6100", amt, 0, base, None, None, None))
        ledger.append(LedgerRow(nid("r"), ts, "1000", 0, amt, base, None, None, None))

    return BookState(tuple(ledger), tuple(invoices), tuple(payments), tuple(fx),
                     build_manifest(cfg), build_policy())
