"""wiresheet: system wiring sheets as clean SVG, from a few lines of Python.

Each sheet is a fixed grid. Columns run left to right in reading order (sources on the
left, loads on the right); boxes stack top to bottom in the order you list them. A box
shows a title, a model line, an optional photo, one row per port, and an optional note.
A wire leaves a port horizontally, runs down or up in its own vertical track in the
channel between two columns, and enters the next port horizontally. Longer runs take the
track nearest the source so wires never cross each other. Ports shared by several wires
get junction dots. A wire that has to skip a column dips just under the boxes of that
column. Every sheet is placed on a fixed page (A3 landscape by default) with a frame and
a title block.

Minimal use:

    from wiresheet import Sheet, RED, BLK

    s = Sheet("01-power", "Power", sheet="1 of 1", project="My robot",
              columns=[["Battery"], ["Fuse box"], ["Motor", "Lamp"]])
    s.dev("Battery", "12 V 20 Ah", None, ["+", "-"])
    s.dev("Fuse box", "4-way", None, ["IN +", "IN -", "OUT 1 +", "OUT 1 -", "OUT 2 +", "OUT 2 -"])
    s.dev("Motor", "", None, ["+", "-"])
    s.dev("Lamp", "", None, ["+", "-"])
    s.pair("Battery", ["+", "-"], "Fuse box", ["IN +", "IN -"])
    s.pair("Fuse box", ["OUT 1 +", "OUT 1 -"], "Motor", ["+", "-"], "10 A")
    s.pair("Fuse box", ["OUT 2 +", "OUT 2 -"], "Lamp", ["+", "-"], "2 A")
    s.render()            # writes 01-power.svg, .png, .pdf

Requires rsvg-convert (librsvg) on PATH for PNG and PDF output, and pypdf to merge sheets; SVG needs nothing.
"""
from __future__ import annotations

import base64
import datetime as _dt
import os
import shutil
import subprocess

__version__ = "0.3.1"

# ---------------------------------------------------------------- wire colours
RED, BLK, BLU, YEL, GRN, ORG = "#c00000", "#111111", "#1f5fbf", "#d9a800", "#1e9e3e", "#e07000"
GRY, LGRY, WHT, PUR, BRN = "#808080", "#b5b5b5", "#dddddd", "#7a3fa0", "#7a4a12"

# ---------------------------------------------------------------- page formats, landscape, mm
PAGES = {"A3": (420, 297), "A4": (297, 210), "A2": (594, 420), "Letter": (279.4, 215.9), "Tabloid": (431.8, 279.4)}
PX_PER_MM = 4


class Style:
    """Box geometry and type sizes in drawing pixels. Change on the class to affect every sheet,
    or pass an instance to Sheet(style=...)."""
    title_h, type_h, port_h, note_h, img_pad = 27, 18, 25, 18, 6
    f_title, f_type, f_port, f_note, f_label = 14.5, 11, 13.5, 10.5, 10.5
    margin, v_space = 20, 36
    track_offset, track_pitch = 18, 10        # first track distance from the box, spacing between tracks
    min_gap = 120                             # minimum channel width between columns
    max_scale = 1.35                          # never blow a small drawing up beyond this on the page
    box_fill, title_fill, stroke = "white", "#eeeeee", "#333333"


def _b64(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}[ext]
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def _esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Sheet:
    def __init__(self, fname: str, title: str, sheet: str = "", columns=(), *, project: str = "",
                 rev: str = "A", date: str | None = None, sub: str = "", width: int = 260, gap: int | None = None,
                 page: str = "A3", img_dir: str = "img", out_dir: str = ".", style: Style | None = None):
        self.fname, self.title, self.sheet, self.project, self.rev = fname, title, sheet, project, rev
        self.date = date if date is not None else _dt.date.today().isoformat()
        self.sub, self.columns, self.W, self.gap_override = sub, [list(c) for c in columns], width, gap
        self.page, self.img_dir, self.out_dir = page, img_dir, out_dir
        self.st = style or Style()
        self.devs: dict[str, dict] = {}
        self.wires: list[dict] = []

    # ---------------------------------------------------------------- data entry
    def dev(self, name: str, type_: str = "", img: str | None = None, ports=(), note: str = "", imgh: int = 80,
            offrobot: bool = False, link: str | None = None):
        """Add a box. `ports` are the labels printed on the device, top to bottom. `img` is a file in img_dir.
        `offrobot=True` draws the box dashed (external equipment). `link` is a URL: the picture becomes
        clickable in the SVG and gets a link annotation in the PDF; a box without a picture links its title bar."""
        self.devs[name] = dict(type=type_, img=img, ports=list(ports), note=note, imgh=imgh, off=offrobot, link=link)

    def wire(self, a, b, color: str = BLK, label: str = "", width: float = 2.5, dashed: bool = False):
        """One conductor from (box, port) to (box, port)."""
        self.wires.append(dict(a=tuple(a), b=tuple(b), color=color, label=label, width=width, dashed=dashed))

    def pair(self, ad, ap, bd, bp, label: str = "", width: float = 2.5, colors=(RED, BLK)):
        """Several conductors between the same two boxes: ports listed in parallel, colours in order.
        The label goes on the first conductor only."""
        for pa, pb, c, lab in zip(ap, bp, colors, (label, *[""] * (len(ap) - 1))):
            self.wire((ad, pa), (bd, pb), c, lab, width)

    # ---------------------------------------------------------------- geometry
    def node_h(self, d) -> float:
        st = self.st
        h = st.title_h + 4
        if d["type"]: h += st.type_h
        if d["img"]: h += d["imgh"] + 2 * st.img_pad
        h += st.port_h * len(d["ports"])
        if d["note"]: h += st.note_h
        return h

    def col_of(self, name: str) -> int:
        for c, col in enumerate(self.columns):
            if name in col: return c
        raise KeyError(f"{name!r} is not in any column of sheet {self.fname}")

    def layout(self):
        st = self.st
        for col in self.columns:
            for n in col:
                if n not in self.devs: raise KeyError(f"box {n!r} is in the columns but has no dev() line")
        ncols = len(self.columns)
        counts = [0] * (ncols + 1)
        for w in self.wires:
            ca, cb = self.col_of(w["a"][0]), self.col_of(w["b"][0])
            if ca != cb: counts[min(ca, cb) + 1] += 1
        self.gap = self.gap_override or max(st.min_gap, 2 * st.track_offset + st.track_pitch * max(counts) + 20)
        self.col_x = [st.margin + 60 + c * (self.W + self.gap) for c in range(ncols)]
        heights = [sum(self.node_h(self.devs[n]) for n in col) + st.v_space * (len(col) - 1) for col in self.columns]
        H = max(heights)
        self.pos = {}
        for c, col in enumerate(self.columns):
            y = st.margin + (H - heights[c]) / 2
            for n in col:
                self.pos[n] = (self.col_x[c], y)
                y += self.node_h(self.devs[n]) + st.v_space
        self.width = self.col_x[-1] + self.W + st.margin + 60
        self.height = 2 * st.margin + H

    def port_y(self, name: str, port: str) -> float:
        st = self.st
        d = self.devs[name]; x, y = self.pos[name]
        if port not in d["ports"]: raise KeyError(f"box {name!r} has no port {port!r}; ports are {d['ports']}")
        off = st.title_h + 4 + (st.type_h if d["type"] else 0) + (d["imgh"] + 2 * st.img_pad if d["img"] else 0)
        return y + off + st.port_h * d["ports"].index(port) + st.port_h / 2

    def col_bottom(self, c: int) -> float:
        return max(self.pos[n][1] + self.node_h(self.devs[n]) for n in self.columns[c])

    # ---------------------------------------------------------------- svg pieces
    def node_svg(self, name: str) -> str:
        st = self.st
        d = self.devs[name]; x, y = self.pos[name]; W = self.W; h = self.node_h(d)
        dash = ' stroke-dasharray="6,4"' if d["off"] else ""
        link = d.get("link")
        o = [f'<rect x="{x}" y="{y}" width="{W}" height="{h}" fill="{st.box_fill}" stroke="{st.stroke}" stroke-width="1.2"{dash}/>']
        title = (f'<rect x="{x}" y="{y}" width="{W}" height="{st.title_h}" fill="{st.title_fill}" stroke="{st.stroke}" stroke-width="1.2"{dash}/>\n'
                 f'<text x="{x + W/2}" y="{y + 18.5}" text-anchor="middle" font-size="{st.f_title}" font-weight="bold">{_esc(name)}</text>')
        if link and not d["img"]:                       # no picture: the title bar carries the link
            self.link_rects.append((link, x, y, W, st.title_h))
            title = f'<a href="{_esc(link)}" target="_blank">{title}</a>'
        o.append(title)
        cy = y + st.title_h + 4
        if d["type"]:
            o.append(f'<text x="{x + W/2}" y="{cy + 13}" text-anchor="middle" font-size="{st.f_type}" fill="#444">{_esc(d["type"])}</text>')
            cy += st.type_h
        if d["img"]:
            src = _b64(os.path.join(self.img_dir, d["img"]))
            img = f'<image x="{x + 12}" y="{cy + st.img_pad}" width="{W - 24}" height="{d["imgh"]}" href="{src}" preserveAspectRatio="xMidYMid meet"/>'
            if link:                                     # the picture is the link
                self.link_rects.append((link, x + 12, cy + st.img_pad, W - 24, d["imgh"]))
                img = f'<a href="{_esc(link)}" target="_blank">{img}</a>'
            o.append(img)
            cy += d["imgh"] + 2 * st.img_pad
        for p in d["ports"]:
            o.append(f'<rect x="{x}" y="{cy}" width="{W}" height="{st.port_h}" fill="none" stroke="#aaa" stroke-width="0.8"/>')
            o.append(f'<text x="{x + 9}" y="{cy + 17}" font-size="{st.f_port}">{_esc(p)}</text>')
            cy += st.port_h
        if d["note"]:
            o.append(f'<text x="{x + W/2}" y="{cy + 13}" text-anchor="middle" font-size="{st.f_note}" fill="#555">{_esc(d["note"])}</text>')
        return "\n".join(o)

    def wires_svg(self) -> str:
        st, W = self.st, self.W
        chans: dict[tuple, list] = {}
        bypass: list[tuple] = []
        for w in self.wires:
            (ad, ap), (bd, bp) = w["a"], w["b"]
            ca, cb = self.col_of(ad), self.col_of(bd)
            if ca == cb:                                                   # same column: loop on the west side
                chans.setdefault(("w", ca), []).append(dict(w=w, src=(ad, ap), dst=(bd, bp),
                                                            ys=self.port_y(ad, ap), yd=self.port_y(bd, bp)))
                continue
            if ca > cb: (ad, ap), (bd, bp), ca, cb = (bd, bp), (ad, ap), cb, ca   # always route left to right
            ys, yd = self.port_y(ad, ap), self.port_y(bd, bp)
            if cb == ca + 1:                                               # neighbouring columns
                chans.setdefault(("f", ca), []).append(dict(w=w, src=(ad, ap), dst=(bd, bp), ys=ys, yd=yd))
            else:                                                          # skips columns: dip under them
                by = max(self.col_bottom(c) for c in range(ca + 1, cb)) + 26 + 12 * len(bypass)
                e1 = dict(w=w, src=(ad, ap), dst=None, ys=ys, yd=by)
                e2 = dict(w=w, src=None, dst=(bd, bp), ys=by, yd=yd)
                chans.setdefault(("f", ca), []).append(e1)
                chans.setdefault(("f", cb - 1), []).append(e2)
                bypass.append((e1, e2))
        # one vertical track per wire in a channel; the longest run sits nearest the source
        for (kind, c), items in chans.items():
            items.sort(key=lambda e: -abs(e["ys"] - e["yd"]))
            for i, e in enumerate(items):
                if kind == "f":
                    e["xs"], e["xd"] = self.col_x[c] + W, self.col_x[c + 1]
                    e["xt"] = e["xs"] + st.track_offset + st.track_pitch * i
                else:
                    e["xs"] = e["xd"] = self.col_x[c]
                    e["xt"] = e["xs"] - st.track_offset - st.track_pitch * i
        paths, dots, labels, stubs = [], [], [], {}

        def stroke(w):
            dash = ' stroke-dasharray="8,5"' if w["dashed"] else ""
            return f'fill="none" stroke="{w["color"]}" stroke-width="{w["width"]}" stroke-linejoin="round"{dash}'

        def label(w, lx, ly):
            tw = 6 * len(w["label"]) + 8
            labels.append(f'<rect x="{lx - tw/2}" y="{ly - 11}" width="{tw}" height="14" fill="white" fill-opacity="0.9"/>'
                          f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="{st.f_label}" fill="#444">{_esc(w["label"])}</text>')

        done = set()
        for items in chans.values():
            for e in items:
                w = e["w"]
                if e["src"] and e["dst"]:
                    paths.append(f'<path d="M {e["xs"]} {e["ys"]} H {e["xt"]} V {e["yd"]} H {e["xd"]}" {stroke(w)}/>')
                    stubs.setdefault(e["src"], []).append((e["xt"], e["ys"], w["color"], e["xs"]))
                    stubs.setdefault(e["dst"], []).append((e["xt"], e["yd"], w["color"], e["xd"]))
                    if w["label"]:
                        if abs(e["xt"] - e["xs"]) >= abs(e["xd"] - e["xt"]): label(w, (e["xs"] + e["xt"]) / 2, e["ys"] - 6)
                        else: label(w, (e["xt"] + e["xd"]) / 2, e["yd"] - 6)
                elif id(w) not in done:
                    done.add(id(w))
                    e1, e2 = next(b for b in bypass if b[0]["w"] is w)
                    paths.append(f'<path d="M {e1["xs"]} {e1["ys"]} H {e1["xt"]} V {e1["yd"]} H {e2["xt"]} V {e2["yd"]} H {e2["xd"]}" {stroke(w)}/>')
                    stubs.setdefault(e1["src"], []).append((e1["xt"], e1["ys"], w["color"], e1["xs"]))
                    stubs.setdefault(e2["dst"], []).append((e2["xt"], e2["yd"], w["color"], e2["xd"]))
                    if w["label"]: label(w, (e1["xt"] + e2["xt"]) / 2, e1["yd"] - 6)
        for (node, port), lst in stubs.items():                            # junction dots on shared ports
            if len(lst) < 2: continue
            px = lst[0][3]
            far = max(lst, key=lambda t: abs(t[0] - px))
            for xt, y, color, _ in lst:
                if (xt, y) != (far[0], far[1]):
                    dots.append(f'<circle cx="{xt}" cy="{y}" r="3.8" fill="{color}"/>')
        return "\n".join(paths + dots + labels)

    # ---------------------------------------------------------------- page
    def svg(self) -> str:
        """The finished page as an SVG string."""
        self.layout()
        self.link_rects = []
        body = [self.wires_svg()] + [self.node_svg(n) for n in self.devs]
        pw_mm, ph_mm = PAGES[self.page]
        PW, PH = round(pw_mm * PX_PER_MM), round(ph_mm * PX_PER_MM)
        fx, fy, fw, fh = 24, 24, PW - 48, PH - 48
        tb_h, tb_w = 64, min(760, fw - 40)
        ax, ay, aw, ah = fx + 16, fy + 16, fw - 32, fh - 32 - tb_h
        sc = min(aw / self.width, ah / self.height, self.st.max_scale)
        ox = ax + (aw - self.width * sc) / 2
        oy = ay + (ah - self.height * sc) / 2
        k = (pw_mm * 72 / 25.4) / PW                      # page px -> PDF points
        self.pdf_links = [dict(url=u, x1=(ox + lx * sc) * k, x2=(ox + (lx + lw) * sc) * k,
                               y1=(PH - (oy + (ly + lh) * sc)) * k, y2=(PH - (oy + ly * sc)) * k)
                          for (u, lx, ly, lw, lh) in self.link_rects]
        tbx, tby = fx + fw - tb_w, fy + fh - tb_h
        cells = [(0, tb_w - 360, "", self.title, 19, True), (tb_w - 360, 120, "sheet", self.sheet, 15, False),
                 (tb_w - 240, 80, "rev", self.rev, 15, False), (tb_w - 160, 160, "date", self.date, 15, False)]
        tb = [f'<rect x="{tbx}" y="{tby}" width="{tb_w}" height="{tb_h}" fill="white" stroke="#333" stroke-width="1.5"/>']
        for cx, cw, head, val, fs, bold in cells:
            x = tbx + cx
            tb.append(f'<line x1="{x}" y1="{tby}" x2="{x}" y2="{tby + tb_h}" stroke="#333" stroke-width="1"/>')
            if head:
                tb.append(f'<text x="{x + 10}" y="{tby + 20}" font-size="10" fill="#666">{head}</text>')
            weight = ' font-weight="bold"' if bold else ""
            tb.append(f'<text x="{x + 10}" y="{tby + 44}" font-size="{fs}"{weight}>{_esc(val)}</text>')
        foot = "  ·  ".join(t for t in (self.project, self.sub) if t)
        if foot:
            tb.append(f'<text x="{tbx - 14}" y="{tby + tb_h - 12}" text-anchor="end" font-size="11" fill="#666">{_esc(foot)}</text>')
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw_mm}mm" height="{ph_mm}mm" viewBox="0 0 {PW} {PH}" '
                 f'font-family="Helvetica, Arial, sans-serif">',
                 f'<rect x="0" y="0" width="{PW}" height="{PH}" fill="white"/>',
                 f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="none" stroke="#333" stroke-width="1.5"/>',
                 f'<g transform="translate({ox:.1f},{oy:.1f}) scale({sc:.4f})">', *body, '</g>', *tb, '</svg>']
        return "\n".join(parts)

    def render(self, formats=("svg", "png", "pdf"), png_scale: float = 2.0) -> list[str]:
        """Write the page. Returns the list of files written. PNG and PDF need rsvg-convert."""
        os.makedirs(self.out_dir, exist_ok=True)
        base = os.path.join(self.out_dir, self.fname)
        svg_path = base + ".svg"
        open(svg_path, "w").write(self.svg())
        written = [svg_path]
        wanted = [f for f in formats if f != "svg"]
        if wanted:
            if not shutil.which("rsvg-convert"):
                raise RuntimeError("rsvg-convert not found: install librsvg (brew install librsvg / apt install librsvg2-bin) "
                                   "or call render(formats=('svg',))")
            if "png" in wanted:
                subprocess.run(["rsvg-convert", "-z", str(png_scale), "-b", "white", "-o", base + ".png", svg_path], check=True)
                written.append(base + ".png")
            if "pdf" in wanted:
                subprocess.run(["rsvg-convert", "-f", "pdf", "-o", base + ".pdf", svg_path], check=True)
                written.append(base + ".pdf")
                if self.pdf_links:
                    add_pdf_links(base + ".pdf", self.pdf_links)
        print(f"{self.fname}: drawing {self.width:.0f}x{self.height:.0f} px on {self.page}, {', '.join(os.path.basename(p) for p in written)}")
        return written


def add_pdf_links(pdf: str, links) -> int:
    """Make sure a single-page PDF carries the link annotations for `links` (dicts with url, x1, y1, x2, y2
    in PDF points, origin bottom-left). librsvg 2.63 writes them itself from the SVG <a> elements; this
    only adds them, with pypdf, when the page has none (older librsvg). Returns the number added."""
    links = list(links)
    if not links:
        return 0
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Link
    except ImportError:
        return 0
    if PdfReader(pdf).pages[0].get("/Annots"):
        return 0
    wr = PdfWriter(clone_from=pdf)
    for l in links:
        wr.add_annotation(page_number=0, annotation=Link(rect=(l["x1"], l["y1"], l["x2"], l["y2"]), url=l["url"]))
    with open(pdf, "wb") as f:
        wr.write(f)
    return len(links)


def merge_pdfs(out: str, pdfs) -> str:
    """Join single-sheet PDFs into one file, keeping link annotations. Needs pypdf."""
    pdfs = list(pdfs)
    try:
        from pypdf import PdfWriter
    except ImportError as e:
        raise RuntimeError("merge_pdfs needs pypdf: pip install pypdf") from e
    wr = PdfWriter()
    for p in pdfs:
        wr.append(p)
    with open(out, "wb") as f:
        wr.write(f)
    print(f"{out}: {len(pdfs)} pages")
    return out
