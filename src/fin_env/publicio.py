"""Reading/writing the six public files as plain dicts (public IDs only)."""
from __future__ import annotations

import csv
from pathlib import Path

from . import canon

LEDGER_COLS = ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency",
               "entity_id", "invoice_id", "payment_id"]
FX_COLS = ["date", "source_currency", "target_currency", "rate"]
PUBLIC_FILES = ("manifest.json", "policy.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv")
NULL = "null"


def fx_key(date: str, src: str, tgt: str) -> str:
    return f"FX:{date}:{src}:{tgt}"


def _cell(value) -> str:
    return NULL if value is None else str(value)


def write_raw(directory: Path, manifest: dict, policy: dict, ledger: list[dict],
              invoices: list[dict], payments: list[dict], fx: list[dict]) -> dict[str, str]:
    """Write the six files; returns {filename: sha256}."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    return {
        "manifest.json": canon.write_json(d / "manifest.json", manifest),
        "policy.json": canon.write_json(d / "policy.json", policy),
        "ledger.csv": canon.write_csv(d / "ledger.csv", LEDGER_COLS,
                                      [[_cell(r[c]) for c in LEDGER_COLS] for r in ledger]),
        "invoices.jsonl": canon.write_jsonl(d / "invoices.jsonl", invoices),
        "payments.jsonl": canon.write_jsonl(d / "payments.jsonl", payments),
        "fx.csv": canon.write_csv(d / "fx.csv", FX_COLS, [[_cell(r[c]) for c in FX_COLS] for r in fx]),
    }


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_raw(directory: Path) -> dict:
    """Parse public files into typed dicts. Missing references become None."""
    d = Path(directory)
    ledger = []
    for r in _read_csv(d / "ledger.csv"):
        row = {k: (None if v == NULL else v) for k, v in r.items()}
        row["debit_minor"] = int(row["debit_minor"])
        row["credit_minor"] = int(row["credit_minor"])
        ledger.append(row)
    fx = []
    for r in _read_csv(d / "fx.csv"):
        row = dict(r)
        row["key"] = fx_key(row["date"], row["source_currency"], row["target_currency"])
        fx.append(row)
    return {
        "manifest": canon.read_json(d / "manifest.json"),
        "policy": canon.read_json(d / "policy.json"),
        "ledger": ledger,
        "invoices": canon.read_jsonl(d / "invoices.jsonl"),
        "payments": canon.read_jsonl(d / "payments.jsonl"),
        "fx": fx,
    }


def known_ids(raw: dict) -> set[str]:
    ids: set[str] = set()
    ids.update(r["row_id"] for r in raw["ledger"])
    ids.update(r["invoice_id"] for r in raw["invoices"])
    ids.update(r["payment_id"] for r in raw["payments"])
    ids.update(r["doc_id"] for r in raw["invoices"])
    ids.update(r["doc_id"] for r in raw["payments"])
    ids.update(r["key"] for r in raw["fx"])
    return ids
