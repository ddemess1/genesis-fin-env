"""Evaluator-side oracle: reads the sealed truth, submits correct findings after exactly 10 inspections.

It measures the reward ceiling; it says nothing about agent ability."""
from __future__ import annotations

from pathlib import Path

from .. import canon
from .base import Scripted, submit

ORACLE_STEPS = 10


class OraclePolicy(Scripted):
    name = "oracle"

    def __init__(self, sealed_dir: Path):
        self.truth = canon.read_json(Path(sealed_dir) / "truth.json")

    def plan(self, obs):
        actions: list[dict] = []
        ids: list[str] = []
        for issue in self.truth["issues"]:
            ids += [x for x in issue["evidence_sets"][0] if x not in ids]
        for x in ids[:ORACLE_STEPS]:
            if x.startswith("DOC-"):
                actions.append({"action": "get_document", "doc_id": x})
            elif x.startswith("ROW-"):
                actions.append({"action": "get_record", "table": "ledger", "id": x})
            else:
                actions.append({"action": "get_record", "table": "fx", "id": x})
        while len(actions) < ORACLE_STEPS:
            actions.append({"action": "list_records", "table": "ledger", "limit": 50})
        findings = [{"type": i["type"], "affected_ids": list(i["affected_ids"]),
                     "claimed_amount_minor": i["expected_amount_minor"], "currency": i["currency"],
                     "evidence_ids": list(i["evidence_sets"][0]), "explanation": "recomputed from evidence"}
                    for i in self.truth["issues"]]
        actions.append(submit(findings, self.truth["episode_id"]))
        return actions
