"""Read-only investigation tools over the PUBLIC files only.

No shell, SQL, file system or network. IDs are looked up in in-memory indexes
and never used to build paths. Every failure maps to a fixed error code.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext
from pathlib import Path

from . import publicio

MAX_PAGE = 50
TABLES = ("ledger", "invoices", "payments", "fx")
ERRORS = {
    "UNKNOWN_ID": "No record with this id.",
    "BAD_ACTION": "Unknown or malformed action.",
    "BAD_ARGS": "Invalid arguments.",
    "CALC_ERROR": "Expression rejected.",
    "EPISODE_DONE": "Episode is finished.",
}
_ID_FIELD = {"ledger": "row_id", "invoices": "invoice_id", "payments": "payment_id", "fx": "key"}
_META_KEYS = {"action", "name", "args", "arguments"}
_SIGNATURES = {
    "list_records": (("table",), ("cursor", "limit")),
    "get_record": (("table", "id"), ()),
    "get_document": (("doc_id",), ()),
    "calculator": (("expression",), ()),
}


class ToolError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def action_name(action) -> str | None:
    if not isinstance(action, dict):
        return None
    name = action.get("action", action.get("name"))
    return name if isinstance(name, str) else None


def action_params(action: dict) -> dict:
    for key in ("args", "arguments"):
        if isinstance(action.get(key), dict):
            return dict(action[key])
    return {k: v for k, v in action.items() if k not in _META_KEYS}


class PublicTools:
    def __init__(self, public_dir: Path):
        self.raw = publicio.load_raw(public_dir)
        raw = self.raw
        self.manifest = raw["manifest"]
        self.policy = raw["policy"]
        self._tables = {t: raw[t] for t in TABLES}
        self._index = {t: {r[_ID_FIELD[t]]: r for r in raw[t]} for t in TABLES}
        self._docs = {}
        for t in ("invoices", "payments"):
            for r in raw[t]:
                self._docs[r["doc_id"]] = r
        self._key = hashlib.blake2b(
            (self.manifest["episode_id"] + "|cursor").encode(), digest_size=16).digest()

    # ---- cursors -------------------------------------------------------
    def _tag(self, table: str, offset: int) -> str:
        return hmac.new(self._key, f"{table}:{offset}".encode(), "sha256").hexdigest()[:12]

    def _make_cursor(self, table: str, offset: int) -> str:
        return f"c{offset:06x}{self._tag(table, offset)}"

    def _parse_cursor(self, table: str, cursor) -> int:
        if cursor is None:
            return 0
        if not isinstance(cursor, str) or not re.fullmatch(r"c[0-9a-f]{6}[0-9a-f]{12}", cursor):
            raise ToolError("BAD_ARGS")
        offset = int(cursor[1:7], 16)
        if not hmac.compare_digest(cursor[7:], self._tag(table, offset)):
            raise ToolError("BAD_ARGS")
        return offset

    # ---- actions -------------------------------------------------------
    def list_records(self, table, cursor=None, limit=MAX_PAGE) -> dict:
        if table not in TABLES:
            raise ToolError("BAD_ARGS")
        if limit is None:
            limit = MAX_PAGE
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_PAGE:
            raise ToolError("BAD_ARGS")
        rows = self._tables[table]
        offset = self._parse_cursor(table, cursor)
        if offset > len(rows):
            raise ToolError("BAD_ARGS")
        page = rows[offset: offset + limit]
        end = offset + len(page)
        nxt = self._make_cursor(table, end) if end < len(rows) else None
        return {"table": table, "records": [self._public(table, r) for r in page], "next_cursor": nxt}

    def get_record(self, table, id) -> dict:
        if table not in TABLES or not isinstance(id, str):
            raise ToolError("BAD_ARGS")
        row = self._index[table].get(id)
        if row is None:
            raise ToolError("UNKNOWN_ID")
        return {"table": table, "record": self._public(table, row)}

    def get_document(self, doc_id) -> dict:
        if not isinstance(doc_id, str):
            raise ToolError("BAD_ARGS")
        row = self._docs.get(doc_id)
        if row is None:
            raise ToolError("UNKNOWN_ID")
        return {"document": dict(row)}

    def calculator(self, expression) -> dict:
        if not isinstance(expression, str):
            raise ToolError("BAD_ARGS")
        return {"value": safe_calc(expression)}

    @staticmethod
    def _public(table: str, row: dict) -> dict:
        out = {k: v for k, v in row.items() if not (table == "fx" and k == "key")}
        if table == "fx":
            out = {"id": row["key"], **out}
        return out

    # ---- dispatch ------------------------------------------------------
    def dispatch(self, action) -> tuple[dict | None, str | None]:
        """Execute an inspection action. Returns (result, error_code)."""
        try:
            name = action_name(action)
            if name not in _SIGNATURES:
                raise ToolError("BAD_ACTION")
            params = action_params(action)
            required, optional = _SIGNATURES[name]
            if any(k not in params for k in required) or set(params) - set(required) - set(optional):
                raise ToolError("BAD_ARGS")
            return getattr(self, name)(**params), None
        except ToolError as exc:
            return None, exc.code
        except Exception:  # never leak tracebacks
            return None, "BAD_ARGS"


# ---- calculator ----------------------------------------------------------
_TOKEN = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|(.))", re.S)
MAX_EXPR = 200
MAX_DIGITS = 30


def safe_calc(expression: str) -> str:
    """Arithmetic over decimal numbers: + - * / ( ) and unary signs. Nothing else."""
    if len(expression) > MAX_EXPR or not expression.strip():
        raise ToolError("CALC_ERROR")
    tokens: list[str] = []
    pos = 0
    while pos < len(expression):
        m = _TOKEN.match(expression, pos)
        if not m or m.end() == pos:
            break
        if m.group(1) is not None:
            digits = m.group(1).replace(".", "")
            if len(digits) > MAX_DIGITS:
                raise ToolError("CALC_ERROR")
            tokens.append(m.group(1))
        elif m.group(2) is not None:
            if m.group(2) not in "+-*/()":
                if m.group(2).isspace():
                    pos = m.end()
                    continue
                raise ToolError("CALC_ERROR")
            tokens.append(m.group(2))
        pos = m.end()
    if not tokens:
        raise ToolError("CALC_ERROR")
    idx = [0]

    def peek():
        return tokens[idx[0]] if idx[0] < len(tokens) else None

    def take():
        tok = peek()
        idx[0] += 1
        return tok

    def parse_expr(depth):
        if depth > 40:
            raise ToolError("CALC_ERROR")
        val = parse_term(depth)
        while peek() in ("+", "-"):
            op = take()
            rhs = parse_term(depth)
            val = val + rhs if op == "+" else val - rhs
        return val

    def parse_term(depth):
        val = parse_factor(depth)
        while peek() in ("*", "/"):
            op = take()
            rhs = parse_factor(depth)
            val = val * rhs if op == "*" else val / rhs
        return val

    def parse_factor(depth):
        tok = take()
        if tok is None:
            raise ToolError("CALC_ERROR")
        if tok in ("+", "-"):
            inner = parse_factor(depth + 1)
            return inner if tok == "+" else -inner
        if tok == "(":
            val = parse_expr(depth + 1)
            if take() != ")":
                raise ToolError("CALC_ERROR")
            return val
        if tok[0].isdigit() or tok[0] == ".":
            return Decimal(tok)
        raise ToolError("CALC_ERROR")

    try:
        with localcontext() as ctx:
            ctx.prec = 28
            ctx.traps[InvalidOperation] = True
            ctx.traps[DivisionByZero] = True
            ctx.traps[Overflow] = True
            result = parse_expr(0)
            if idx[0] != len(tokens):
                raise ToolError("CALC_ERROR")
            text = format(result.normalize(), "f")
    except ToolError:
        raise
    except (ArithmeticError, ValueError, RecursionError):
        raise ToolError("CALC_ERROR")
    return "0" if text in ("-0", "") else text
