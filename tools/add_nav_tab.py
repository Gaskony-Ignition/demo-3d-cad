#!/usr/bin/env python3
"""Keep the nav bar in step across every view that carries one.

Idempotent: run it twice and nothing changes. Each tab is cloned from NavOverview
in the SAME view rather than written from scratch, so it inherits that view's
styling and - more importantly - the exact event shape. A nav action with a
missing "scope" key returns HTTP 500 on EVERY page of the project while the scan
still reports success, so the safe move is never to hand-author one.

Cell3D and CadModel deliberately have NO nav bar: they are full-bleed model
screens with a Back button in their header instead. They are skipped here,
and they are the reason the list below has more entries than the bar has
room to lose.

Run:  python3 tools/add_nav_tab.py
"""

import copy
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.join(HERE, os.pardir, "project",
                     "com.inductiveautomation.perspective", "views", "Machine")

# The bar, in order. A tab is removed by deleting its line: the rewrite below
# replaces the whole Nav container, so an old tab does not linger in a view
# nobody thought to open.
TABS = [
    ("NavOverview", "OVERVIEW", "/"),
    ("NavCell3d",   "3D CELL",  "/cell3d"),
    ("NavCad",      "CAD",      "/cad"),
    ("NavManual",   "MANUAL",   "/manual"),
    ("NavAlarms",   "ALARMS",   "/alarms"),
    ("NavSetup",    "SETUP",    "/setup"),
]

# Which tab each view lights up. A view not listed here lights up nothing.
ACTIVE_TAB = {
    "Overview": "NavOverview",
    "Manual": "NavManual",
    "Alarms": "NavAlarms",
    "Setup": "NavSetup",
}

ACTIVE = {"backgroundColor": "var(--md-info-bg, #152f3b)",
          "border": "1px solid var(--md-info, #6cc4e8)",
          "color": "var(--md-info-ink-2, #cfeafa)"}
INACTIVE = {"backgroundColor": "transparent",
            "border": "1px solid var(--md-line, #2c343d)",
            "color": "var(--md-ink-quiet, #8b98a3)"}


def keyboard_nav(component, page):
    """WCAG 2.1 AA 2.1.1: make a nav-onClick component reachable by Tab and
    fired by Enter/Space. `onClick` stays a plain `nav` action (it has no key
    filter of its own), so the onKeyDown script calls
    system.perspective.navigate itself, gated to the two activation keys.

    scope MUST be "G" - a script-type dom action registered with "C" never
    reaches the client at all (silent console warning, "Client Action
    'script' not registered"), which is how T_dark's onClick two tabs over
    already does it."""
    component.setdefault("meta", {})["tabIndex"] = 0
    dom = component.setdefault("events", {}).setdefault("dom", {})
    dom["onKeyDown"] = {
        "type": "script", "scope": "G",
        "config": {"script": (
            "\tif event.key in ('Enter', ' '):\n"
            "\t\tsystem.perspective.navigate(page='%s')" % page
        )},
    }
    return component


def find(node, name):
    if node.get("meta", {}).get("name") == name:
        return node
    for child in node.get("children", []):
        hit = find(child, name)
        if hit:
            return hit
    return None


def stamp(view_dir):
    path = os.path.join(view_dir, "resource.json")
    r = json.load(open(path))
    lm = r.setdefault("attributes", {}).setdefault("lastModification", {})
    lm["actor"] = "external"
    lm["timestamp"] = (datetime.datetime.now(datetime.timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ"))
    # A stale content-hash makes the scan silently skip the resource.
    r.pop("lastModificationSignature", None)
    lm.pop("lastModificationSignature", None)
    json.dump(r, open(path, "w"), indent=2)


changed = []
for name in sorted(os.listdir(VIEWS)):
    view_dir = os.path.join(VIEWS, name)
    view_file = os.path.join(view_dir, "view.json")
    if not os.path.isfile(view_file):
        continue

    before = open(view_file).read()
    view = json.loads(before)
    nav = find(view["root"], "Nav")
    if nav is None:
        print("%-10s no nav bar - skipped" % name)
        continue

    template = find(nav, "NavOverview")
    if template is None:
        raise SystemExit("%s has a nav but no NavOverview to clone" % name)
    template = copy.deepcopy(template)
    active = ACTIVE_TAB.get(name)

    kids = []
    for tab_name, text, page in TABS:
        existing = find(nav, tab_name)
        tab = copy.deepcopy(existing if existing is not None else template)
        tab["meta"]["name"] = tab_name
        tab["props"]["text"] = text
        tab["events"]["dom"]["onClick"]["config"]["page"] = page
        tab["props"]["style"].update(ACTIVE if tab_name == active else INACTIVE)
        keyboard_nav(tab, page)
        kids.append(tab)
    nav["children"] = kids

    after = json.dumps(view, indent=2)
    if after == before:
        print("%-10s already correct" % name)
        continue
    open(view_file, "w").write(after)
    stamp(view_dir)
    changed.append(name)
    print("%-10s nav rewritten (%d tabs, active=%s)"
          % (name, len(TABS), active or "none"))

print("\nchanged: %s" % (", ".join(changed) or "nothing"))
