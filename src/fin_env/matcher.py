"""Shared matcher: structural validation + one-to-one maximum bipartite matching.

TP rule (all must hold):
  * type equal;
  * set(affected_ids) == set(issue.affected_ids) (exact string compare; order and repeats do not matter);
  * |claimed_amount_minor - expected| <= issue.amount_tolerance_minor (default 0);
  * currency equal (exact string compare, case-sensitive);
  * set(evidence_ids) is a superset of at least one allowed evidence set AND every
    cited id exists in the episode's public records (unknown ids make the finding FP).
Matching is a maximum bipartite matching (Kuhn). Findings are processed in a canonical
order, so the TP count (and the chosen pairs) do not depend on the order of submission.
Duplicates can never match the same issue twice -> they are FP.
"""
from __future__ import annotations

from .money import is_int

MAX_FINDINGS = 30
MAX_EVIDENCE = 10
MAX_EXPLANATION = 1000
REQUIRED = ("type", "affected_ids", "claimed_amount_minor", "currency", "evidence_ids", "explanation")


class StructureError(Exception):
    pass


def validate_structure(payload, expected_episode_id: str | None = None) -> list[dict]:
    """Return the list of findings or raise StructureError (-> reward -1)."""
    if isinstance(payload, dict):
        if "findings" not in payload:
            raise StructureError("MISSING_FINDINGS")
        if "episode_id" in payload and (not isinstance(payload["episode_id"], str)
                                        or (expected_episode_id is not None
                                            and payload["episode_id"] != expected_episode_id)):
            raise StructureError("EPISODE_ID")
        findings = payload["findings"]
    elif isinstance(payload, list):
        findings = payload
    else:
        raise StructureError("NOT_OBJECT")
    if not isinstance(findings, list):
        raise StructureError("FINDINGS_NOT_LIST")
    if len(findings) > MAX_FINDINGS:
        raise StructureError("TOO_MANY_FINDINGS")
    for f in findings:
        if not isinstance(f, dict) or any(k not in f for k in REQUIRED):
            raise StructureError("BAD_FINDING")
        if not isinstance(f["type"], str) or not isinstance(f["currency"], str) \
                or not isinstance(f["explanation"], str):
            raise StructureError("BAD_TYPES")
        if not is_int(f["claimed_amount_minor"]):
            raise StructureError("BAD_AMOUNT")
        for key in ("affected_ids", "evidence_ids"):
            if not isinstance(f[key], list) or not all(isinstance(x, str) for x in f[key]):
                raise StructureError("BAD_IDS")
        if len(f["evidence_ids"]) > MAX_EVIDENCE:
            raise StructureError("TOO_MANY_EVIDENCE")
        if len(f["explanation"]) > MAX_EXPLANATION:
            raise StructureError("EXPLANATION_TOO_LONG")
    return findings


def is_match(finding: dict, issue: dict, known_ids: set[str]) -> bool:
    if finding["type"] != issue["type"]:
        return False
    if set(finding["affected_ids"]) != set(issue["affected_ids"]):
        return False
    if finding["currency"] != issue["currency"]:
        return False
    tol = issue.get("amount_tolerance_minor", 0)
    if abs(finding["claimed_amount_minor"] - issue["expected_amount_minor"]) > tol:
        return False
    cited = set(finding["evidence_ids"])
    if not cited <= known_ids:
        return False
    return any(set(es) <= cited for es in issue["evidence_sets"])


def _canonical_key(f: dict):
    return (f["type"], tuple(sorted(f["affected_ids"])), f["claimed_amount_minor"], f["currency"],
            tuple(sorted(f["evidence_ids"])), f["explanation"])


def match(findings: list[dict], issues: list[dict], known_ids: set[str]) -> dict:
    """Maximum one-to-one matching. Returns tp/fp/fn and (finding_index, issue_id) pairs."""
    order = sorted(range(len(findings)), key=lambda i: _canonical_key(findings[i]))
    adj = {i: [j for j, iss in enumerate(issues) if is_match(findings[i], iss, known_ids)]
           for i in order}
    owner: dict[int, int] = {}

    def augment(i: int, seen: set[int]) -> bool:
        for j in adj[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or augment(owner[j], seen):
                owner[j] = i
                return True
        return False

    for i in order:
        augment(i, set())
    tp = len(owner)
    pairs = sorted((order.index(i), issues[j]["issue_id"]) for j, i in owner.items())
    return {"tp": tp, "fp": len(findings) - tp, "fn": len(issues) - tp,
            "matched": [(findings[order[k]]["type"], iid) for k, iid in pairs]}
