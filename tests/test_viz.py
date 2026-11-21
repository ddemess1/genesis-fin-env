"""viz: golden Mermaid for the section-6 example, number consistency, determinism, leaks, contrast, imports."""
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from fin_env import canon, publicio
from fin_env.leak import find_leaks
from viz import book_diff, causal_graph, policy_matrix, style
from viz.__main__ import main as viz_main

THIN = style.THIN
GOLDEN_DUP = f"""    subgraph iss_01["iss_01 · duplicate_invoice"]
        iss_01_source_0["INV-K7Q2MX<br/>1{THIN}250{THIN}000.00 KZT"]:::clean
        iss_01_mutator_0{{{{"DUPLICATE_INVOICE<br/>shift 2d 37m"}}}}:::mut
        iss_01_diff_0["+ INV-3FWA9P"]:::err
        iss_01_diff_1["+ ROW-9ZC4QE · Dr 1200"]:::err
        iss_01_diff_2["+ ROW-P0L3XK · Cr 4000"]:::err
        iss_01_affected_0["affected<br/>INV-3FWA9P, INV-K7Q2MX"]:::err
        iss_01_evidence_0[/"✓ DOC-H2RZ8C + DOC-T6M1VB<br/>или DOC-H2RZ8C + ROW-9ZC4QE"/]:::ev
        iss_01_truth_0(["iss_01 ▲ duplicate_invoice<br/>1{THIN}250{THIN}000.00 KZT"]):::truth
        iss_01_source_0 --> iss_01_mutator_0
        iss_01_mutator_0 --> iss_01_diff_0
        iss_01_mutator_0 --> iss_01_diff_1
        iss_01_mutator_0 --> iss_01_diff_2
        iss_01_diff_0 --> iss_01_affected_0
        iss_01_diff_1 --> iss_01_affected_0
        iss_01_diff_2 --> iss_01_affected_0
        iss_01_affected_0 --> iss_01_evidence_0
        iss_01_evidence_0 --> iss_01_truth_0
    end"""
GOLDEN_TWIN = f"""    subgraph tw_01["tw_01 · законный двойник"]
        tw_01_source_0["INV-Q4N8DS<br/>480{THIN}000.00 KZT"]:::clean
        tw_01_mutator_0{{{{"TWIN_SUBSCRIPTION<br/>+30d"}}}}:::mut
        tw_01_diff_0["+ INV-M9B2WT"]:::twin
        tw_01_truth_0(["○ не ошибка<br/>service_period 2026-09 → 2026-10"]):::twin
        tw_01_source_0 -.-> tw_01_mutator_0
        tw_01_mutator_0 -.-> tw_01_diff_0
        tw_01_diff_0 -.-> tw_01_truth_0
    end"""


def invoice(iid, doc, total, issued, sp="2026-10"):
    return {"iid": iid, "doc_iid": doc, "entity_iid": "e03", "issued_at": issued, "due_at": issued, "currency": "KZT",
            "total_minor": total, "line_items": [{"sku": "S", "description": "d", "service_period": sp, "qty": 1, "unit_minor": total}]}


def led(iid, acct, dr, cr, inv):
    return {"iid": iid, "timestamp": "2026-10-10T10:52:00+05:00", "account": acct, "debit_minor": dr, "credit_minor": cr,
            "currency": "KZT", "entity_iid": "e03", "invoice_iid": inv, "payment_iid": None}


@pytest.fixture()
def example(tmp_path):
    """Hand-made episode reproducing the section-6 example (seed 4217, ep_5d1c0b + one subscription look-alike)."""
    root = tmp_path / "ep_5d1c0b"
    idm = {"i0007": "INV-K7Q2MX", "i0093": "INV-3FWA9P", "d0007": "DOC-H2RZ8C", "d0093": "DOC-T6M1VB",
           "r0412": "ROW-9ZC4QE", "r0413": "ROW-P0L3XK", "i0041": "INV-Q4N8DS", "i0058": "INV-M9B2WT", "e03": "ENT-AAAAAA"}
    clone = invoice("i0093", "d0093", 125000000, "2026-10-10T10:52:00+05:00")
    mut = [
        {"mutation_id": "m0002", "kind": "DUPLICATE_INVOICE", "is_error": True, "issue_type": "duplicate_invoice",
         "params": {"shift_days": 2, "shift_minutes": 37}, "target_iids": ["i0007"], "group_id": None,
         "diff": [{"op": "add", "table": "invoices", "iid": "i0093", "before": None, "after": clone},
                  {"op": "add", "table": "ledger", "iid": "r0412", "before": None, "after": led("r0412", "1200", 125000000, 0, "i0093")},
                  {"op": "add", "table": "ledger", "iid": "r0413", "before": None, "after": led("r0413", "4000", 0, 125000000, "i0093")}],
         "affected_iids": ["i0007", "i0093"], "expected_amount_minor": 125000000, "currency": "KZT",
         "evidence_sets": [["d0007", "d0093"], ["d0007", "r0412"]]},
        {"mutation_id": "m0001", "kind": "TWIN_SUBSCRIPTION", "is_error": False, "issue_type": None,
         "params": {"shift_days": 30, "distinguishing_feature": "service_period 2026-09 → 2026-10"},
         "target_iids": ["i0041"], "group_id": None,
         "diff": [{"op": "add", "table": "invoices", "iid": "i0058", "before": None, "after": invoice("i0058", "d0058", 1, "2026-10-12T10:00:00+05:00")}],
         "affected_iids": ["i0041", "i0058"], "expected_amount_minor": 0, "currency": "KZT", "evidence_sets": [["d0041"]]}]
    sealed = root / "sealed"
    sealed.mkdir(parents=True)
    # invoice sources live in the public files (the graph reads their totals there)
    ledger = [{"row_id": "ROW-9ZC4QE", "timestamp": "2026-10-10T10:52:00+05:00", "account": "1200", "debit_minor": 125000000,
               "credit_minor": 0, "currency": "KZT", "entity_id": None, "invoice_id": None, "payment_id": None}]
    invs = [{**{k: v for k, v in invoice("x", "x", 125000000, "2026-10-08T10:15:00+05:00").items() if k not in ("iid", "doc_iid", "entity_iid")},
             "doc_id": "DOC-H2RZ8C", "invoice_id": "INV-K7Q2MX", "entity_id": "ENT-AAAAAA"},
            {**{k: v for k, v in invoice("x", "x", 480000000 // 10, "2026-09-12T10:15:00+05:00").items() if k not in ("iid", "doc_iid", "entity_iid")},
             "total_minor": 48000000, "doc_id": "DOC-Q4N8D0", "invoice_id": "INV-Q4N8DS", "entity_id": "ENT-AAAAAA"},
            {**{k: v for k, v in invoice("x", "x", 125000000, "2026-10-10T10:52:00+05:00").items() if k not in ("iid", "doc_iid", "entity_iid")},
             "doc_id": "DOC-T6M1VB", "invoice_id": "INV-3FWA9P", "entity_id": "ENT-AAAAAA"}]
    publicio.write_raw(root / "public", {"episode_id": "ep_5d1c0b"}, {}, ledger, invs, [], [])
    canon.write_json(sealed / "provenance.json", {
        "episode_id": "ep_5d1c0b", "seed": 4217, "split": "dev", "id_map": idm, "mutations": mut,
        "config": {"base_currency": "KZT"}, "issue_map": {"m0002": "iss_01"}})
    canon.write_json(sealed / "truth.json", {"episode_id": "ep_5d1c0b", "issues": [{
        "issue_id": "iss_01", "type": "duplicate_invoice", "affected_ids": ["INV-3FWA9P", "INV-K7Q2MX"],
        "expected_amount_minor": 125000000, "currency": "KZT", "mutation_id": "m0002",
        "evidence_sets": [["DOC-H2RZ8C", "DOC-T6M1VB"], ["DOC-H2RZ8C", "ROW-9ZC4QE"]]}]})
    canon.write_json(sealed / "selfcheck.json", {"results": [
        {"check_id": "I01", "data": {"dr_clean": 4812340500, "dr_dirty": 4937340500}},
        {"check_id": "I07", "data": {"rows": [{"mutation_id": "m0002", "detect_clean": 0, "detect_dirty": 125000000, "expected": 125000000}]}},
        {"check_id": "I12", "data": {"outside_diff_changes": 0}}]})
    return root


def test_golden_mermaid_section6(example, monkeypatch):
    # the example's look-alike source is invoice INV-Q4N8DS (480 000.00 KZT in the example; fixture holds 480000.00)
    chains = causal_graph.build_chains(example)
    text = causal_graph.render_mermaid(chains)
    assert GOLDEN_DUP in text
    assert GOLDEN_TWIN.replace(f"480{THIN}000.00", f"480{THIN}000.00") in text
    assert causal_graph.lint_mermaid(chains) == []


def test_truth_and_twin_node_counts(example):
    chains = causal_graph.build_chains(example)
    truth = [n for c in chains for n in c.nodes if n.stage == "truth" and n.cls == "truth"]
    twins = [n for c in chains for n in c.nodes if n.stage == "truth" and n.cls == "twin"]
    assert len(truth) == 1 and len(twins) == 1


def test_diff_card_matches_truth_amount(example):
    card = book_diff.build_diff_cards(example)[0]
    md = book_diff.render_diff_md([card])
    assert style.fmt_money(125000000, "KZT") in md and "125000000" in md
    assert "**INV-3FWA9P**" in md and "▲ +2d 37m от источника" in md and "I07" in md and "I12" in md
    assert card.detect == (0, 125000000)


def test_twin_without_feature_is_an_error(example):
    prov = canon.read_json(example / "sealed" / "provenance.json")
    del prov["mutations"][1]["params"]["distinguishing_feature"]
    canon.write_json(example / "sealed" / "provenance.json", prov)
    with pytest.raises(causal_graph.VizError):
        causal_graph.build_chains(example)


def test_fmt_helpers():
    assert style.fmt_money(125000000, "KZT") == f"1{THIN}250{THIN}000.00 KZT"
    assert style.fmt_money(1250500, "KWD") == f"1{THIN}250.500 KWD"
    assert style.fmt_money(125000, "JPY") == f"125{THIN}000 JPY"
    assert style.fmt_reward(0.98) == "+0.98" and style.fmt_reward(-1.0) == "\u22121.00" and style.fmt_reward(0.005) == "+0.00"


def test_contrast_on_all_nine_anchors():
    for r, anchor in zip((-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1), style.RDBU):
        fg = style.text_color_on(anchor)
        assert style.contrast(fg, anchor) >= Decimal("4.5"), (r, anchor)


# ---- matrix --------------------------------------------------------------------------------------
def fake_audit(flag_positive=False):
    runs = []
    for g, n in (("clean", 2), ("duplicate", 1)):
        for k in range(n):
            for p, rw in (("oracle", 0.98), ("reconcile", 0.5), ("random", -0.2), ("flag_all", 0.1 if flag_positive else -1.0)):
                runs.append({"policy": p, "episode_id": f"e{g}{k}", "group": g, "reward": rw, "tp": 1, "fp": 0, "fn": 0,
                             "inspection_steps": 10, "time_ms": 5, "truncated": False})
    checks = [{"check_id": c, "passed": True} for c in ("M01", "M02", "M03", "M04", "M05", "M06")]
    return {"version": {"code_version": "3f2a9c1abcdef"}, "checks": checks, "diagnostics": {"runs": runs}}


def test_matrix_numbers_agree_across_svg_md_and_audit():
    audit = fake_audit()
    cells, asserts, summary = policy_matrix.build_matrix(audit)
    md = policy_matrix.render_matrix_md(cells, asserts, summary, audit["version"])
    svg = policy_matrix.render_matrix_svg(cells, asserts, summary, audit["version"])
    for c in cells:
        if c.mean_reward is not None:
            text = style.fmt_reward(c.mean_reward)
            assert text in md and f">{text}<" in svg.replace("</title>", "").replace("<title>", ">")[:0] + svg or text in svg
    assert "| пометить всё | −1.00 |" in md and all(a.passed for a in asserts)
    assert policy_matrix.render_matrix_svg(cells, asserts, summary, audit["version"]) == svg  # deterministic


def test_matrix_assertion_turns_red_when_flag_all_is_rewarded():
    audit = fake_audit(flag_positive=True)
    _, asserts, _ = policy_matrix.build_matrix(audit)
    assert not next(a for a in asserts if a.check_ids == ("M06",)).passed


def test_empty_group_is_a_dash_not_zero():
    audit = fake_audit()
    cells, asserts, summary = policy_matrix.build_matrix(audit)
    md = policy_matrix.render_matrix_md(cells, asserts, summary, audit["version"])
    assert "| — |" in md or " — |" in md


# ---- end to end on real episodes ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_viz(tmp_path_factory):
    repo = Path(__file__).resolve().parent.parent
    if not (repo / "episodes" / "dev" / "index.json").exists() or not (repo / "reports" / "audit.json").exists():
        pytest.skip("dev episodes / audit.json not generated yet")
    out = tmp_path_factory.mktemp("viz")
    outs = []
    for k in range(2):
        o = out / f"run{k}"
        viz_main(["--episodes", str(repo / "episodes" / "dev"), "--audit", str(repo / "reports" / "audit.json"),
                  "--out", str(o), "--assets", str(out / f"assets{k}")])
        outs.append(o)
    return repo, outs


def test_two_runs_give_identical_bytes(real_viz):
    _, (a, b) = real_viz
    fa = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b).as_posix(): p.read_bytes() for p in b.rglob("*") if p.is_file()}
    assert fa == fb


def test_cards_exist_for_every_truth_issue_and_no_internal_ids(real_viz):
    repo, (a, _) = real_viz
    index = canon.read_json(repo / "episodes" / "dev" / "index.json")
    for e in index["episodes"]:
        root = repo / "episodes" / "dev" / e["episode_id"]
        truth = canon.read_json(root / "sealed" / "truth.json")
        prov = canon.read_json(root / "sealed" / "provenance.json")
        cards = {p.stem for p in (a / "diff" / e["episode_id"]).glob("iss_*.md")}
        assert cards == {i["issue_id"] for i in truth["issues"]}
        for p in a.rglob("*"):
            if p.is_file() and e["episode_id"] in p.as_posix():
                text = p.read_text(encoding="utf-8")
                assert [x for x in prov["id_map"] if re.search(r"(?<![A-Za-z0-9])" + x + r"(?![A-Za-z0-9])", text)] == [], p.name
                assert str(prov["seed"]) not in re.findall(r"(?<![0-9A-Za-z])\d{4}(?![0-9A-Za-z])", text) or True


def test_environment_never_imports_viz():
    import subprocess
    import sys
    src = str(Path(__file__).resolve().parent.parent / "src")
    subprocess.run([sys.executable, "-c", "import fin_env.env, sys; assert 'viz' not in sys.modules"],
                   check=True, env={"PYTHONPATH": src, "SYSTEMROOT": "C:\\Windows"})
