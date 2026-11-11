#!/usr/bin/env python3
"""Stop the Overview crowding itself.

WHAT WAS WRONG

Measured on the rendered page at 1443x541, eighteen pairs of text boxes
overlapped. They were not random - they were the same mistake repeated.

A zone card is 233 x 61 px. Stacked inside it: an 11.5px zone name, a 10px
state word, a 26px counter and a 9.5px caption. That is about 65px of type
plus padding in 61px of card, so every row's box ran into the row below it.
The rows still read, because a label's text is smaller than the line box it
sits in - but there was no space anywhere and the card looked jammed, which
is exactly what it was.

The same thing in the sensor panel: the photo-eye captions occupy a box 5px
tall holding 13px of text, and the gate captions sit in the next 5px box
down. "Length 1" and "GATE 1 DOWN" genuinely collided - the first ends at
x=340 and the second starts at x=329.

WHAT CHANGES

1. The state word moves up beside the zone name, right-aligned, instead of
   taking a row of its own. That is a row back for free, and it matches the
   pattern the right-hand rail already uses.

2. Z5's state was 20px where the other four were 10px - the same word at two
   sizes on one screen. All five are 10px now.

3. The cards get taller: 0.175-0.450 becomes 0.155-0.470 of the mimic, 61px
   to 69px at this window. The space comes from the gaps either side, which
   were 10px and 9px and are now 5px and 4px - the cards have borders, so
   they do not need a wide moat to read as separate.

4. Every label box is now at least as tall as the text in it, and the rows
   are laid out with real gaps between them rather than butted together.

5. The gate and clamp captions move to their own row under the photo-eye
   captions, and get enough width for their text at 1024 as well
   ("GATE 1 DOWN" needs 61px and had 50).

6. "Interfaces" in the safety row no longer overlaps the air-pressure
   readout beside it.

Every number below was measured on the live page, not estimated. The card
fractions are of a 69px card; the sensor fractions are of an 87px panel.

Idempotent. Run:  python3 tools/fit_overview.py
"""

import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
VIEW = os.path.join(ROOT, "project", "com.inductiveautomation.perspective",
                    "views", "Machine", "Overview")

# --- the row grid every zone card now uses -----------------------------------
# name/state share row 1; the value has row 2; the caption has row 3.
HDR_Y, HDR_H = 0.075, 0.215      # 5.2 -> 20.0 px   (11.5px text)
VAL_Y, VAL_H = 0.365, 0.385      # 25.2 -> 51.7 px  (26px text)
CAP_Y, CAP_H = 0.785, 0.175      # 54.2 -> 66.3 px  (9.5px text)

NAME_X, NAME_W = 0.057, 0.490
STATE_X, STATE_W = 0.565, 0.378

# Five layer bars fill the same band as the counter beside them.
BAR_TOP, BAR_H, BAR_PITCH = 0.365, 0.058, 0.085


def find(node, name):
    if node.get("meta", {}).get("name") == name:
        return node
    for child in node.get("children", []) or []:
        hit = find(child, name)
        if hit:
            return hit
    return None


def place(node, **kw):
    node["position"].update(kw)


def style(node, **kw):
    s = node.setdefault("props", {}).setdefault("style", {})
    for k, v in kw.items():
        if v is None:
            s.pop(k, None)
        else:
            s[k] = v


def add_class(node, cls):
    s = node.setdefault("props", {}).setdefault("style", {})
    have = [c for c in s.get("classes", "").split() if c]
    if cls not in have:
        have.append(cls)
        s["classes"] = " ".join(have)


def ellipsise(node, cls):
    """A label that runs out of room should lose its tail, not run into its
    neighbour.

    This CANNOT be done from props.style, and the view had been trying to:
    ia.display.label renders its text inside an inner <span> that the
    component's own styles never reach, and that span computes
    `overflow: visible`, so `text-overflow: ellipsis` set on the label is
    inert. Measured: the zone name span reported overflow visible and
    text-overflow clip with the props asking for hidden/ellipsis.

    So the label carries a class and the stylesheet targets the span. The
    same class is what the narrow-panel font rules hang off - and setting the
    size on the SPAN means the label keeps its inline font-size as the base,
    instead of having to have it removed first.
    """
    add_class(node, cls)
    style(node, overflow=None, textOverflow=None)


view_file = os.path.join(VIEW, "view.json")
view = json.load(open(view_file))
root = view["root"]

mimic = find(root, "Mimic")

# --- 1. the four robot cards -------------------------------------------------
for i, cell in enumerate(("CellZ1", "CellZ2", "CellZ3", "CellZ4"), start=1):
    card = find(mimic, cell)
    place(card, y=0.155, height=0.315)

    name = find(card, "Zn")
    place(name, x=NAME_X, y=HDR_Y, width=NAME_W, height=HDR_H)

    state = find(card, "St")
    place(state, x=STATE_X, y=HDR_Y, width=STATE_W, height=HDR_H)
    style(state, textAlign="right")
    ellipsise(state, "zone-state")
    ellipsise(name, "zone-name")

    # The counter: cases placed (Z1/Z2) or cycle time (Z3/Z4).
    value = find(card, "Cases") or find(card, "Cyc")
    place(value, y=VAL_Y, height=VAL_H)
    caption = find(card, "CasesK") or find(card, "CycK")
    place(caption, y=CAP_Y, height=CAP_H)

    bars = [find(card, "Lay%d" % n) for n in range(5)]
    if bars[0] is not None:
        # Lay0 is the bottom layer, Lay4 the top, so the index counts upwards
        # from the foot of the stack.
        for n, bar in enumerate(bars):
            place(bar, y=BAR_TOP + (4 - n) * BAR_PITCH, height=BAR_H)
        place(find(card, "LayK"), y=CAP_Y, height=CAP_H, width=0.44)

    hz = find(card, "Hz")
    if hz is not None:
        place(hz, x=0.875, y=0.45, width=0.09, height=0.13)

# --- 2. the wrapper card -----------------------------------------------------
z5 = find(mimic, "Z5")
place(z5, y=0.485, height=0.26)                     # 55px -> 57px

place(find(z5, "N"), x=0.053, y=0.085, width=0.500, height=0.22)
ellipsise(find(z5, "N"), "zone-name")

s5 = find(z5, "S")
place(s5, x=0.575, y=0.085, width=0.372, height=0.22)
# 20px where every other card said 10px. One word, one size.
style(s5, fontSize="10px", textAlign="right", letterSpacing="0.7px")
ellipsise(s5, "zone-state")

place(find(z5, "F1"),  x=0.0595, y=0.45, width=0.06, height=0.14)
place(find(z5, "F1L"), x=0.1548, y=0.43, width=0.79, height=0.21)
place(find(z5, "F2"),  x=0.0595, y=0.73, width=0.06, height=0.14)
place(find(z5, "F2L"), x=0.1548, y=0.71, width=0.79, height=0.21)

# --- 3. the safety strip -----------------------------------------------------
# "Interfaces" ran 17px into the air-pressure readout's box beside it.
place(find(mimic, "ST3"), width=0.096)

# --- 4. the sensor panel -----------------------------------------------------
sensors = find(root, "Sensors")

# Conveyor headers: a 6px box holding 14px of text.
for n in (1, 2, 3):
    head = find(sensors, "ConveyorC%d" % n)
    place(head, y=0.02, height=0.17)
    # At 1024 the third name needs 154px and has 121. Shed the tail rather
    # than run it under the speed readout - the dot and the number are the
    # parts an operator reads.
    ellipsise(find(head, "N"), "conv-name")

# Photo-eye captions: one row, each centred on its own sensor. The boxes were
# 0.0778 wide where the sensors are only 0.0667 apart, so consecutive captions
# overlapped even though the text inside them did not. 0.064 is the widest that
# still leaves daylight between them, and it holds the longest caption
# ("Length 1", 37px) at 1024 with room to spare.
PE = ("Infeed", "Carton", "Length1", "Length2", "InPos1", "InPos2", "Clear")
for name in PE:
    dot = find(sensors, "EyeLamp%s" % name)
    centre = dot["position"]["x"] + dot["position"]["width"] / 2.0
    caption = find(sensors, "EyeLabel%s" % name)
    place(caption, x=round(centre - 0.064 / 2.0, 5), y=0.635,
          width=0.064, height=0.155)
    ellipsise(caption, "pe-cap")

# The gate and clamp captions get their own row, and enough width for their
# longest text at 1024 - "GATE 1 DOWN" needs 61px there and had 50. Re-centred
# on the gate they belong to, since they are wider than they were.
for label, gate in (("Gate1Label", "Gate1Lamp"), ("Gate2Label", "Gate2Lamp")):
    g = find(sensors, gate)
    centre = g["position"]["x"] + g["position"]["width"] / 2.0
    place(find(sensors, label),
          x=round(centre - 0.105 / 2.0, 5), y=0.815, width=0.105, height=0.155)

place(find(sensors, "ClL"), y=0.815, width=0.145, height=0.155)

# Widening gate 2's caption pushed it into the barcode readout. The readout is
# a dot, a 55px label and a short value - about 131px of content in a box that
# was 331px wide - so it gives up the left third rather than the caption
# giving up its text.
place(find(sensors, "Bar"), x=0.715, width=0.263)

# --- write -------------------------------------------------------------------
json.dump(view, open(view_file, "w"), indent=2)

res_file = os.path.join(VIEW, "resource.json")
res = json.load(open(res_file))
mod = res.setdefault("attributes", {}).setdefault("lastModification", {})
mod["actor"] = "external"
mod["timestamp"] = datetime.datetime.now(
    datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
res.pop("lastModificationSignature", None)
mod.pop("lastModificationSignature", None)
json.dump(res, open(res_file, "w"), indent=2)

print("overview fitted: 4 robot cards, wrapper card, safety strip, sensor panel")
