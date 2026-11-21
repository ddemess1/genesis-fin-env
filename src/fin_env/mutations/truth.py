"""The ONLY place where truth.json / provenance.json content is produced - always from MutationRecords."""
from __future__ import annotations

import base64
import hashlib

from ..books.state import BookState, MutationRecord, record_to_dict
from ..rng import DetRng

_PREFIX = {"i": "INV", "p": "PAY", "d": "DOC", "r": "ROW", "e": "ENT"}


def all_iids(s: BookState) -> list[str]:
    ids: set[str] = set()
    for r in s.ledger:
        ids.add(r.iid)
        ids.update(x for x in (r.entity_iid, r.invoice_iid, r.payment_iid) if x)
    for i in s.invoices:
        ids.update((i.iid, i.doc_iid, i.entity_iid))
    for p in s.payments:
        ids.update((p.iid, p.doc_iid))
    return sorted(ids)


def assign_public_ids(s: BookState, rng: DetRng) -> dict[str, str]:
    """iid -> public id: PREFIX- + 6 base32 chars of blake2b(salt || iid); collision -> next salt."""
    iids = all_iids(s)
    for attempt in range(100):
        salt = f"{rng.seed}|ids|{attempt}"
        mapping = {}
        for iid in iids:
            digest = hashlib.blake2b(f"{salt}|{iid}".encode(), digest_size=5).digest()
            mapping[iid] = f"{_PREFIX[iid[0]]}-{base64.b32encode(digest).decode()[:6]}"
        if len(set(mapping.values())) == len(mapping):
            return mapping
    raise RuntimeError("public id collision")


def pub(id_map: dict[str, str], x: str) -> str:
    return id_map.get(x, x)  # fx keys are already public


def derive_truth(recs: list[MutationRecord], id_map: dict[str, str], episode_id: str) -> dict:
    issues = []
    for rec in recs:
        if not rec.is_error:
            continue
        issues.append({
            "type": rec.issue_type,
            "affected_ids": sorted(pub(id_map, x) for x in rec.affected_iids),
            "expected_amount_minor": rec.expected_amount_minor,
            "currency": rec.currency,
            "amount_tolerance_minor": 0,
            "evidence_sets": sorted(sorted(pub(id_map, x) for x in es.members) for es in rec.evidence_sets),
            "mutation_id": rec.mutation_id,
        })
    issues.sort(key=lambda i: (i["type"], i["affected_ids"]))
    for n, issue in enumerate(issues, 1):
        issue["issue_id"] = f"iss_{n:02d}"
    return {"episode_id": episode_id, "issues": issues}


def derive_provenance(seed: int, cfg: dict, config_hash: str, recs: list[MutationRecord],
                      id_map: dict[str, str], versions: dict, truth: dict, files_sha256: dict,
                      split: str, episode_id: str) -> dict:
    return {
        "episode_id": episode_id, "seed": seed, "split": split, "config": cfg, "config_hash": config_hash,
        "versions": versions, "mutations": [record_to_dict(r) for r in recs], "id_map": id_map,
        "issue_map": {i["mutation_id"]: i["issue_id"] for i in truth["issues"]},
        "files_sha256": files_sha256,
    }
