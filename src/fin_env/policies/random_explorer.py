"""Random explorer with a fixed seed: random inspections, then 0-2 random guesses."""
from __future__ import annotations

from ..rng import DetRng
from .base import Policy, submit

TABLES = ("ledger", "invoices", "payments", "fx")
TYPES = ("duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff")


class RandomExplorer(Policy):
    name = "random"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def start(self, obs):
        super().start(obs)
        self.rng = DetRng(self.seed, ("random-explorer",))
        self.n_explore = self.rng.randint(8, 40)
        self.taken = 0
        self.invoice_ids: list[str] = []
        self.payment_ids: list[str] = []
        self.doc_ids: list[str] = []
        self.row_ids: list[str] = []
        self.totals: list[int] = []
        self.base = obs["manifest"]["base_currency"]
        self.episode_id = obs["manifest"]["episode_id"]

    def _learn(self, obs):
        res = obs.get("result") or {}
        for rec in res.get("records", []) if "records" in res else []:
            self._learn_row(rec)
        if "record" in res:
            self._learn_row(res["record"])
        if "document" in res:
            self._learn_row(res["document"])

    def _learn_row(self, r: dict):
        for key, bucket in (("invoice_id", self.invoice_ids), ("payment_id", self.payment_ids),
                            ("doc_id", self.doc_ids), ("row_id", self.row_ids)):
            if r.get(key) and r[key] not in bucket:
                bucket.append(r[key])
        if "total_minor" in r:
            self.totals.append(r["total_minor"])

    def act(self, obs):
        self._learn(obs)
        if self.taken < self.n_explore:
            self.taken += 1
            kind = self.rng.randrange(4)
            if kind == 0 or not self.doc_ids:
                return {"action": "list_records", "table": self.rng.choice(TABLES), "limit": 50}
            if kind == 1:
                pools = [(t, p) for t, p in (("ledger", self.row_ids), ("invoices", self.invoice_ids),
                                             ("payments", self.payment_ids)) if p]
                table, pool = self.rng.choice(pools)
                return {"action": "get_record", "table": table, "id": self.rng.choice(pool)}
            if kind == 2:
                return {"action": "get_document", "doc_id": self.rng.choice(self.doc_ids)}
            return {"action": "calculator", "expression": "1+1"}
        findings = []
        for _ in range(self.rng.randrange(3)):
            ids = self.invoice_ids + self.payment_ids
            if not ids:
                break
            affected = sorted({self.rng.choice(ids) for _ in range(self.rng.randint(1, 2))})
            evidence = sorted({self.rng.choice(self.doc_ids + self.row_ids) for _ in range(2)}) if self.doc_ids else []
            findings.append({"type": self.rng.choice(TYPES), "affected_ids": affected,
                             "claimed_amount_minor": self.rng.choice(self.totals) if self.totals else 100,
                             "currency": self.base, "evidence_ids": evidence, "explanation": "random guess"})
        return submit(findings, self.episode_id)
