"""Code/config version fingerprints (content hashes, independent of git availability)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from . import CONFIG_VERSION, GENERATOR_VERSION, SCHEMA_VERSION, canon


@lru_cache(maxsize=1)
def code_version() -> str:
    root = Path(__file__).resolve().parent
    h = canon.sha256_bytes(b"".join(
        p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n")
        for p in sorted(root.rglob("*.py"))))
    return h[:12]


def versions() -> dict:
    return {"generator_version": GENERATOR_VERSION, "schema_version": SCHEMA_VERSION,
            "config_version": CONFIG_VERSION, "code_version": code_version()}
