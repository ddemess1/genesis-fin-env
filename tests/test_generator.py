"""Module A + B end to end: every mutator, determinism, detect(clean)=0 / detect(dirty)=expected."""
import hashlib
from pathlib import Path

import pytest

from fin_env.books.clean import ERROR_KINDS, TWIN_KINDS, build_clean_books
from fin_env.generator import build_artifacts, generate_episode
from fin_env.selfcheck import detectors
from fin_env.selfcheck.runner import EpisodeInvalid, verify_clean

KIND_CFG = {
    **{k: {"errors": {k: 1}, "twins": {"TWIN_SUBSCRIPTION": 1}} for k in ERROR_KINDS},
    **{k: {"twins": {k: 1}} for k in TWIN_KINDS},
    "INT1": {"interactions": {"INT1": 1}}, "INT2": {"interactions": {"INT2": 1}},
}


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + p.read_bytes())
    return h.hexdigest()


@pytest.mark.parametrize("name", sorted(KIND_CFG))
def test_every_mutator_is_detected_independently(name):
    for seed in (11, 12, 13):
        art = build_artifacts(seed, KIND_CFG[name])
        assert verify_clean(art.clean).ok
        for rec in art.recs:
            if rec.is_error:
                assert detectors.detect(rec.issue_type, art.clean, rec.affected_iids) == 0
                assert detectors.detect(rec.issue_type, art.dirty, rec.affected_iids) == rec.expected_amount_minor > 0
            else:
                for typ in rec.params["against"]:
                    assert detectors.detect(typ, art.dirty, rec.affected_iids) == 0
                assert isinstance(rec.params["distinguishing_feature"], str)


def test_book_stays_balanced_after_every_mutation():
    art = build_artifacts(5, KIND_CFG["INT1"])
    assert sum(r.debit_minor for r in art.dirty.ledger) == sum(r.credit_minor for r in art.dirty.ledger)


def test_full_episode_passes_all_17_and_writes_two_dirs(tmp_path):
    root = generate_episode(4217, KIND_CFG["DUPLICATE_INVOICE"], tmp_path, "dev")
    assert sorted(p.name for p in (root / "public").iterdir()) == sorted(
        ["manifest.json", "policy.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv"])
    assert sorted(p.name for p in (root / "sealed").iterdir()) == ["provenance.json", "selfcheck.json", "truth.json"]
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".tmp")]


def test_same_seed_same_bytes_and_different_seed_differs(tmp_path):
    cfg = KIND_CFG["INT1"]
    a = generate_episode(42, cfg, tmp_path / "a")
    b = generate_episode(42, cfg, tmp_path / "b")
    c = generate_episode(43, cfg, tmp_path / "c")
    assert tree_hash(a) == tree_hash(b)
    assert tree_hash(a) != tree_hash(c)


def test_failed_selfcheck_leaves_no_files(tmp_path, monkeypatch):
    from fin_env import generator
    real = generator.derive_truth

    def bad_truth(recs, id_map, episode_id):
        t = real(recs, id_map, episode_id)
        t["issues"].append({"type": "fx_conversion", "affected_ids": ["PAY-NOPE"], "expected_amount_minor": 1,
                            "currency": "KZT", "amount_tolerance_minor": 0, "evidence_sets": [["DOC-NOPE"]],
                            "mutation_id": "m9999", "issue_id": "iss_99"})
        return t
    monkeypatch.setattr(generator, "derive_truth", bad_truth)
    with pytest.raises(EpisodeInvalid) as exc:
        generate_episode(9, KIND_CFG["DUPLICATE_INVOICE"], tmp_path)
    assert "seed=9" in str(exc.value) and "I10" in str(exc.value)
    assert list(tmp_path.iterdir()) == []


def test_truth_never_exposes_twins_or_internal_ids(tmp_path):
    art = build_artifacts(3, {"twins": {"TWIN_SUBSCRIPTION": 1, "TWIN_REFUND": 1, "TWIN_BOUNDARY_TZ": 1}})
    assert art.truth["issues"] == []
    assert len([r for r in art.recs if not r.is_error]) == 3


def test_public_ids_do_not_encode_clone_or_order():
    art = build_artifacts(8, KIND_CFG["DUPLICATE_INVOICE"])
    dup = next(r for r in art.recs if r.is_error)
    a, b = (art.id_map[x] for x in dup.affected_iids)
    assert a[:4] == b[:4] == "INV-" and a != b
    assert art.truth["issues"][0]["affected_ids"] == sorted([a, b])


def test_many_seeds_never_invalid(tmp_path):
    for seed in range(300, 340):
        generate_episode(seed, KIND_CFG["INT2"] if seed % 2 else KIND_CFG["INT1"], tmp_path)
