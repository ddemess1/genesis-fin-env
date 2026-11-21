"""Shared test helpers: build a full in-memory episode context from the real generator."""
from dataclasses import replace

import pytest

from fin_env import publicio
from fin_env.generator import build_artifacts
from fin_env.rng import DetRng
from fin_env.selfcheck.invariants import Ctx
from fin_env.serialize import raw_to_state, write_public

DEFAULT_CFG = {"errors": {"DUPLICATE_INVOICE": 1, "PARTIAL_ALLOCATION": 1, "WRONG_FX_RATE": 1},
               "twins": {"TWIN_SUBSCRIPTION": 1, "TWIN_REFUND": 1}}


def make_ctx(tmp_path, cfg=None, seed=7):
    art = build_artifacts(seed, cfg or DEFAULT_CFG)
    pub_dir = tmp_path / "public"
    write_public(art.dirty, art.id_map, DetRng(seed).child("order"), pub_dir, art.episode_id)
    raw = publicio.load_raw(pub_dir)
    ctx = Ctx(clean=art.clean, pub=raw_to_state(raw), dirty_mem=art.dirty, raw=raw, recs=art.recs,
              truth=art.truth, id_map=art.id_map, public_dir=pub_dir, seed=seed)
    return ctx, art


def retarget(ctx):
    """Rebuild the parsed public state after tampering with ctx.raw."""
    ctx.pub = raw_to_state(ctx.raw)
    return ctx


@pytest.fixture()
def ctx(tmp_path):
    c, _ = make_ctx(tmp_path)
    return c
