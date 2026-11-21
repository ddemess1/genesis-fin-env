"""Attack: flag everything. Reads the tables, then submits 30 findings of mixed types over visible records."""
from __future__ import annotations

from .base import Policy, submit


class FlagAllPolicy(Policy):
    name = "flag_all"

    def start(self, obs):
        super().start(obs)
        self.episode_id = obs["manifest"]["episode_id"]
        self.invoices: list[dict] = []
        self.payments: list[dict] = []
        self.stage = ["invoices", "payments"]

    def act(self, obs):
        res = obs.get("result") or {}
        if "records" in res:
            (self.invoices if res["table"] == "invoices" else self.payments).extend(res["records"])
            if res["next_cursor"]:
                return {"action": "list_records", "table": res["table"], "cursor": res["next_cursor"], "limit": 50}
        if self.stage:
            return {"action": "list_records", "table": self.stage.pop(0), "limit": 50}
        return submit(self._findings(), self.episode_id)

    def _findings(self) -> list[dict]:
        base = self.manifest["base_currency"]
        out: list[dict] = []
        invs, pays = self.invoices, self.payments
        for k in range(30):
            kind = ("duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff")[k % 4]
            inv = invs[k % len(invs)] if invs else None
            pay = pays[k % len(pays)] if pays else None
            if kind == "duplicate_invoice" and len(invs) > 1:
                a, b = invs[k % len(invs)], invs[(k + 1) % len(invs)]
                f = (sorted([a["invoice_id"], b["invoice_id"]]), b["total_minor"], b["currency"],
                     [a["doc_id"], b["doc_id"]])
            elif kind == "payment_allocation" and pay:
                ids = [pay["payment_id"]]
                if pay["invoice_refs"]:
                    ids = sorted([pay["invoice_refs"][0]["invoice_id"], pay["payment_id"]])
                f = (ids, pay["amount_minor"], pay["currency"], [pay["doc_id"]])
            elif kind == "fx_conversion" and pay:
                f = ([pay["payment_id"]], pay["amount_minor"], base, [pay["doc_id"]])
            elif inv:
                f = ([inv["invoice_id"]], inv["total_minor"], base, [inv["doc_id"]])
            else:
                continue
            out.append({"type": kind, "affected_ids": f[0], "claimed_amount_minor": f[1], "currency": f[2],
                        "evidence_ids": f[3], "explanation": "suspicious"})
        return out
