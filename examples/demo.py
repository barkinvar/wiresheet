#!/usr/bin/env python3
"""Two example sheets for a small battery-powered machine: a power sheet and a data sheet.
Run from this folder:  python3 demo.py   -> writes out/01-power.* and out/02-data.*"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from wiresheet import Sheet, RED, BLK, BLU, YEL, GRN, GRY, merge_pdfs

OUT = os.path.join(os.path.dirname(__file__), "out")
common = dict(project="Demo machine", rev="A", out_dir=OUT, img_dir=os.path.join(os.path.dirname(__file__), "img"))

# ------------------------------------------------------------------ sheet 1: power
s = Sheet("01-power", "24 V distribution", "1 of 2",
          columns=[["Battery A", "Battery B"], ["Main breaker"], ["+24V bus bar", "0V bus bar"],
                   ["Motor controller", "Computer", "24-12 V converter", "Lidar"]], **common)
s.dev("Battery A", "24 V 50 Ah LiFePO4", None, ["+", "-"], link="https://example.com/battery")
s.dev("Battery B", "24 V 50 Ah LiFePO4", None, ["+", "-"], "parallel with A")
s.dev("Main breaker", "100 A panel mount", None, ["stud, battery side", "stud, load side"], "main disconnect")
s.dev("+24V bus bar", "4 studs, 150 A", None, ["stud 1", "stud 2", "stud 3", "stud 4"])
s.dev("0V bus bar", "4 studs, 150 A", None, ["stud 1", "stud 2", "stud 3", "stud 4"])
s.dev("Motor controller", "", None, ["DC +", "DC -"])
s.dev("Computer", "", None, ["DC IN +", "DC IN -"])
s.dev("24-12 V converter", "non-isolated, 30 A", None, ["IN +", "IN -", "OUT +", "OUT -"], "OUT: 12 V rail")
s.dev("Lidar", "", None, ["VIN", "GND"])
s.wire(("Battery A", "+"), ("Battery B", "+"), RED, "", 3.5)
s.wire(("Battery A", "-"), ("Battery B", "-"), BLK, "", 3.5)
s.wire(("Battery A", "+"), ("Main breaker", "stud, battery side"), RED, "", 4)
s.wire(("Main breaker", "stud, load side"), ("+24V bus bar", "stud 1"), RED, "", 4)
s.wire(("Battery B", "-"), ("0V bus bar", "stud 1"), BLK, "", 4)            # skips a column: routed under the breaker
for load, pp, pn, stud in [("Motor controller", "DC +", "DC -", "stud 2"), ("Computer", "DC IN +", "DC IN -", "stud 3"),
                           ("24-12 V converter", "IN +", "IN -", "stud 3"), ("Lidar", "VIN", "GND", "stud 4")]:
    s.wire(("+24V bus bar", stud), (load, pp), RED)
    s.wire(("0V bus bar", stud), (load, pn), BLK)
s.render()

# ------------------------------------------------------------------ sheet 2: data
d = Sheet("02-data", "Ethernet and CAN", "2 of 2", sub="CAN: 120 ohm at both ends",
          columns=[["Computer"], ["Switch", "CAN adapter"], ["Lidar", "Camera", "Motor controller", "Terminator"]], **common)
d.dev("Computer", "", None, ["ETH", "USB 1", "USB 2"])
d.dev("Switch", "5-port gigabit", None, ["Port 1", "Port 2", "Port 3"])
d.dev("CAN adapter", "USB to CAN", None, ["USB", "CANH", "CANL"])
d.dev("Lidar", "", None, ["ETH"])
d.dev("Camera", "", None, ["ETH"])
d.dev("Motor controller", "", None, ["CANH", "CANL"])
d.dev("Terminator", "120 ohm", None, ["CANH", "CANL"])
d.wire(("Computer", "ETH"), ("Switch", "Port 1"), BLU, "Cat6")
d.wire(("Switch", "Port 2"), ("Lidar", "ETH"), BLU, "Cat6")
d.wire(("Switch", "Port 3"), ("Camera", "ETH"), BLU, "Cat6")
d.wire(("Computer", "USB 1"), ("CAN adapter", "USB"), BLK, "USB")
d.pair("CAN adapter", ["CANH", "CANL"], "Motor controller", ["CANH", "CANL"], "", 2.5, (YEL, GRN))
d.pair("CAN adapter", ["CANH", "CANL"], "Terminator", ["CANH", "CANL"], "", 2, (YEL, GRN))
d.render()

try:
    merge_pdfs(os.path.join(OUT, "demo-sheets.pdf"), [os.path.join(OUT, "01-power.pdf"), os.path.join(OUT, "02-data.pdf")])
except RuntimeError as e:
    print("merge skipped:", e)
