"""`python -m viz --episodes episodes/dev --audit reports/audit.json --out reports/viz`"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from fin_env import canon

from . import book_diff, causal_graph, policy_matrix


def _write(path: Path, text: str, index: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text(path, text)
    index.append(path)


def episode_roots(dirs: list[Path]) -> list[Path]:
    roots = []
    for d in dirs:
        idx = canon.read_json(d / "index.json")
        roots += [d / e["episode_id"] for e in idx["episodes"]]
    return roots


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m viz")
    ap.add_argument("--episodes", type=Path, nargs="+", default=[Path("episodes/dev")])
    ap.add_argument("--audit", type=Path, default=Path("reports/audit.json"))
    ap.add_argument("--out", type=Path, default=Path("reports/viz"))
    ap.add_argument("--assets", type=Path, default=Path("assets"))
    ap.add_argument("--svg-for", default="auto", help="'auto' or comma list of episode ids")
    a = ap.parse_args(argv)
    out, files = a.out, []
    audit = canon.read_json(a.audit)
    version = audit["version"]
    cells, assertions, summary = policy_matrix.build_matrix(audit)
    _write(out / "policy_matrix.svg", policy_matrix.render_matrix_svg(cells, assertions, summary, version), files)
    _write(out / "policy_matrix.md", policy_matrix.render_matrix_md(cells, assertions, summary, version), files)
    _write(out / "policy_timing.md", policy_matrix.render_timing_md(summary), files)
    roots = episode_roots(a.episodes)
    wanted = set(a.svg_for.split(",")) if a.svg_for != "auto" else set()
    diff_svg = graph_svg = None
    top3: dict[str, tuple] = {}
    for root in roots:
        prov = canon.read_json(root / "sealed" / "provenance.json")
        if prov["split"] == "closed":
            raise SystemExit("viz refuses to run on closed episodes")
        eid = prov["episode_id"]
        cards = book_diff.group_cards(book_diff.build_diff_cards(root)) if prov["mutations"] else []
        all_cards = book_diff.build_diff_cards(root)
        by_issue = {c.issue_id: c for c in book_diff.group_cards(all_cards)}
        for card in book_diff.group_cards(all_cards):
            ids = [m.issue_id for m in card.members] or [card.issue_id]
            for iid in ids:
                _write(out / "diff" / eid / f"{iid}.md", book_diff.render_diff_md([card]), files)
            auto = diff_svg is None and (bool(card.members) or card.group_id is None)
            if (a.svg_for == "auto" and auto and (card.members or diff_svg is None)) or eid in wanted:
                svg = book_diff.render_diff_svg(card)
                _write(out / "diff" / eid / f"{ids[0]}.svg", svg, files)
                if diff_svg is None or card.members:
                    diff_svg = svg
        if not all_cards:
            from .book_diff import DiffCard  # noqa: F401
            _write(out / "diff" / eid / "clean.md",
                   f"### {eid} · чистый эпизод\n\nΣDr = ΣCr ✓ · 0 ошибок в truth · "
                   f"двойников: {sum(1 for m in prov['mutations'] if not m['is_error'])} (detect = 0, I11 ✓)\n", files)
        chains = causal_graph.build_chains(root)
        problems = causal_graph.lint_mermaid(chains)
        if problems:
            raise SystemExit(f"mermaid lint: {problems}")
        header = f"эпизод {eid} · {sum(c.is_error for c in chains)} ошибок/групп · {sum(not c.is_error for c in chains)} двойников"
        _write(out / "causal" / f"{eid}.mmd", causal_graph.render_mermaid(chains, header), files)
        md = [f"## Граф причинности · {header}", ""]
        for ch in chains:
            md += ["```mermaid", causal_graph.render_mermaid([ch]).rstrip(), "```", ""]
        _write(out / "causal" / f"{eid}.md", "\n".join(md), files)
        _write(out / "causal" / f"{eid}.svg", causal_graph.render_graph_svg(chains, header), files)
        for ch in chains:
            kind = "twin" if not ch.is_error else "group" if ch.chain_id.startswith("grp_") else "single"
            top3.setdefault(kind, (eid, ch))
    if len(top3) == 3:
        order = [top3[k] for k in ("single", "group", "twin")]
        chains = [c for _, c in order]
        _write(out / "causal" / "README_top3.md", "\n".join(
            [f"### {c.title} (эпизод {e})\n\n```mermaid\n{causal_graph.render_mermaid([c]).rstrip()}\n```\n" for e, c in order]), files)
        graph_svg = causal_graph.render_graph_svg(chains, "Граф причинности: ошибка · взаимодействие · двойник")
        _write(out / "causal" / "top3.svg", graph_svg, files)
    lines = ["# Индекс визуалов", "", "| файл | sha256 |", "| --- | --- |"]
    for f in sorted(set(files)):
        lines.append(f"| {f.relative_to(out).as_posix()} | {canon.sha256_file(f)} |")
    canon.write_text(out / "index.md", "\n".join(lines) + "\n")
    a.assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / "policy_matrix.svg", a.assets / "policy_matrix.svg")
    if graph_svg:
        canon.write_text(a.assets / "causal_graph.svg", graph_svg)
    if diff_svg:
        canon.write_text(a.assets / "diff_card.svg", diff_svg)
    print(f"viz: {len(files)} files -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
