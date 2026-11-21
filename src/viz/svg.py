"""Mini SVG builder: integer coordinates, fixed attribute order, no dates, no random ids, LF line ends."""
from __future__ import annotations

from xml.sax.saxutils import escape

from . import style


def _attrs(pairs) -> str:
    return "".join(f' {k}="{escape(str(v), {chr(34): "&quot;"})}"' for k, v in pairs if v is not None)


class Svg:
    def __init__(self, width: int, height: int, title: str):
        self.w, self.h, self.title = int(width), int(height), title
        self.parts: list[str] = []

    def rect(self, x, y, w, h, fill="none", stroke=None, sw=None, dash=None, tip=None, rx=None):
        a = _attrs([("x", int(x)), ("y", int(y)), ("width", int(w)), ("height", int(h)), ("rx", rx),
                    ("fill", fill), ("stroke", stroke), ("stroke-width", sw), ("stroke-dasharray", dash)])
        self.parts.append(f"<rect{a}>" + (f"<title>{escape(tip)}</title></rect>" if tip else "</rect>"))

    def text(self, x, y, s, size=style.TEXT, fill=style.INK, anchor=None, weight=None, tip=None):
        a = _attrs([("x", int(x)), ("y", int(y)), ("font-size", size), ("fill", fill), ("text-anchor", anchor),
                    ("font-weight", weight)])
        self.parts.append(f"<text{a}>{escape(s)}" + (f"<title>{escape(tip)}</title>" if tip else "") + "</text>")

    def line(self, x1, y1, x2, y2, stroke=style.INK, sw=1, dash=None):
        a = _attrs([("x1", int(x1)), ("y1", int(y1)), ("x2", int(x2)), ("y2", int(y2)), ("stroke", stroke),
                    ("stroke-width", sw), ("stroke-dasharray", dash)])
        self.parts.append(f"<line{a}></line>")

    def path(self, points, stroke=style.INK, sw=1, dash=None, arrow=False):
        d = "M" + " L".join(f"{int(x)} {int(y)}" for x, y in points)
        a = _attrs([("d", d), ("fill", "none"), ("stroke", stroke), ("stroke-width", sw), ("stroke-dasharray", dash)])
        self.parts.append(f"<path{a}></path>")
        if arrow:
            x, y = points[-1]
            self.parts.append(f'<path d="M{int(x) - 6} {int(y) - 4} L{int(x)} {int(y)} L{int(x) - 6} {int(y) + 4}" '
                              f'fill="none" stroke="{stroke}" stroke-width="{sw}"></path>')

    def render(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" font-family="{style.FONT}" role="img">')
        body = [f"<title>{escape(self.title)}</title>",
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#FFFFFF"></rect>', *self.parts]
        return "\n".join([head, *body, "</svg>"]) + "\n"
