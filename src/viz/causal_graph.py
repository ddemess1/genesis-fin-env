"""Visual 1: causal graph per mutation chain. One model (Chain/Node/Edge), two outputs: Mermaid and grid SVG."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fin_env import canon, publicio

from . import style
from .svg import Svg

Stage = Literal["source", "mutator", "diff", "affected", "evidence", "truth"]
STAGES = ("source", "mutator", "diff", "affected", "evidence", "truth")
STAGE_TITLES = ("ЧИСТАЯ ЗАПИСЬ", "МУТАТОР", "DIFF", "AFFECTED_IDS", "ДОКАЗАТЕЛЬСТВА", "TRUTH.JSON")
CLASS_DEFS = [
    "classDef clean stroke:#999999", "classDef mut fill:#FCEBC8,stroke:#E69F00",
    "classDef err fill:#FBE3D6,stroke:#D55E00,stroke-width:2px", "classDef ev fill:#E0F2EC,stroke:#009E73",
    "classDef truth fill:#F5E3EE,stroke:#CC79A7", "classDef twin stroke:#0072B2,stroke-dasharray:4 3",
]


class VizError(Exception):
    pass


@dataclass(frozen=True)
class Node:
    node_id: str
    stage: Stage
    label: tuple[str, ...]
    full_label: str
    cls: Literal["clean", "mut", "err", "twin", "ev", "truth"]


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    dashed: bool


@dataclass(frozen=True)
class Chain:
    chain_id: str
    is_error: bool
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    title: str = ""


def _more(ids: list[str], limit: int = 3) -> str:
    shown = ", ".join(style.trunc_id(i) for i in ids[:limit])
    return shown + (f" … ещё {len(ids) - limit}" if len(ids) > limit else "")


def _param_line(rec: dict) -> str:
    p = rec["params"]
    if rec["kind"] == "TWIN_SUBSCRIPTION":
        return f"+{p['shift_days']}d"
    if "allocated_share_pct" in p:
        return f"в 1200 ушло {p['allocated_share_pct']}%"
    if "shift_days" in p and "shift_minutes" in p:
        return f"shift {p['shift_days']}d {p['shift_minutes']}m"
    if "variant" in p:
        return f"курс {p['variant'].split(':')[-1]}" if rec["kind"] == "WRONG_FX_DATE" else f"rate {p['variant']}"
    if "shift_days" in p:
        return f"shift {p['shift_days']}d"
    return ", ".join(f"{k}={v}" for k, v in sorted(p.items())[:2] if k not in ("against", "distinguishing_feature"))


def _diff_label(op: dict, pub, base: str) -> str:
    sign = {"add": "+", "modify": "~", "remove": "−"}[op["op"]]
    snap = op["after"] or op["before"]
    pid = style.trunc_id(pub(op["iid"]))
    if op["table"] == "ledger":
        side = "Dr" if snap["debit_minor"] else "Cr"
        return f"{sign} {pid} · {side} {snap['account']}"
    return f"{sign} {pid}"


def _evidence_lines(sets: list[list[str]]) -> tuple[str, ...]:
    lines: list[str] = []
    for k, s in enumerate(sets):
        text = " + ".join(style.trunc_id(x) for x in s)
        lines.append(("✓ " if k == 0 else "или ") + text)
    return tuple(lines)


def build_chains(episode_dir: Path) -> list[Chain]:
    root = Path(episode_dir)
    prov = canon.read_json(root / "sealed" / "provenance.json")
    truth = canon.read_json(root / "sealed" / "truth.json")
    raw = publicio.load_raw(root / "public")
    known = publicio.known_ids(raw)
    pub_invoices = {i["invoice_id"]: i for i in raw["invoices"]}
    pub_payments = {p["payment_id"]: p for p in raw["payments"]}
    id_map, base = prov["id_map"], prov["config"]["base_currency"]
    pub = lambda x: id_map.get(x, x)  # noqa: E731
    issues = {i["mutation_id"]: i for i in truth["issues"]}
    snapshots = {}
    for m in prov["mutations"]:
        for op in m["diff"]:
            if op["after"]:
                snapshots[op["iid"]] = (op["table"], op["after"])

    def source_node(cid, rec):
        t = rec["target_iids"][0]
        lines = [style.trunc_id(pub(t))]
        snap = snapshots.get(t)
        if snap and snap[0] == "invoices":
            lines.append(style.fmt_money(snap[1]["total_minor"], snap[1]["currency"]))
        elif snap and snap[0] == "payments":
            lines.append(style.fmt_money(snap[1]["amount_minor"], snap[1]["currency"]))
        elif pub(t) in pub_invoices:
            i = pub_invoices[pub(t)]
            lines.append(style.fmt_money(i["total_minor"], i["currency"]))
        elif pub(t) in pub_payments:
            p = pub_payments[pub(t)]
            lines.append(f"{style.fmt_money(p['amount_minor'], p['currency'])} · {p['timestamp'][5:10]} {p['timestamp'][11:16]}")
        return Node(f"{cid}_source_0", "source", tuple(lines), pub(t), "clean")

    def mut_node(cid, k, rec, twin):
        return Node(f"{cid}_mutator_{k}", "mutator", (rec["kind"], _param_line(rec)),
                    rec["kind"], "mut")

    def build(cid, recs, is_error, title):
        nodes: list[Node] = []
        edges: list[Edge] = []
        add = lambda n: nodes.append(n) or n.node_id  # noqa: E731
        src = add(source_node(cid, recs[0]))
        diff_ids: dict[tuple, str] = {}
        d_count = 0
        for k, rec in enumerate(recs):
            twin = not is_error
            mid = add(mut_node(cid, k, rec, twin))
            edges.append(Edge(src, mid, twin))
            mine = []
            for op in rec["diff"]:
                key = (op["table"], op["iid"])
                if key not in diff_ids:
                    label = _diff_label(op, pub, base)
                    diff_ids[key] = add(Node(f"{cid}_diff_{d_count}", "diff", (label,), pub(op["iid"]),
                                             "twin" if twin else "err"))
                    d_count += 1
                mine.append(diff_ids[key])
                edges.append(Edge(mid, diff_ids[key], twin))
            if twin:
                feat = rec["params"].get("distinguishing_feature")
                if not feat:
                    raise VizError(f"look-alike {rec['mutation_id']} has no distinguishing_feature")
                tid = add(Node(f"{cid}_truth_0", "truth", ("○ не ошибка", feat), "not an error: " + feat, "twin"))
                edges.append(Edge(mine[-1], tid, True))
                continue
            affected = sorted(pub(x) for x in rec["affected_iids"])
            aid = add(Node(f"{cid}_affected_{k}", "affected", ("affected", _more(affected)),
                           ", ".join(affected), "err"))
            for d in mine:
                edges.append(Edge(d, aid, False))
            sets = sorted(sorted(pub(x) for x in es) for es in rec["evidence_sets"])
            for x in (i for s in sets for i in s):
                if x not in known:
                    raise VizError(f"evidence id {x} is not in public files")
            eid = add(Node(f"{cid}_evidence_{k}", "evidence", _evidence_lines(sets),
                           " | ".join(" + ".join(s) for s in sets), "ev"))
            issue = issues[rec["mutation_id"]]
            tid = add(Node(f"{cid}_truth_{k}", "truth", (f"{issue['issue_id']} ▲ {issue['type']}",
                           style.fmt_money(issue["expected_amount_minor"], issue["currency"])),
                           f"{issue['issue_id']} {issue['type']} {issue['expected_amount_minor']} {issue['currency']}", "truth"))
            edges += [Edge(aid, eid, False), Edge(eid, tid, False)]
        return Chain(cid, is_error, tuple(nodes), tuple(edges), title)

    chains: list[Chain] = []
    groups: dict[str, list[dict]] = {}
    for rec in prov["mutations"]:
        if rec["is_error"] and rec["group_id"]:
            groups.setdefault(rec["group_id"], []).append(rec)
    done: set[str] = set()
    errs = sorted((r for r in prov["mutations"] if r["is_error"]), key=lambda r: issues[r["mutation_id"]]["issue_id"])
    for rec in errs:
        gid = rec["group_id"]
        if gid:
            if gid in done:
                continue
            done.add(gid)
            kinds = "+".join(r["kind"] for r in groups[gid])
            chains.append(build(f"grp_{gid[1:]}", groups[gid], True, f"grp_{gid[1:]} · {kinds}"))
        else:
            iss = issues[rec["mutation_id"]]
            chains.append(build(iss["issue_id"], [rec], True, f"{iss['issue_id']} · {iss['type']}"))
    twins = sorted((r for r in prov["mutations"] if not r["is_error"]),
                   key=lambda r: (r["kind"], pub(r["affected_iids"][0])))
    for n, rec in enumerate(twins, 1):
        chains.append(build(f"tw_{n:02d}", [rec], False, f"tw_{n:02d} · законный двойник"))
    return chains


# ---- Mermaid ----------------------------------------------------------------------------------
def _esc(s: str) -> str:
    return s.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def _shape(n: Node) -> str:
    text = "<br/>".join(_esc(x) for x in n.label)
    return {"mutator": f'{{{{"{text}"}}}}', "evidence": f'[/"{text}"/]', "truth": f'(["{text}"])'}.get(
        n.stage, f'["{text}"]')


def render_mermaid(chains: list[Chain], header: str = "") -> str:
    lines = ["flowchart LR"] + [f"    {c}" for c in CLASS_DEFS]
    for ch in chains:
        lines += ["", f'    subgraph {ch.chain_id}["{_esc(ch.title)}"]']
        lines += [f"        {n.node_id}{_shape(n)}:::{n.cls}" for n in ch.nodes]
        lines += [f"        {e.src} {'-.->' if e.dashed else '-->'} {e.dst}" for e in ch.edges]
        lines.append("    end")
    return "\n".join(lines) + "\n"


def lint_mermaid(chains: list[Chain]) -> list[str]:
    """Mini linter: unique node ids, edges on existing nodes, safe ids."""
    import re
    problems, ids = [], set()
    for ch in chains:
        for n in ch.nodes:
            if n.node_id in ids or not re.fullmatch(r"[a-z0-9_]+", n.node_id):
                problems.append(f"bad or duplicate id {n.node_id}")
            ids.add(n.node_id)
    for ch in chains:
        for e in ch.edges:
            if e.src not in ids or e.dst not in ids:
                problems.append(f"dangling edge {e.src}->{e.dst}")
    return problems


# ---- grid SVG ---------------------------------------------------------------------------------
def render_graph_svg(chains: list[Chain], header: str) -> str:
    gap_x, gap_y, pad = 36, 24, 20
    widths = [0] * 6
    for ch in chains:
        for n in ch.nodes:
            w = max(len(x) for x in n.label) * style.CHAR_W + 16
            widths[STAGES.index(n.stage)] = max(widths[STAGES.index(n.stage)], w)
    xs = [pad]
    for w in widths[:-1]:
        xs.append(xs[-1] + max(w, 60) + gap_x)
    total_w = xs[-1] + max(widths[-1], 60) + pad
    pos: dict[str, tuple[int, int, int, int]] = {}
    y = 84
    row_tops = []
    for ch in chains:
        row_tops.append((ch, y))
        stage_y = {s: y for s in STAGES}
        bottom = y
        for n in ch.nodes:
            si = STAGES.index(n.stage)
            h = 14 * len(n.label) + 12
            pos[n.node_id] = (xs[si], stage_y[n.stage], max(widths[si], 60), h)
            stage_y[n.stage] += h + 10
            bottom = max(bottom, stage_y[n.stage])
        y = bottom + gap_y + 18
    svg = Svg(total_w, y + 70, header)
    svg.text(pad, 24, header, style.HEAD, weight="bold")
    for t, x, w in zip(STAGE_TITLES, xs, widths):
        svg.text(x, 56, t, 11, style.GREY, weight="bold")
    for ch, top in row_tops:
        svg.text(pad, top - 8, ch.title, 12, style.INK, weight="bold")
        for e in ch.edges:
            x1, y1, w1, h1 = pos[e.src]
            x2, y2, _, h2 = pos[e.dst]
            sx, sy, ex, ey = x1 + w1, y1 + h1 // 2, x2, y2 + h2 // 2
            mx = (sx + ex) // 2
            svg.path([(sx, sy), (mx, sy), (mx, ey), (ex, ey)], style.BLUE if e.dashed else "#444444",
                     1 if e.dashed else 2, "4 3" if e.dashed else None, arrow=True)
        for n in ch.nodes:
            x, ny, w, h = pos[n.node_id]
            fill, stroke, sw, dash = style.CLASSES[n.cls]
            svg.rect(x, ny, w, h, fill, stroke, sw, dash, tip=n.full_label, rx=6 if n.stage == "truth" else None)
            for k, line in enumerate(n.label):
                svg.text(x + 8, ny + 18 + 14 * k, line, 12, style.INK)
    ly = y + 20
    lx = pad
    for cls, name in (("clean", "чистая запись"), ("mut", "мутатор"), ("err", "ошибка / diff"), ("ev", "доказательства"),
                      ("truth", "строка truth"), ("twin", "○ двойник")):
        fill, stroke, sw, dash = style.CLASSES[cls]
        svg.rect(lx, ly, 26, 16, fill, stroke, sw, dash)
        svg.text(lx + 32, ly + 12, name, 11)
        lx += 32 + len(name) * 7 + 22
    return svg.render()
