# wiresheet

System wiring sheets as clean SVG, from a few lines of Python. Made for documenting how the parts of a
machine are cabled together: battery to breaker to bus bar to loads, computer to switch to sensors,
a CAN daisy chain. Each box shows a photo of the real part and the port names as printed on it; wires
are right-angle lines in the colour of the real conductor; shared terminals get junction dots; every
sheet lands on a fixed page with a frame and a title block.

No layout engine, no diagramming app. The script computes positions on a fixed grid and writes SVG
text. librsvg turns that into PNG and vector PDF.

![example](docs/example.png)

## Install

- Python 3.8 or newer, standard library only.
- `rsvg-convert` for PNG and PDF output: `brew install librsvg` on macOS, `apt install librsvg2-bin` on Debian/Ubuntu. SVG output needs nothing.
- Optional: `pip install pypdf` to merge sheets into one PDF with `merge_pdfs`. On macOS `tools/mergepdf.swift` does the same with PDFKit.

Drop `wiresheet.py` next to your script, or add this folder to `PYTHONPATH`.

## Quick start

```python
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
s.render()      # 01-power.svg, 01-power.png, 01-power.pdf
```

`examples/demo.py` builds a two-sheet set and merges it; run it from the `examples` folder.

## The model

A sheet is a grid. You give it the columns in reading order, sources on the left and loads on the
right, and inside each column the boxes top to bottom. That order is the whole layout; nothing is
auto-arranged, so the drawing comes out the way you would sketch it by hand.

```python
Sheet(fname, title, sheet="1 of 6", columns=[[...], [...]], project="", rev="A", date=None,
      sub="", width=260, gap=None, page="A3", img_dir="img", out_dir=".")
```

- `fname` is the output file name without extension.
- `title`, `sheet`, `rev`, `date` fill the title block; `date` defaults to today. `project` and `sub` go in the small footer line.
- `width` is the box width in drawing pixels; `gap` overrides the channel width between columns.
- `page` is one of `A3`, `A4`, `A2`, `Letter`, `Tabloid`, all landscape. The drawing is scaled to fit.

Boxes:

```python
s.dev(name, type_="", img=None, ports=(), note="", imgh=80, offrobot=False, link=None)
```

- `name` is the title and the handle used by wires.
- `type_` is the model line under the title.
- `img` is a file in `img_dir`, shown `imgh` pixels tall. Vendor photos, datasheet crops or your own shots all work; the file is embedded in the SVG as base64.
- `ports` are the labels printed on the device, top to bottom. Use the real printing, `DC PWR  VP+`, `PoE+  RJ45`, `stud 3`, not invented names.
- `note` is one short line under the ports. Keep it to facts.
- `offrobot=True` draws the box dashed, for chargers, docks and other external equipment.
- `link` is a URL, usually the product page. The picture becomes clickable in the SVG and gets a link
  annotation in the PDF, so a reader clicks the part and lands on its datasheet or shop page. A box with no
  picture links its title bar instead.

Wires:

```python
s.wire((box, port), (box, port), color=BLK, label="", width=2.5, dashed=False)
s.pair(box_a, [ports_a], box_b, [ports_b], label="", width=2.5, colors=(RED, BLK))
```

`pair` is a shortcut for several conductors between the same two boxes, matched by position.
Colours are plain hex strings; `RED BLK BLU YEL GRN ORG GRY LGRY WHT PUR BRN` are predefined.

## How the wires are routed

- A wire leaves its port horizontally, turns into a vertical track in the channel between the two
  columns, runs to the height of the target port, and turns in. One SVG path: `M x y H x V y H x`.
- Every wire in a channel gets its own track, spaced 10 px. The wires are sorted by vertical run and
  the longest gets the track nearest the source, so a long wire runs inside and shorter ones peel
  off outside it without crossing.
- Several wires on one port share the stub out of the port and get a junction dot at each turn-off.
- A wire between two boxes in the same column loops out on the left side.
- A wire that skips a column dips just below the boxes of that column, runs across, and comes back
  up. Use this sparingly; it is usually nicer to put the two boxes in neighbouring columns.

Labels sit above the longest straight segment of their wire. Keep them short: a connector type,
a gauge, a length.

## Look and feel

`Style` holds row heights, font sizes, track spacing and colours. Change the class attributes to
restyle every sheet, or pass an instance to `Sheet(style=...)` for one.

What tends to read well, learnt the hard way:

- One device per sheet. If a converter's input is on the power sheet, put its output on the sheet
  where the load is, and say "OUT: sheet 3" in the note.
- Terse notes, no sentences. Open questions belong in a README next to the drawings, not on them.
- Order loads the way the bus bar or distribution block is numbered.
- Keep a sheet to one voltage rail or one bus. Six focused sheets beat one that needs a magnifier.

## Output

Per sheet: `name.svg` (editable in Inkscape, Illustrator, Figma), `name.png` at 2x, `name.pdf` as a
vector page in the chosen format. `merge_pdfs(out, [pdfs])` joins them.

Links in PDFs: librsvg does not carry SVG links into the PDF, so after rendering the engine adds link
annotations itself. It uses pypdf if installed (`pip install pypdf`), otherwise on macOS it builds and
runs `tools/pdflinks.swift` (PDFKit, no dependencies). `merge_pdfs` works the same way with
`tools/mergepdf.swift`, and keeps the annotations.

## Project layout

```
wiresheet.py          the whole engine, one file
examples/demo.py      two-sheet example
examples/img/         photos for the example (empty; add your own)
tools/mergepdf.swift  PDF merge via PDFKit (macOS fallback when pypdf is absent)
tools/pdflinks.swift  PDF link annotations via PDFKit (same)
docs/example.png      the image at the top of this file
```
