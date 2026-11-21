"""Visual 2: before/after diff card per issue (Markdown for all, SVG for selected). Formatting only:
every number comes from provenance diffs and sealed/selfcheck.json (CheckResult.data)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fin_env import canon

from . import style
from .svg import Svg

TABLE_ORDER = ("invoices", "payments", "fx", "ledger")


@dataclass(frozen=True)
class FieldChange:
    field: str
    before: str | None
    after: str | None
    changed: bool


@dataclass(frozen=True)
class RecordChange:
    table: str
    public_id: str
    op: str
    fields: tuple[FieldChange, ...]
    source_public_id: str | None


@dataclass(frozen=True)
class DiffCard:
    issue_id: str
    issue_type: str
    kind: str
    mutation_id: str
    params: dict
    changes: tuple[RecordChange, ...]
    balance: tuple[int, int]
    detect: tuple[int, int]
    expected: int
    currency: str
    outside_diff_changes: int
    group_id: str | None
    base: str = "KZT"
    episode_id: str = ""
    members: tuple["DiffCard", ...] = ()      # group card: the member cards, in mutation order


def _pub(id_map: dict, x):
    return None if x is None else id_map.get(x, x)


def _led(snap: dict, base: str) -> str:
    amt, side = (snap["debit_minor"], "Dr") if snap["debit_minor"] else (snap["credit_minor"], "Cr")
    return f"{side} {snap['account']} · {style.fmt_money(amt, base, False)}"


def _changes_for_op(op: dict, rec: dict, id_map: dict, base: str) -> RecordChange:
    table, pid = op["table"], _pub(id_map, op["iid"])
    before, after = op["before"], op["after"]
    fields: list[FieldChange] = []
    source = None
    if op["op"] == "add":
        if table == "invoices":
            src = rec["target_iids"][0] if rec["target_iids"] and rec["target_iids"][0] in id_map else None
            source = _pub(id_map, src) if src and src.startswith("i") else None
            fields = [FieldChange("invoice_id", None, pid, True),
                      FieldChange("doc_id", None, _pub(id_map, after["doc_iid"]), True),
                      FieldChange("issued_at", None, style.fmt_ts(after["issued_at"]), True),
                      FieldChange("total", None, f"{style.fmt_money(after['total_minor'], after['currency'])} ({after['total_minor']})", True)]
            sps = {li["service_period"] for li in after["line_items"]}
            if rec["params"].get("distinguishing_feature", "").startswith("service_period"):
                fields.append(FieldChange("service_period", None, ", ".join(sorted(sps)), True))
        elif table == "payments":
            fields = [FieldChange("payment_id", None, pid, True),
                      FieldChange("amount", None, f"{style.fmt_money(after['amount_minor'], after['currency'])} ({after['amount_minor']})", True),
                      FieldChange("timestamp", None, style.fmt_ts(after["timestamp"]), True)]
        else:
            fields = [FieldChange("row", None, _led(after, base), True)]
    else:
        keys = ("account", "debit_minor", "credit_minor") if table == "ledger" else tuple(after)
        for k in keys:
            if before.get(k) != after.get(k):
                money = k in ("debit_minor", "credit_minor")
                fmt = (lambda v: style.fmt_money(v, base, False)) if money else str
                fields.append(FieldChange(k, fmt(before.get(k)), fmt(after.get(k)), True))
    return RecordChange(table, pid, op["op"], tuple(fields), source)


def _note(rc: RecordChange, fc: FieldChange, rec: dict) -> str:
    if rc.op != "add":
        return "▲ modify"
    p = rec["params"]
    if fc.field == "issued_at" and "shift_days" in p:
        return f"▲ +{p['shift_days']}d {p.get('shift_minutes', 0)}m от источника"
    if fc.field == "total" and rc.source_public_id:
        return "▲ = источник"
    return "▲ add"


def _load(episode_dir: Path):
    prov = canon.read_json(episode_dir / "sealed" / "provenance.json")
    truth = canon.read_json(episode_dir / "sealed" / "truth.json")
    sc = canon.read_json(episode_dir / "sealed" / "selfcheck.json")
    return prov, truth, sc, {r["check_id"]: r for r in sc["results"]}


def build_diff_cards(episode_dir: Path) -> list[DiffCard]:
    prov, truth, sc, checks = _load(Path(episode_dir))
    id_map, base = prov["id_map"], prov["config"]["base_currency"]
    i01, i07, i12 = checks["I01"]["data"], {r["mutation_id"]: r for r in checks["I07"]["data"]["rows"]}, checks["I12"]["data"]
    cards: list[DiffCard] = []
    for rec in prov["mutations"]:
        if not rec["is_error"]:
            continue
        ops = [_changes_for_op(op, rec, id_map, base) for op in rec["diff"]]
        ops.sort(key=lambda c: (TABLE_ORDER.index(c.table), c.public_id))
        row = i07[rec["mutation_id"]]
        cards.append(DiffCard(prov["issue_map"][rec["mutation_id"]], rec["issue_type"], rec["kind"], rec["mutation_id"],
                              rec["params"], tuple(ops), (i01["dr_clean"], i01["dr_dirty"]),
                              (row["detect_clean"], row["detect_dirty"]), rec["expected_amount_minor"],
                              rec["currency"], i12["outside_diff_changes"], rec["group_id"], base,
                              prov["episode_id"]))
    cards.sort(key=lambda c: c.issue_id)
    return cards


def group_cards(cards: list[DiffCard]) -> list[DiffCard]:
    """Interacting issues share one card (clean | after m1 | after m2); others stay single."""
    out, seen = [], set()
    for c in cards:
        if c.group_id is None:
            out.append(c)
        elif c.group_id not in seen:
            seen.add(c.group_id)
            members = tuple(sorted((m for m in cards if m.group_id == c.group_id), key=lambda m: m.mutation_id))
            out.append(DiffCard(" + ".join(m.issue_id for m in members), c.issue_type, "GROUP", c.mutation_id, {},
                                (), c.balance, c.detect, c.expected, c.currency, c.outside_diff_changes,
                                c.group_id, c.base, c.episode_id, members))
    return out


def _rows(card: DiffCard) -> list[tuple[str, list[str], str, str]]:
    """(label, values per column, marker, table) - values per column are clean | dirty or clean | m1 | m2."""
    stages = card.members or (card,)
    rows: dict[tuple, list] = {}
    order: list[tuple] = []
    for k, m in enumerate(stages):
        for rc in m.changes:
            for fc in rc.fields:
                key = (rc.table, rc.public_id, fc.field)
                if key not in rows:
                    rows[key] = [fc.before if fc.before is not None else "—"] * (len(stages) + 1)
                    order.append(key)
                    rows[key].append("▲ " + rc.op)
                for j in range(k + 1, len(stages) + 1):
                    rows[key][j] = fc.after
    return [(f"{k[1]}" if k[2] == "row" else f"{k[1]} · {k[2]}", rows[k][:-1], rows[k][-1], k[0]) for k in order]


def _check_rows(card: DiffCard) -> list[list[str]]:
    c = card
    fmt = lambda v: style.fmt_money(v, c.base)  # noqa: E731
    out = [["ΣDr = ΣCr", f"✓ {style.fmt_money(c.balance[0], c.base, False)}", f"✓ {style.fmt_money(c.balance[1], c.base, False)}", "I01"]]
    stage_cards = c.members or (c,)
    for m in stage_cards:
        ok = m.detect[1] == m.expected
        out.append([f"detect {m.issue_id}" if c.members else "detect", f"{'✓' if m.detect[0] == 0 else '✗'} {m.detect[0]}",
                    f"{'✓' if ok else '✗'} {fmt(m.detect[1])}", "= expected · I07" if ok else "≠ expected · I07"])
    out.append(["вне diff", "", f"{'✓' if c.outside_diff_changes == 0 else '✗'} {c.outside_diff_changes} изменений", "I12"])
    return out


def _params(m: DiffCard) -> str:
    p = ", ".join(f"{k}={v}" for k, v in sorted(m.params.items()) if k != "next_period")
    src = next((rc.source_public_id for rc in m.changes if rc.source_public_id), None)
    return f"params: {p}" + (f" · копия счёта {src}" if src else "")


def render_diff_md(cards: list[DiffCard]) -> str:
    out: list[str] = []
    for card in cards:
        title = f"### {card.issue_id} · {card.issue_type} · {card.kind}" + ("" if card.members else "")
        out += [title, ""]
        for m in (card.members or (card,)):
            out.append(f"{m.issue_id}: {m.issue_type} · {m.kind} ({m.mutation_id}) · " + _params(m) if card.members else _params(m))
        out.append("")
        rows = _rows(card)
        heads = ["clean", "dirty"] if not card.members else ["clean"] + [f"после {m.mutation_id}" for m in card.members]
        for table in TABLE_ORDER:
            tr = [r for r in rows if r[3] == table]
            if not tr:
                continue
            out += [f"**{table}**", "", "| поле | " + " | ".join(heads) + " | → |", "| --- |" + " --- |" * (len(heads) + 1)]
            for label, vals, marker, _ in tr:
                shown = [v if i == 0 else f"**{v}**" for i, v in enumerate(vals)]
                shown = ["—" if v is None else v for v in shown]
                note = marker
                for m in (card.members or (card,)):
                    for rc in m.changes:
                        if label.startswith(rc.public_id) and rc.fields:
                            fc = next((f for f in rc.fields if label.endswith(f.field) or f.field == "row"), rc.fields[0])
                            note = _note(rc, fc, {"params": m.params})
                out.append(f"| {label} | " + " | ".join(shown) + f" | {note} |")
            out.append("")
        out += ["**проверка**", "", "| инвариант | clean | dirty | |", "| --- | --- | --- | --- |"]
        for r in _check_rows(card):
            out.append("| " + " | ".join(r) + " |")
        out.append("")
    return "\n".join(out)


def render_diff_svg(card: DiffCard) -> str:
    rows = _rows(card)
    heads = ["поле", "clean"] + (["dirty"] if not card.members else [f"после {m.mutation_id}" for m in card.members]) + ["→"]
    table_rows = [[lbl, *vals, mk] for lbl, vals, mk, _ in rows]
    checks = _check_rows(card)
    widths = [max(len(r[i]) for r in [heads, *table_rows]) * style.CHAR_W + 16 for i in range(len(heads))]
    w = max(sum(widths) + 40, 600)
    height = 90 + (len(table_rows) + 1) * 20 + (len(checks) + 2) * 20 + 20
    svg = Svg(w, height, f"{card.issue_id} {card.issue_type}")
    svg.text(20, 24, f"{card.issue_id} · {card.issue_type} · {card.kind} · эпизод {card.episode_id}", style.HEAD, weight="bold")
    svg.text(20, 44, _params(card.members[0] if card.members else card), 12, style.GREY)
    y = 70
    x = 20
    for h, cw in zip(heads, widths):
        svg.text(x + 8, y, h, 12, weight="bold")
        x += cw
    for r in table_rows:
        y += 20
        x = 20
        for i, (v, cw) in enumerate(zip(r, widths)):
            changed = 0 < i < len(r) - 1 and v != "—" and i > 1 or (i == len(r) - 1)
            if changed:
                svg.rect(x, y - 14, cw, 20, style.CHANGED_BG)
            svg.text(x + 8, y, v, 12, style.VERMILION if changed else (style.GREY if v == "—" else style.INK),
                     weight="bold" if changed else None, tip=v if len(v) > 40 else None)
            x += cw
    y += 34
    svg.text(20, y, "проверка", 12, weight="bold")
    for r in checks:
        y += 20
        svg.text(28, y, r[0], 12)
        svg.text(28 + widths[0], y, r[1], 12, style.GREEN if r[1].startswith("✓") else style.VERMILION)
        svg.text(28 + widths[0] + widths[1], y, r[2], 12, style.GREEN if r[2].startswith("✓") else style.VERMILION)
        svg.text(28 + sum(widths[:3]), y, r[3], 12, style.GREY)
    return svg.render()
