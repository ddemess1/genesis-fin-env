"""Visual 3: policy x episode-group matrix of mean terminal reward (reliability of the reward).

Only formatting, except the one allowed computation: means (exact Decimal) and micro P/R/F1 over summed
TP/FP/FN - the same definition as the matcher. Timing (non-deterministic) goes to policy_timing.md.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from decimal import Decimal

from fin_env.policies.registry import LABELS, ORDER

from . import style
from .svg import Svg

GROUPS = ("clean", "duplicate", "allocation", "fx", "period", "interaction")
GROUP_LABELS = {"clean": "Чистые", "duplicate": "Дубли", "allocation": "Оплаты", "fx": "FX", "period": "Период",
                "interaction": "Взаим."}
NOTES = {"oracle": "верхняя граница, не агент", "random": "seed фиксирован", "flag_all": "атака",
         "reconcile": "базовый алгоритм"}
CELL_W, CELL_H = 80, 36


@dataclass(frozen=True)
class MatrixCell:
    policy: str
    group: str
    n: int
    mean_reward: Decimal | None


@dataclass(frozen=True)
class Assertion:
    text: str
    check_ids: tuple[str, ...]
    passed: bool


def _runs(audit: dict) -> list[dict]:
    return [r for r in audit["diagnostics"]["runs"] if "reward" in r]


def _policies(runs: list[dict]) -> list[str]:
    present = {r["policy"] for r in runs}
    return [p for p in ORDER if p in present] + sorted(present - set(ORDER))


def _mean(rewards: list[float]) -> Decimal:
    return sum((Decimal(repr(r)) for r in rewards), Decimal(0)) / len(rewards)


def _check_ok(audit: dict, cid: str) -> bool:
    return any(c["check_id"] == cid and c["passed"] for c in audit["checks"])


def build_matrix(audit: dict) -> tuple[list[MatrixCell], list[Assertion], list[dict]]:
    runs = _runs(audit)
    pols = _policies(runs)
    cells: list[MatrixCell] = []
    for p in pols:
        for g in (*GROUPS, "all"):
            sel = [r["reward"] for r in runs if r["policy"] == p and (g == "all" or r["group"] == g)]
            cells.append(MatrixCell(p, g, len(sel), _mean(sel) if sel else None))
    cell = {(c.policy, c.group): c for c in cells}
    # assertions are evaluated on episodes / on the audit's own check results, never on rendered numbers
    others = [p for p in pols if p != "oracle"]
    oracle_best = all(
        cell[("oracle", g)].mean_reward is None or all(
            cell[(p, g)].mean_reward is None or cell[("oracle", g)].mean_reward >= cell[(p, g)].mean_reward
            for p in others) for g in GROUPS)
    flag_neg = all(r["reward"] < 0 for r in runs if r["policy"] == "flag_all") and \
        any(r["policy"] == "flag_all" for r in runs)
    assertions = [
        Assertion("oracle не ниже остальных на каждой группе (по средней награде)", ("M01", "M02"),
                  oracle_best and _check_ok(audit, "M01") and _check_ok(audit, "M02")),
        Assertion("молчание на чистых выше ложных обвинений", ("M03", "M04"),
                  _check_ok(audit, "M03") and _check_ok(audit, "M04")),
        Assertion("«пометить всё» ниже нуля на каждом эпизоде", ("M06",), flag_neg and _check_ok(audit, "M06")),
        Assertion("дубль вывода не повышает награду", ("M05",), _check_ok(audit, "M05")),
    ]
    summary = []
    for p in pols:
        rs = [r for r in runs if r["policy"] == p]
        tp, fp, fn = (sum(r[k] for r in rs) for k in ("tp", "fp", "fn"))
        prec = Decimal(tp) / Decimal(tp + fp) if tp + fp else Decimal(0)
        rec = Decimal(tp) / Decimal(tp + fn) if tp + fn else Decimal(0)
        f1 = Decimal(2 * tp) / Decimal(2 * tp + fp + fn) if 2 * tp + fp + fn else Decimal(1)
        summary.append({"policy": p, "p": prec, "r": rec, "f1": f1, "reward": _mean([r["reward"] for r in rs]),
                        "steps": statistics.median(r["inspection_steps"] for r in rs),
                        "time_ms": statistics.median(r["time_ms"] for r in rs),
                        "truncated": sum(1 for r in rs if r["truncated"]), "n": len(rs)})
    return cells, assertions, summary


def _d2(x: Decimal) -> str:
    return f"{x:.2f}"


def _med(x) -> str:
    return str(int(x)) if x == int(x) else f"{x}"


def _header(cells: list[MatrixCell]) -> list[tuple[str, int]]:
    out = []
    for g in (*GROUPS, "all"):
        n = max((c.n for c in cells if c.group == g), default=0)
        out.append((GROUP_LABELS.get(g, "Все"), n))
    return out


def _title(version: dict, cells) -> str:
    n = max((c.n for c in cells if c.group == "all"), default=0)
    return f"Награда политик по группам эпизодов · {n} эпизодов · sha={version['code_version'][:7]}"


def render_matrix_md(cells, assertions, summary, version: dict) -> str:
    head = _header(cells)
    lines = [f"### {_title(version, cells)}", "",
             "Надёжность награды: значение = средняя терминальная награда, (n) = число эпизодов. "
             "oracle — верхняя граница награды, а не агент; «случайная» на чистых получает высокую награду, "
             "если ничего не сдаёт, — это корректно.", "",
             "| Политика | " + " | ".join(f"{h} ({n})" for h, n in head) + " |",
             "| --- |" + " --- |" * len(head)]
    by = {(c.policy, c.group): c for c in cells}
    for s in summary:
        row = []
        for g in (*GROUPS, "all"):
            c = by[(s["policy"], g)]
            row.append("—" if c.mean_reward is None else style.fmt_reward(c.mean_reward))
        lines.append(f"| {LABELS.get(s['policy'], s['policy'])} | " + " | ".join(row) + " |")
    lines += ["", "| Политика | P | R | F1 | Возврат | Шаги (мед.) | truncated |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for s in summary:
        lines.append(f"| {LABELS.get(s['policy'], s['policy'])} | {_d2(s['p'])} | {_d2(s['r'])} | {_d2(s['f1'])} | "
                     f"{style.fmt_reward(s['reward'])} | {_med(s['steps'])} | {s['truncated']} |")
    lines.append("")
    for a in assertions:
        lines.append(f"{'✓' if a.passed else '✗'} {a.text} ({', '.join(a.check_ids)})")
    return "\n".join(lines) + "\n"


def render_timing_md(summary) -> str:
    lines = ["# Время политик (недетерминированно, поэтому вне SVG)", "", "| Политика | Время (мед., мс) |", "| --- | --- |"]
    lines += [f"| {LABELS.get(s['policy'], s['policy'])} | {_med(s['time_ms'])} |" for s in summary]
    return "\n".join(lines) + "\n"


def render_matrix_svg(cells, assertions, summary, version: dict) -> str:
    head = _header(cells)
    by = {(c.policy, c.group): c for c in cells}
    label_w, x0, y0 = 190, 20, 92
    n_rows = len(summary)
    h = y0 + n_rows * CELL_H + 40 + 30 + 4 * 18 + 40 + (n_rows + 1) * 18 + 24
    svg = Svg(960, h, _title(version, cells))
    svg.text(x0, 24, _title(version, cells), style.HEAD, weight="bold")
    svg.text(x0, 44, "надёжность награды: средняя терминальная награда; oracle — верхняя граница, не агент", 12, style.GREY)
    cols = [x0 + label_w + i * CELL_W + (2 if i == 6 else 0) for i in range(7)]
    for (name, n), cx in zip(head, cols):
        svg.text(cx + CELL_W // 2, y0 - 22, name, 12, anchor="middle", weight="bold")
        svg.text(cx + CELL_W // 2, y0 - 8, f"({n})", 12, style.GREY, anchor="middle")
    for k, s in enumerate(summary):
        y = y0 + k * CELL_H
        svg.text(x0, y + 15, LABELS.get(s["policy"], s["policy"]), 12, weight="bold")
        svg.text(x0, y + 29, NOTES.get(s["policy"], "наш агент"), 10, style.GREY)
        for g, cx in zip((*GROUPS, "all"), cols):
            c = by[(s["policy"], g)]
            if c.mean_reward is None:
                svg.rect(cx, y, CELL_W, CELL_H, "#FFFFFF", "#DDDDDD", 1)
                svg.text(cx + CELL_W // 2, y + 23, "—", 12, style.GREY, anchor="middle")
                continue
            bg = style.reward_color(c.mean_reward)
            svg.rect(cx, y, CELL_W, CELL_H, bg, "#FFFFFF", 1, tip=f"{s['policy']} · {g} · n={c.n}")
            svg.text(cx + CELL_W // 2, y + 23, style.fmt_reward(c.mean_reward), 14,
                     style.text_color_on(bg), anchor="middle", weight="bold")
    sep_x = cols[6] - 1
    svg.line(sep_x, y0 - 4, sep_x, y0 + n_rows * CELL_H, style.INK, 2)
    y = y0 + n_rows * CELL_H + 26
    svg.text(x0, y, f"{style.MINUS}1", 12)
    for i, anchor in enumerate(style.RDBU):
        svg.rect(x0 + 24 + i * 40, y - 12, 40, 14, anchor, "#FFFFFF", 1)
    svg.text(x0 + 24 + 9 * 40 + 8, y, "+1   шкала RdBu, число в каждой ячейке; столбец «Все» отделён чертой", 12, style.GREY)
    y += 34
    svg.text(x0, y, "Контрольные утверждения", 12, weight="bold")
    for a in assertions:
        y += 18
        svg.text(x0, y, f"{'✓' if a.passed else '✗'} {a.text}  ({', '.join(a.check_ids)})", 12,
                 style.GREEN if a.passed else style.VERMILION)
    y += 34
    cols_t = [x0, x0 + 200, x0 + 270, x0 + 340, x0 + 420, x0 + 540, x0 + 660]
    for t, cx in zip(("Политика", "P", "R", "F1", "Возврат", "Шаги (мед.)", "truncated"), cols_t):
        svg.text(cx, y, t, 12, weight="bold")
    for s in summary:
        y += 18
        vals = (LABELS.get(s["policy"], s["policy"]), _d2(s["p"]), _d2(s["r"]), _d2(s["f1"]),
                style.fmt_reward(s["reward"]), _med(s["steps"]), str(s["truncated"]))
        for v, cx in zip(vals, cols_t):
            svg.text(cx, y, v, 12)
    return svg.render()
