"""Simple reconciliation baseline: reads every table, then applies four naive textbook checks.

Deliberately naive (this is what the environment must make insufficient): it ignores service periods,
compares calendar months as written in the timestamps (not in the manifest timezone) and flags every
similar pair. It is a baseline for diagnostics, not a good auditor.
"""
from __future__ import annotations

from decimal import Decimal

from ..money import convert
from .base import Policy, submit

TABLES = ("invoices", "payments", "ledger", "fx")


def _list(table: str, cursor=None) -> dict:
    return {"action": "list_records", "table": table, "cursor": cursor, "limit": 50}


class ReconcilePolicy(Policy):
    name = "reconcile"

    def start(self, obs):
        super().start(obs)
        self.episode_id = obs["manifest"]["episode_id"]
        self.base = obs["manifest"]["base_currency"]
        self.month = obs["manifest"]["period_start"][:7]
        self.data = {t: [] for t in TABLES}
        self.todo = list(TABLES)

    def act(self, obs):
        res = obs.get("result") or {}
        if "records" in res:
            self.data[res["table"]] += res["records"]
            if res["next_cursor"]:
                return _list(res["table"], res["next_cursor"])
        if self.todo:
            return _list(self.todo.pop(0))
        return submit(self.findings()[:30], self.episode_id)

    # ---- the four naive checks -------------------------------------------------------------
    def findings(self) -> list[dict]:
        invs, pays, rows = self.data["invoices"], self.data["payments"], self.data["ledger"]
        by_pay: dict[str, list[dict]] = {}
        by_inv: dict[str, list[dict]] = {}
        for r in rows:
            if r["payment_id"]:
                by_pay.setdefault(r["payment_id"], []).append(r)
            if r["invoice_id"] and not r["payment_id"]:
                by_inv.setdefault(r["invoice_id"], []).append(r)
        rates: dict[tuple[str, str], list[tuple[str, Decimal]]] = {}
        for f in self.data["fx"]:
            rates.setdefault((f["source_currency"], f["target_currency"]), []).append((f["date"], f["id"], Decimal(f["rate"])))
        out: list[dict] = []
        groups: dict[tuple, list[dict]] = {}
        for i in invs:
            groups.setdefault((i["entity_id"], i["currency"], i["total_minor"]), []).append(i)
        for members in groups.values():
            members.sort(key=lambda i: i["issued_at"])
            for later in members[1:]:
                out.append(self._f("duplicate_invoice", sorted([members[0]["invoice_id"], later["invoice_id"]]),
                                   later["total_minor"], later["currency"], [members[0]["doc_id"], later["doc_id"]]))
        for p in pays:
            if not p["invoice_refs"] or p["amount_minor"] <= 0:
                continue
            prow = by_pay.get(p["payment_id"], [])
            susp = [r for r in prow if r["account"] == "2900"]
            ar = [r for r in prow if r["account"] == "1200"]
            s_susp = sum(r["credit_minor"] for r in susp)
            if s_susp > 0:
                total = s_susp + sum(r["credit_minor"] for r in ar)
                amount = (2 * p["amount_minor"] * s_susp + total) // (2 * total)
                out.append(self._f("payment_allocation", sorted([p["invoice_refs"][0]["invoice_id"], p["payment_id"]]),
                                   amount, p["currency"], [p["doc_id"]] + [r["row_id"] for r in susp + ar]))
            if p["currency"] != self.base:
                cands = [x for x in rates.get((p["currency"], self.base), []) if x[0] <= p["timestamp"][:10]]
                cash = [r for r in prow if r["account"] == "1000"]
                if cands and cash:
                    key, rate = cands[-1][1], cands[-1][2]
                    expected = convert(abs(p["amount_minor"]), p["currency"], self.base, rate)
                    posted = abs(sum(r["debit_minor"] - r["credit_minor"] for r in cash))
                    if posted != expected:
                        out.append(self._f("fx_conversion", [p["payment_id"]], abs(posted - expected), self.base,
                                           [p["doc_id"], key, cash[0]["row_id"]]))
        for i in invs:
            rev = [r for r in by_inv.get(i["invoice_id"], []) if r["account"] == "4000"]
            if i["issued_at"][:7] != self.month and rev:
                out.append(self._f("period_cutoff", [i["invoice_id"]], sum(r["credit_minor"] for r in rev),
                                   self.base, [i["doc_id"], rev[0]["row_id"]]))
        return out

    @staticmethod
    def _f(kind, affected, amount, currency, evidence) -> dict:
        return {"type": kind, "affected_ids": affected, "claimed_amount_minor": amount, "currency": currency,
                "evidence_ids": evidence[:10], "explanation": "naive reconciliation mismatch"}
