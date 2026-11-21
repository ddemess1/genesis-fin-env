"""pytest calls the very same check functions the `python -m audit` command runs (no duplicated logic)."""
import importlib
import tempfile
from pathlib import Path

import pytest

from audit.common import DEFAULT_SUITE, Store
from audit.runner import BLOCK_MODULES


@pytest.fixture(scope="session")
def store():
    with tempfile.TemporaryDirectory(prefix="fin-audit-test-") as d:
        yield Store.build(DEFAULT_SUITE, Path(d), fast=True)


def collect():
    out = []
    for block, mod in BLOCK_MODULES.items():
        try:
            m = importlib.import_module(f"audit.{mod}")
        except ModuleNotFoundError:
            continue
        out += [(cid, title, fn) for cid, (title, fn) in sorted(m.CHECKS.items())]
    return out


@pytest.mark.parametrize("cid,title,fn", collect(), ids=[c[0] for c in collect()])
def test_audit_check(store, cid, title, fn):
    ok, detail = fn(store)
    assert ok, f"{cid} {title}: {detail}"
