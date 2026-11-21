"""generate_episode(seed, cfg): A (clean books -> mutators) -> B (self-check) -> write to disk."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import canon
from .books.clean import build_clean_books, normalize_cfg
from .books.state import BookState, MutationRecord
from .mutations.plan import apply_plan, plan_mutations
from .mutations.truth import assign_public_ids, derive_provenance, derive_truth
from .rng import DetRng
from .selfcheck.runner import CheckReport, EpisodeInvalid, verify_clean, verify_episode
from .serialize import write_public
from .version import versions


@dataclass
class Artifacts:
    seed: int
    cfg: dict
    config_hash: str
    episode_id: str
    clean: BookState
    dirty: BookState
    recs: list[MutationRecord]
    id_map: dict[str, str]
    truth: dict


def fill_defaults(cfg: dict | None) -> dict:
    """An empty/partial config still yields a valid episode: a clean book needs >= 3 look-alikes (I17)."""
    cfg = dict(cfg or {})
    if not cfg.get("errors") and not cfg.get("interactions") and not cfg.get("twins"):
        cfg["twins"] = {"TWIN_SUBSCRIPTION": 1, "TWIN_REFUND": 1, "TWIN_BOUNDARY_TZ": 1}
    return cfg


def config_hash(cfg: dict) -> str:
    return canon.sha256_bytes(canon.dumps(cfg).encode())[:16]


def make_episode_id(seed: int, chash: str) -> str:
    return "ep_" + hashlib.blake2b(f"{seed}|{chash}|episode".encode(), digest_size=4).hexdigest()


def build_artifacts(seed: int, cfg: dict) -> Artifacts:
    cfg = normalize_cfg(cfg)
    chash = config_hash(cfg)
    rng = DetRng(seed)
    clean = build_clean_books(seed, cfg)
    report = verify_clean(clean)
    if not report.ok:
        raise EpisodeInvalid(report, seed)
    plan = plan_mutations(cfg, rng.child("plan"))
    dirty, recs = apply_plan(clean, plan, rng)
    id_map = assign_public_ids(dirty, rng.child("ids"))
    episode_id = make_episode_id(seed, chash)
    truth = derive_truth(recs, id_map, episode_id)
    return Artifacts(seed, cfg, chash, episode_id, clean, dirty, recs, id_map, truth)


def report_to_dict(report: CheckReport) -> dict:
    return {"episode_id": report.episode_id, "ok": report.ok,
            "results": [{"check_id": r.check_id, "passed": r.passed, "d_condition": r.d_condition,
                         "detail": r.detail, "refs": list(r.refs), "data": r.data} for r in report.results]}


def generate_episode(seed: int, cfg: dict, out_dir: Path, split: str = "open") -> Path:
    """Generate, self-verify, then write episodes/<...>/<episode_id>/{public,sealed}. Returns the root."""
    art = build_artifacts(seed, cfg)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f".tmp-{art.episode_id}"
    if tmp.exists():
        shutil.rmtree(tmp)
    try:
        rng = DetRng(seed)
        files = write_public(art.dirty, art.id_map, rng.child("order"), tmp / "public", art.episode_id)
        report = verify_episode(art.clean, art.dirty, art.recs, art.truth, tmp / "public", art.id_map, seed)
        if not report.ok:
            raise EpisodeInvalid(report, seed)
        sealed = tmp / "sealed"
        sealed.mkdir(parents=True, exist_ok=True)
        canon.write_json(sealed / "truth.json", art.truth)
        canon.write_json(sealed / "provenance.json", derive_provenance(
            seed, art.cfg, art.config_hash, art.recs, art.id_map, versions(), art.truth, files, split,
            art.episode_id))
        canon.write_json(sealed / "selfcheck.json", report_to_dict(report))
        root = out_dir / art.episode_id
        if root.exists():
            shutil.rmtree(root)
        try:
            tmp.rename(root)
        except OSError:  # e.g. a sync client (OneDrive) holds the directory: copy instead of rename
            shutil.copytree(tmp, root)
        generate_episode.last_report = report  # for the CLI banner (timing is NOT persisted)
        return root
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def generate_to_temp(seed: int, cfg: dict) -> tuple[tempfile.TemporaryDirectory, Path]:
    td = tempfile.TemporaryDirectory(prefix="fin-env-")
    return td, generate_episode(seed, cfg, Path(td.name))


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m fin_env.generate")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", default="dev")
    a = ap.parse_args(argv)
    cfg = canon.read_json(a.config)
    try:
        root = generate_episode(a.seed, cfg, a.out, a.split)
    except EpisodeInvalid as exc:
        print(f"EpisodeInvalid: {exc}", file=sys.stderr)
        return 2
    rep = generate_episode.last_report
    n = sum(r.passed for r in rep.results)
    print(f"✓ selfcheck {n}/{len(rep.results)} ({rep.duration_ms} ms)  {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
