"""Harmless transformations for paired checks: reorder rows, rename IDs (prefixes kept, order broken)."""
from __future__ import annotations

import base64
import hashlib
import shutil
from pathlib import Path

from fin_env import canon, publicio
from fin_env.rng import DetRng

_PREFIXES = ("INV", "PAY", "DOC", "ROW", "ENT")


def _variant_dir(out_dir: Path | None, public_dir: Path, tag: str) -> Path:
    base = Path(out_dir) if out_dir else Path(public_dir).parent.parent / f"{Path(public_dir).parent.name}-{tag}"
    if base.exists():
        shutil.rmtree(base)
    (base / "public").mkdir(parents=True)
    return base


def reorder(public_dir: Path, rng: DetRng, out_dir: Path | None = None) -> Path:
    """Permute the rows of every table (a different permutation than the original). Returns the new episode root."""
    raw = publicio.load_raw(public_dir)
    root = _variant_dir(out_dir, public_dir, "reorder")
    tables = {}
    for name in ("ledger", "invoices", "payments", "fx"):
        rows = list(raw[name])
        for _ in range(10):
            rng.shuffle(rows)
            if len(rows) < 2 or rows != raw[name]:
                break
        tables[name] = rows
    publicio.write_raw(root / "public", raw["manifest"], raw["policy"], tables["ledger"], tables["invoices"],
                       tables["payments"], [{k: v for k, v in r.items() if k != "key"} for r in tables["fx"]])
    return root


def _fresh_ids(olds: list[str], salt: str, prefix: str) -> dict[str, str]:
    mapping = {}
    for old in olds:
        digest = hashlib.blake2b(f"{salt}|{old}".encode(), digest_size=5).digest()
        mapping[old] = f"{prefix}-{base64.b32encode(digest).decode()[:6]}"
    return mapping


def build_mapping(raw: dict, rng: DetRng) -> dict[str, str]:
    groups: dict[str, set[str]] = {p: set() for p in _PREFIXES}
    for r in raw["ledger"]:
        groups["ROW"].add(r["row_id"])
        for k in ("entity_id", "invoice_id", "payment_id"):
            if r[k]:
                groups[k[:3].upper() if k != "entity_id" else "ENT"].add(r[k])
    for i in raw["invoices"]:
        groups["INV"].add(i["invoice_id"]); groups["DOC"].add(i["doc_id"]); groups["ENT"].add(i["entity_id"])
    for p in raw["payments"]:
        groups["PAY"].add(p["payment_id"]); groups["DOC"].add(p["doc_id"])
    mapping: dict[str, str] = {}
    for prefix in _PREFIXES:
        olds = sorted(groups[prefix])
        for attempt in range(50):
            m = _fresh_ids(olds, f"{rng.randrange(1 << 62)}|{attempt}", prefix)
            news = list(m.values())
            unique = len(set(news)) == len(news) and not (set(news) & set(olds))
            order_broken = len(olds) < 3 or [m[o] for o in olds] != sorted(news)
            if unique and order_broken:
                mapping.update(m)
                break
        else:
            raise RuntimeError("could not rename ids")
    return mapping


def apply_mapping_raw(raw: dict, m: dict[str, str]) -> dict:
    mp = lambda x: None if x is None else m.get(x, x)  # noqa: E731
    ledger = [{**r, "row_id": mp(r["row_id"]), "entity_id": mp(r["entity_id"]), "invoice_id": mp(r["invoice_id"]),
               "payment_id": mp(r["payment_id"])} for r in raw["ledger"]]
    invoices = [{**i, "doc_id": mp(i["doc_id"]), "invoice_id": mp(i["invoice_id"]), "entity_id": mp(i["entity_id"])}
                for i in raw["invoices"]]
    payments = [{**p, "doc_id": mp(p["doc_id"]), "payment_id": mp(p["payment_id"]),
                 "invoice_refs": None if p["invoice_refs"] is None else
                 [{**r, "invoice_id": mp(r["invoice_id"])} for r in p["invoice_refs"]]} for p in raw["payments"]]
    return {**raw, "ledger": ledger, "invoices": invoices, "payments": payments}


def rename_ids(public_dir: Path, rng: DetRng, out_dir: Path | None = None) -> tuple[Path, dict[str, str]]:
    """Consistently rename IDs in all public files. Returns (new episode root, old->new mapping)."""
    raw = publicio.load_raw(public_dir)
    mapping = build_mapping(raw, rng)
    new = apply_mapping_raw(raw, mapping)
    root = _variant_dir(out_dir, public_dir, "rename")
    publicio.write_raw(root / "public", new["manifest"], new["policy"], new["ledger"], new["invoices"],
                       new["payments"], [{k: v for k, v in r.items() if k != "key"} for r in new["fx"]])
    return root, mapping


def map_truth(truth: dict, mapping: dict[str, str]) -> dict:
    """Apply an id mapping to truth (affected ids re-sorted, evidence sets re-sorted)."""
    mp = lambda x: mapping.get(x, x)  # noqa: E731
    issues = []
    for i in truth["issues"]:
        issues.append({**i, "affected_ids": sorted(mp(x) for x in i["affected_ids"]),
                       "evidence_sets": sorted(sorted(mp(x) for x in es) for es in i["evidence_sets"])})
    return {**truth, "issues": issues}


def write_sealed(root: Path, truth: dict) -> None:
    (root / "sealed").mkdir(parents=True, exist_ok=True)
    canon.write_json(root / "sealed" / "truth.json", truth)


def variant(root: Path, rng: DetRng, reorder_rows: bool, rename: bool, out_dir: Path) -> tuple[Path, dict[str, str]]:
    """Build a transformed copy of an episode (public transformed, sealed truth mapped). Returns (root, mapping)."""
    truth = canon.read_json(root / "sealed" / "truth.json")
    mapping: dict[str, str] = {}
    cur = root / "public"
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    stage = out.parent / (out.name + "-stage")
    if rename:
        r1, mapping = rename_ids(cur, rng, stage)
        cur = r1 / "public"
    if reorder_rows:
        r2 = reorder(cur, rng, out)
    else:
        shutil.copytree(cur.parent, out)
        r2 = out
    if stage.exists():
        shutil.rmtree(stage)
    write_sealed(r2, map_truth(truth, mapping))
    return r2, mapping
