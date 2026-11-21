"""AuditCheck / AuditReport, scoring and the three renderers (console, JSON, Markdown)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fin_env import canon

WEIGHTS = {"contract": 25, "data": 25, "reward": 25, "paired": 15}
BLOCK_TITLES = {"contract": "Контракт и изоляция", "data": "Данные и эталон", "reward": "Надёжность награды",
                "paired": "Воспроизводимость"}

ASSUMPTIONS = [
    "Все 80 проверок — наша трактовка опубликованных блоков жюри; «20/20 у нас» не означает 20/20 у жюри.",
    "Формат действия: `{\"action\": name, ...params}` (также принимаются `args` и `name/arguments`).",
    "`list_records(limit>50)` и `limit<1` → `BAD_ARGS` и шаг списан (без тихой обрезки).",
    "`submit.episode_id` необязателен; при несовпадении с manifest ответ структурно неверен (−1). Лишние ключи в выводе игнорируются.",
    "Усечение (100 шагов без submit или 60 с) оценивается как submit пустого ответа; награда по формуле (на чистой книге = 0.8).",
    "Шаг с ошибкой считается инспекцией; `submit` не входит в `inspection_steps`, но входит в лимит 100.",
    "Сумма `payment_allocation` — в валюте платежа и считается точно из публичных записей (см. DESIGN.md); τ = 0.",
    "Лишние `evidence_ids` допустимы, только если все существуют и набор ⊇ одного допустимого; иначе вывод — FP.",
    "C-проверки изолированы try/except, а не процессами; C18 идёт параллельно с остальными (флаг `--fast`: лимит 2 с).",
    "M20 проверяет matcher на синтетическом наборе, потому что в сгенерированном эталоне два issue не бывают неразличимыми (I10).",
    "P-проверки сравнивают oracle до/после преобразования с обратным маппингом ID; новые ID намеренно сортируются иначе.",
]


@dataclass(frozen=True)
class AuditCheck:
    check_id: str
    block: str
    title: str
    passed: bool
    blocking: bool
    duration_ms: int
    detail: str


@dataclass(frozen=True)
class AuditReport:
    version: dict
    checks: tuple[AuditCheck, ...]
    diagnostics: dict
    score: dict
    elapsed_s: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


def score(checks) -> dict:
    out: dict = {}
    total = 0.0
    for block, weight in WEIGHTS.items():
        passed = sum(1 for c in checks if c.block == block and c.passed)
        points = weight * passed / 20
        out[block] = points
        out[block + "_passed"] = passed
        total += points
    out["auto_total"] = total
    out["blocking"] = any(c.blocking and not c.passed for c in checks)
    return out


def _fmt(x: float) -> str:
    return f"{x:.1f}"


def render_console(r: AuditReport) -> str:
    v = r.version
    lines = [f"GENESIS SELF-AUDIT sha={v['code_version'][:7]} cfg={v['config_version']} py{v['python']}", ""]
    for block, title in BLOCK_TITLES.items():
        lines.append(f"{title:<20}{r.score[block + '_passed']:>2}/20 → {_fmt(r.score[block])}")
    blocking = [c.check_id for c in r.checks if c.blocking and not c.passed]
    lines += ["", f"Авто-балл: {_fmt(r.score['auto_total'])} / 90  blocking: {', '.join(blocking) or 'none'}  "
              f"время: {r.elapsed_s} с (ожидаемая оценка, не официальная)"]
    failed = [c for c in r.checks if not c.passed]
    for c in failed:
        lines.append(f"  ✗ {c.check_id} {c.title} — {c.detail[:160]}")
    summary = r.diagnostics.get("summary", [])
    if summary:
        lines.append("")
        lines.append("Диагностика: " + " | ".join(f"{s['policy']} R={s['mean_reward']}" for s in summary))
    return "\n".join(lines)


def to_dict(r: AuditReport) -> dict:
    return {
        "version": r.version, "score": r.score, "elapsed_s": r.elapsed_s,
        "checks": [{"check_id": c.check_id, "block": c.block, "title": c.title, "passed": c.passed,
                    "blocking": c.blocking, "duration_ms": c.duration_ms, "detail": c.detail} for c in r.checks],
        "diagnostics": r.diagnostics, "notes": list(r.notes),
    }


def render_json(r: AuditReport, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(to_dict(r), sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_markdown(r: AuditReport, path: Path) -> None:
    v = r.version
    out = ["# Self-audit (ожидаемая оценка по нашей трактовке критериев жюри)", "",
           f"- код: `{v['code_version']}` · конфиги: `{v['config_hash']}` · suite `{v['suite_version']}` · "
           f"python {v['python']} · зависимости: `{v['deps_hash']}`",
           f"- время прогона: {r.elapsed_s} с", "",
           "| Блок | Пройдено | Баллы |", "| --- | --- | --- |"]
    for block, title in BLOCK_TITLES.items():
        out.append(f"| {title} | {r.score[block + '_passed']}/20 | {_fmt(r.score[block])} / {WEIGHTS[block]} |")
    blocking = [c.check_id for c in r.checks if c.blocking and not c.passed]
    out += [f"| **Авто-итог** | | **{_fmt(r.score['auto_total'])} / 90** |", "",
            f"Блокирующие нарушения: {', '.join(blocking) or 'нет'}. Ещё 10 баллов (инженерия) ставит человек.", "",
            "## Проверки", "", "| ID | Блок | Что проверяем | Итог | мс | Детали |", "| --- | --- | --- | --- | --- | --- |"]
    for c in sorted(r.checks, key=lambda c: c.check_id):
        detail = c.detail.replace("|", "/").replace("\n", " ")[:200]
        out.append(f"| {c.check_id} | {c.block} | {c.title} | {'✓' if c.passed else '✗'} | {c.duration_ms} | {detail} |")
    out += ["", "## Допущения и трактовка (читать вместе с отчётом)", ""] + [f"- {a}" for a in ASSUMPTIONS]
    if r.notes:
        out += ["", "## Примечания прогона", ""] + [f"- {n}" for n in r.notes]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
