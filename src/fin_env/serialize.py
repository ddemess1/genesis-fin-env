"""BookState <-> public files. Public representation uses public IDs only."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from . import publicio
from .books.state import (BookState, FxRate, Invoice, InvoiceRef, LedgerRow, LineItem, Payment)
from .money import fmt_rate, parse_rate
from .rng import DetRng
from .timeutil import parse_ts


def _p(id_map: dict, x):
    return None if x is None else id_map.get(x, x)


def state_to_raw(s: BookState, id_map: dict[str, str]) -> dict:
    ledger = [{"row_id": id_map[r.iid], "timestamp": r.timestamp, "account": r.account,
               "debit_minor": r.debit_minor, "credit_minor": r.credit_minor, "currency": r.currency,
               "entity_id": _p(id_map, r.entity_iid), "invoice_id": _p(id_map, r.invoice_iid),
               "payment_id": _p(id_map, r.payment_iid)} for r in s.ledger]
    invoices = [{"doc_id": id_map[i.doc_iid], "invoice_id": id_map[i.iid], "entity_id": id_map[i.entity_iid],
                 "issued_at": i.issued_at, "due_at": i.due_at, "currency": i.currency,
                 "total_minor": i.total_minor,
                 "line_items": [{"sku": li.sku, "description": li.description, "service_period": li.service_period,
                                 "qty": li.qty, "unit_minor": li.unit_minor} for li in i.line_items]}
                for i in s.invoices]
    payments = [{"doc_id": id_map[p.doc_iid], "payment_id": id_map[p.iid], "timestamp": p.timestamp,
                 "currency": p.currency, "amount_minor": p.amount_minor,
                 "invoice_refs": None if p.invoice_refs is None else
                 [{"invoice_id": id_map[r.invoice_iid], "amount_minor": r.amount_minor} for r in p.invoice_refs]}
                for p in s.payments]
    fx = [{"date": f.date, "source_currency": f.source, "target_currency": f.target, "rate": fmt_rate(f.rate)}
          for f in s.fx]
    return {"ledger": ledger, "invoices": invoices, "payments": payments, "fx": fx}


def manifest_with_counts(s: BookState, episode_id: str) -> dict:
    m = dict(s.manifest)
    m["episode_id"] = episode_id
    m["counts"] = {"ledger": len(s.ledger), "invoices": len(s.invoices), "payments": len(s.payments),
                   "fx": len(s.fx), "documents": len(s.invoices) + len(s.payments)}
    return m


def write_public(s: BookState, id_map: dict[str, str], order_rng: DetRng, directory: Path,
                 episode_id: str) -> dict[str, str]:
    """Shuffle table order (ledger: stable by timestamp with shuffled ties) and write the six files."""
    raw = state_to_raw(s, id_map)
    ledger = list(raw["ledger"])
    order_rng.shuffle(ledger)
    ledger.sort(key=lambda r: parse_ts(r["timestamp"]))
    invoices, payments = list(raw["invoices"]), list(raw["payments"])
    order_rng.shuffle(invoices)
    order_rng.shuffle(payments)
    fx = sorted(raw["fx"], key=lambda r: (r["date"], r["source_currency"], r["target_currency"]))
    return publicio.write_raw(directory, manifest_with_counts(s, episode_id), s.policy, ledger, invoices,
                              payments, fx)


def raw_to_state(raw: dict) -> BookState:
    """Parse public tables into a BookState whose iids ARE the public ids."""
    ledger = tuple(LedgerRow(r["row_id"], r["timestamp"], r["account"], r["debit_minor"], r["credit_minor"],
                             r["currency"], r["entity_id"], r["invoice_id"], r["payment_id"]) for r in raw["ledger"])
    invoices = tuple(Invoice(i["invoice_id"], i["doc_id"], i["entity_id"], i["issued_at"], i["due_at"],
                             i["currency"], i["total_minor"],
                             tuple(LineItem(l["sku"], l["description"], l["service_period"], l["qty"],
                                            l["unit_minor"]) for l in i["line_items"])) for i in raw["invoices"])
    payments = tuple(Payment(p["payment_id"], p["doc_id"], p["timestamp"], p["currency"], p["amount_minor"],
                             None if p["invoice_refs"] is None else
                             tuple(InvoiceRef(r["invoice_id"], r["amount_minor"]) for r in p["invoice_refs"]))
                     for p in raw["payments"])
    fx = tuple(FxRate(f["date"], f["source_currency"], f["target_currency"], parse_rate(f["rate"]))
               for f in raw["fx"])
    return BookState(ledger, invoices, payments, fx, raw["manifest"], raw["policy"])


def load_public_state(public_dir: Path) -> BookState:
    return raw_to_state(publicio.load_raw(public_dir))
