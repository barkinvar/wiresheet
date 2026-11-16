#!/usr/bin/env python3
"""Builds docs/tutorial.md and its images. Each example below is real code: it is executed to render the
picture, and copied verbatim into the markdown, so the text and the drawings cannot drift apart.
Run from anywhere:  python3 examples/tutorial.py"""
import os, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from wiresheet import Sheet, RED, BLK, BLU, YEL, GRN, GRY, merge_pdfs  # noqa: E402

DOCS = os.path.join(ROOT, "docs", "tutorial")
IMG = os.path.join(HERE, "img")
os.makedirs(DOCS, exist_ok=True)
os.makedirs(IMG, exist_ok=True)


def placeholder_png(path, w=240, h=140):
    """A grey battery-ish picture, so the photo example needs no download."""
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            body = 20 <= x < w - 30 and 25 <= y < h - 25
            cap = w - 30 <= x < w - 18 and h // 2 - 18 <= y < h // 2 + 18
            if body or cap:
                shade = 60 + (y * 70 // h)
                row += bytes((shade, shade + 10, shade + 20))
            else:
                row += b"\xff\xff\xff"
        rows.append(bytes(row))
    raw = b"".join(rows)
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


EXAMPLES = [
("One wire", """
The two lists in `columns` are the whole layout. `["Battery"]` is column 0 on the left, `["Lamp"]` is
column 1 to its right. Each `dev` declares a box: title, model line, photo (none here), and the port
rows top to bottom. A `wire` names a port on each end. The wire leaves the Battery on its right edge,
runs in the channel between the columns, and enters the Lamp on its left edge.
""", '''
s = Sheet("01-one-wire", "One wire", page="fit", columns=[["Battery"], ["Lamp"]])
s.dev("Battery", "12 V", None, ["+", "-"])
s.dev("Lamp", "", None, ["+", "-"])
s.wire(("Battery", "+"), ("Lamp", "+"), RED)
s.wire(("Battery", "-"), ("Lamp", "-"), BLK)
s.render()
'''),

("A column of loads", """
Order inside a column is top to bottom, exactly as written: Motor, then Lamp, then Lidar. `pair` draws
several conductors between the same two boxes in one call, red and black by default, with the label on
the first one. Every wire in the channel gets its own vertical track. The longest run (to the Lidar)
takes the track nearest the fuse box, shorter runs sit further out, so nothing crosses.
""", '''
s = Sheet("02-column", "A column of loads", page="fit",
          columns=[["Fuse box"], ["Motor", "Lamp", "Lidar"]])
s.dev("Fuse box", "3-way, 10 A fuses", None,
      ["OUT 1 +", "OUT 1 -", "OUT 2 +", "OUT 2 -", "OUT 3 +", "OUT 3 -"])
s.dev("Motor", "", None, ["+", "-"])
s.dev("Lamp", "", None, ["+", "-"])
s.dev("Lidar", "9-32 V", None, ["VIN", "GND"])
s.pair("Fuse box", ["OUT 1 +", "OUT 1 -"], "Motor", ["+", "-"], "10 A")
s.pair("Fuse box", ["OUT 2 +", "OUT 2 -"], "Lamp", ["+", "-"], "2 A")
s.pair("Fuse box", ["OUT 3 +", "OUT 3 -"], "Lidar", ["VIN", "GND"], "1 A")
s.render()
'''),

("Shared terminals", """
Three loads hang off the same two studs. Wires that leave one port share the stub out of that port,
and a junction dot marks every point where one of them turns off into its own track. Swap the order of
`"Motor"`, `"Lamp"`, `"Lidar"` in the column and only the stacking changes; the tracks are re-assigned
by the same rule.
""", '''
s = Sheet("03-shared", "Shared terminals", page="fit",
          columns=[["Bus bar"], ["Motor", "Lamp", "Lidar"]])
s.dev("Bus bar", "4 studs, 150 A", None, ["stud 1", "stud 2", "stud 3", "stud 4"])
s.dev("Motor", "", None, ["+", "-"])
s.dev("Lamp", "", None, ["+", "-"])
s.dev("Lidar", "", None, ["VIN", "GND"])
for load, p, n in [("Motor", "+", "-"), ("Lamp", "+", "-"), ("Lidar", "VIN", "GND")]:
    s.wire(("Bus bar", "stud 2"), (load, p), RED)
    s.wire(("Bus bar", "stud 3"), (load, n), BLK)
s.render()
'''),

("Same column, skipped column", """
Two special routes. A wire between boxes in the **same column** loops out on the left side, like the
parallel links between the batteries. A wire whose ends are **not in neighbouring columns** dips just
under the boxes of the column in between, like the black lead from Battery B that bypasses the breaker
column on its way to the bus bar. Both work, but a drawing reads best when most wires join neighbours.
""", '''
s = Sheet("04-loops", "Same column, skipped column", page="fit",
          columns=[["Battery A", "Battery B"], ["Breaker"], ["Bus bar"]])
s.dev("Battery A", "24 V 50 Ah", None, ["+", "-"])
s.dev("Battery B", "24 V 50 Ah", None, ["+", "-"], "parallel with A")
s.dev("Breaker", "100 A", None, ["IN", "OUT"])
s.dev("Bus bar", "", None, ["+", "-"])
s.wire(("Battery A", "+"), ("Battery B", "+"), RED, "", 3.5)      # same column
s.wire(("Battery A", "-"), ("Battery B", "-"), BLK, "", 3.5)      # same column
s.wire(("Battery A", "+"), ("Breaker", "IN"), RED, "", 4)
s.wire(("Breaker", "OUT"), ("Bus bar", "+"), RED, "", 4)
s.wire(("Battery B", "-"), ("Bus bar", "-"), BLK, "", 4)          # skips the breaker column
s.render()
'''),

("Photos, links, notes, a real page", """
The last example renders a real page instead of `fit`: A4 landscape with a frame and a title block
filled from `title`, `sheet`, `rev` and `date`, and `project` in the footer. The battery has a photo
from `img_dir`, a one-line `note`, and a `link`, so clicking the picture in the SVG or PDF opens the
product page. The charger and the pad are `external=True`, not part of the machine, and drawn dashed.
Wires can be dashed too, here for the
air gap of a wireless charger, and colours are any hex string.
""", '''
s = Sheet("05-page", "Charging", sheet="1 of 1", project="Demo machine", rev="A", date="2026-11-16",
          page="A4", img_dir=IMG,
          columns=[["Mains charger", "Wireless pad"], ["Battery"]])
s.dev("Mains charger", "LiFePO4 charger, 29.2 V", None, ["DC +", "DC -"], external=True)
s.dev("Wireless pad", "transmitter, in the floor", None, ["coil"], external=True)
s.dev("Battery", "24 V 50 Ah LiFePO4", "placeholder-battery.png", ["+", "-", "coil in"],
      "charge leads land here", imgh=70, link="https://example.com/battery")
s.pair("Mains charger", ["DC +", "DC -"], "Battery", ["+", "-"], "6 AWG, SB50", 3)
s.wire(("Wireless pad", "coil"), ("Battery", "coil in"), "#b5b5b5", "air gap 20-55 mm", 2, dashed=True)
s.render()
'''),

("A set of sheets, merged", """
A real machine takes several sheets. Give them the same `project`, `rev` and `date`, number them with
`sheet`, and point across with a note such as `data: sheet 2`. Each `render()` writes its own PDF;
`merge_pdfs` joins them into one file, links included. It needs `pip install pypdf`; everything else
on this page works without it. The result here is [06-set.pdf](tutorial/06-set.pdf).
""", '''
common = dict(project="Demo machine", rev="A", date="2026-11-16", page="A4")

p = Sheet("06-power", "Power", sheet="1 of 2", columns=[["Battery"], ["Fuse box"], ["Motor", "Computer"]], **common)
p.dev("Battery", "24 V 50 Ah", None, ["+", "-"])
p.dev("Fuse box", "2-way", None, ["IN +", "IN -", "OUT 1 +", "OUT 1 -", "OUT 2 +", "OUT 2 -"])
p.dev("Motor", "", None, ["+", "-"])
p.dev("Computer", "", None, ["DC IN +", "DC IN -"], "USB, LAN: sheet 2")
p.pair("Battery", ["+", "-"], "Fuse box", ["IN +", "IN -"], "", 3.5)
p.pair("Fuse box", ["OUT 1 +", "OUT 1 -"], "Motor", ["+", "-"], "20 A")
p.pair("Fuse box", ["OUT 2 +", "OUT 2 -"], "Computer", ["DC IN +", "DC IN -"], "5 A")
p.render()

d = Sheet("06-data", "Data", sheet="2 of 2", columns=[["Computer"], ["Switch"], ["Lidar", "Camera"]], **common)
d.dev("Computer", "", None, ["ETH", "USB"], "power: sheet 1")
d.dev("Switch", "5-port", None, ["Port 1", "Port 2", "Port 3"])
d.dev("Lidar", "", None, ["ETH"])
d.dev("Camera", "", None, ["ETH"])
d.wire(("Computer", "ETH"), ("Switch", "Port 1"), BLU, "Cat6")
d.wire(("Switch", "Port 2"), ("Lidar", "ETH"), BLU, "Cat6")
d.wire(("Switch", "Port 3"), ("Camera", "ETH"), BLU, "Cat6")
d.render()

merge_pdfs("06-set.pdf", ["06-power.pdf", "06-data.pdf"])
'''),
]


def main():
    placeholder_png(os.path.join(IMG, "placeholder-battery.png"))
    md = ["# wiresheet in six drawings",
          "",
          "Every example is the complete code: run it and you get the picture under it. The first four use",
          "`page=\"fit\"`, which renders just the drawing; the last two are real A4 pages.",
          "Generated by `examples/tutorial.py`, so the code and the pictures always match.",
          ""]
    cwd = os.getcwd()
    os.chdir(DOCS)                                   # examples write next to the markdown's pictures
    try:
        for title, text, code in EXAMPLES:
            ns = dict(Sheet=Sheet, RED=RED, BLK=BLK, BLU=BLU, YEL=YEL, GRN=GRN, GRY=GRY, IMG=IMG, merge_pdfs=merge_pdfs)
            exec(code, ns)
            sheets = [v for v in ns.values() if isinstance(v, Sheet)]
            md += [f"## {title}", "", text.strip(), "", "```python", code.strip(), "```", ""]
            for sh in sheets:
                md += [f"![{sh.title}](tutorial/{sh.fname}.png)", ""]
    finally:
        os.chdir(cwd)
    keep_pdf = {"06-set.pdf"}
    for f in os.listdir(DOCS):
        if f.endswith(".svg") or (f.endswith(".pdf") and f not in keep_pdf):
            os.remove(os.path.join(DOCS, f))
    md += ["## Where to go from here", "",
           "- Put sources on the left and loads on the right, and order loads the way the bus bar or fuse block is numbered.",
           "- One rail or one bus per sheet. Several small sheets beat one large one.",
           "- Use the port names printed on the device, not names you invent.",
           "- Keep open questions in a README next to the drawings, not on them.",
           "", "The full argument reference is in the [README](../README.md)."]
    open(os.path.join(ROOT, "docs", "tutorial.md"), "w").write("\n".join(md) + "\n")
    print("wrote docs/tutorial.md,", len(EXAMPLES), "examples")


if __name__ == "__main__":
    main()
