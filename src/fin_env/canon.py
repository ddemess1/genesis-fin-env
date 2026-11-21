"""Canonical serialization shared by generator, env and audit."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def write_text(path: Path, text: str) -> str:
    """Write UTF-8 text (LF line ends, no translation); returns the sha256 of the bytes written."""
    data = text.encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return sha256_bytes(data)


def write_json(path: Path, obj) -> str:
    return write_text(path, dumps(obj) + "\n")


def write_jsonl(path: Path, rows: list) -> str:
    return write_text(path, "".join(dumps(r) + "\n" for r in rows))


def write_csv(path: Path, header: list[str], rows: list[list]) -> str:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return write_text(path, buf.getvalue())


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]
