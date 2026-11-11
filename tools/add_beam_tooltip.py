#!/usr/bin/env python3
"""WCAG 2.1 AA 1.4.1: the Overview mimic's photo-eye beams say "clear" or
"blocked" only by switching from --md-run green to --md-edge grey - unlike
the gate lamps two rows below them, which already pair colour with a
GATE 1 UP / GATE 1 DOWN label. A beam is a hairline on the diagram with no
room for one, so it gets the word as a tooltip instead, bound the same way
its colour already is.

Idempotent: a beam that already has meta.tooltip is left alone.

Run:  python3 tools/add_beam_tooltip.py
"""
import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW_DIR = os.path.join(HERE, os.pardir, "project",
                        "com.inductiveautomation.perspective", "views",
                        "Machine", "Overview")
VIEW_FILE = os.path.join(VIEW_DIR, "view.json")

# component name -> plain caption, matching the *-pe-cap label already next
# to each beam on the diagram.
CAPTION = {
    "EyeBeamInfeed": "Infeed",
    "EyeBeamCarton": "Carton",
    "EyeBeamLength1": "Length 1",
    "EyeBeamLength2": "Length 2",
    "EyeBeamInPos1": "In pos 1",
    "EyeBeamInPos2": "In pos 2",
    "EyeBeamClear": "Clear",
}

TAG_RE = re.compile(r"\{(\[MachineDemo\][^}]+)\}")


def fix(node, changed):
    name = node.get("meta", {}).get("name", "")
    caption = CAPTION.get(name)
    if caption and "tooltip" not in node.get("meta", {}):
        bg = node.get("propConfig", {}).get("props.style.backgroundColor", {})
        expr = bg.get("binding", {}).get("config", {}).get("expression", "")
        m = TAG_RE.search(expr)
        if m:
            tag = m.group(1)
            node["meta"]["tooltip"] = {"text": ""}
            node.setdefault("propConfig", {})["meta.tooltip.text"] = {
                "binding": {
                    "type": "expr",
                    "config": {"expression": (
                        '"%s beam: " + if(coalesce({%s}, false), "clear", "blocked")'
                        % (caption, tag)
                    )},
                }
            }
            changed[0] += 1
    for child in node.get("children", []):
        fix(child, changed)


def stamp():
    path = os.path.join(VIEW_DIR, "resource.json")
    r = json.load(open(path))
    lm = r.setdefault("attributes", {}).setdefault("lastModification", {})
    lm["actor"] = "external"
    lm["timestamp"] = (datetime.datetime.now(datetime.timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ"))
    r.pop("lastModificationSignature", None)
    lm.pop("lastModificationSignature", None)
    json.dump(r, open(path, "w"), indent=2)


def main():
    before = open(VIEW_FILE, encoding="utf-8").read()
    view = json.loads(before)
    changed = [0]
    fix(view["root"], changed)
    if changed[0]:
        open(VIEW_FILE, "w", encoding="utf-8").write(json.dumps(view, indent=2))
        stamp()
        print("%d beam tooltip(s) added" % changed[0])
    else:
        print("already done")


if __name__ == "__main__":
    main()
