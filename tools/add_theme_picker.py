#!/usr/bin/env python3
"""Put the theme choice in the operator's hands, on every page.

WHY IT IS WORTH HAVING

The session already carried a theme - `session.props.theme` feeds the Cell3D
view param, which feeds the 3D page's `?theme=`, which picks one of six
palettes. All of that plumbing existed and nothing could change the value
without editing the project. This adds the control.

The six names are Ignition's own stock themes, and the 3D page's palettes are
named to match, so one setting moves both: Perspective's components and the
WebGL cell change together instead of drifting apart.

TWO PLACES, ON PURPOSE

  Header dropdown - on every page, for the person driving a demonstration who
                    wants to change it without leaving the screen they are on.
                    Hidden below 1120px: the header already sheds its subtitle,
                    then its padding, then its font sizes at that width, and on
                    a 10in panel an operator does not pick themes.

  Setup page rows - six buttons beside the simulation-speed row, two rows of
                    three, which is the same idiom and is reachable at any
                    width. This is the one that still works on the panel.

The dropdown writes `session.props.theme` through a bidirectional binding.
`bidirectional` goes INSIDE `config`; at binding level it is accepted and
silently never writes back, which looks exactly like a dropdown that does not
work.

Idempotent, and it REBUILDS what it owns rather than skipping when it is
already there - the theme list changes, and a guard that only checks whether
the control exists would leave the old options in place.

Run:  python3 tools/add_theme_picker.py
"""

import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.join(HERE, os.pardir, "project",
                     "com.inductiveautomation.perspective", "views", "Machine")

# Ignition ships six stock themes and the 3D page has a palette for each. All
# six are offered, since 04/09/2026. Until then only the three DARK ones were,
# and the reason is worth keeping because it is what the work had to undo.
#
# WHAT WAS WRONG
#
# tools/themeify.py had mapped 568 neutral colours onto the theme's own
# surface-relative tokens, and on a light theme that part worked. The other
# 849 did not: its regex only matches a prop whose WHOLE value is a hex
# string, so everything inside an if() expression, a `1px solid #2c343d`
# shorthand, a gradient, an alarm-table rowStyle or a script transform stayed
# literal. Measured on all six pages, compositing every rgba layer over its
# real surface rather than reading the top one as opaque:
#
#     dark    590 texts,   0 below 3.0
#     light   590 texts, 190 below 3.0
#
# and the 190 split two ways, only the first of which is about colour choice:
#
#   * accents on light chrome - #46d07c/#eebf5e/#6cc4e8 on #F0F0F0 at 1.5-1.75
#   * surfaces that never flip - a card left at a literal #1d232a while its
#     text follows the token to near-black: 1.06:1, unreadable, and nothing to
#     do with the accents
#
# The second was the bulk of it, and the objection to fixing it was never the
# light themes - it was that adopting the theme tokens outright would restyle
# the three dark ones that are already in use.
#
# WHAT WAS DONE
#
# tools/mdvars.py hoists all 849 into `var(--md-NAME, #originalhex)` and
# defines each --md-NAME so that a dark theme computes it to EXACTLY the
# literal it replaced, and a light theme to the theme's own token (neutrals)
# or a measured light value (the accents). Read that file for the mechanism;
# the short version is a polarity term that clamps to 0 across every dark
# theme and 1 across every light one, so the two ends are pinned and the
# middle never happens.
#
# Ignition's own --success/--warning/--error do flip correctly and were
# rejected for the accents: --success is #0AA648 and the project's running
# green is #46d07c, so adopting them is a dark-theme change.
#
# MEASURED AFTER, 04/09/2026
#
#   tools/verify/md_vars_check.js   66 variables x 3 dark themes,
#                                   0 differ from the literal they replaced
#   tools/verify/colour_snapshot.js 0 elements changed colour, six pages
#   contrast_sweep.js               dark 0 below 3.0   (unchanged)
#   contrast_sweep.js --light       22 below 3.0, from 190
#   contrast_sweep.js --theme light / light-cool / light-warm     0, 0, 0
#
# --light is the historical approximation - it overrides the ten --neutral-*
# tokens and nothing else, and its --neutral-60 is #8A8A8A, lighter than
# dark-cool's own #878D96, so half the ramp reads as dark and the project
# rightly declines to flip. The 22 it still reports are that artefact and the
# theme dropdown, which stays black because --input is not part of the ramp.
# --theme loads the real stylesheet and is the number that means anything.
#
# So: six themes that are verified legible, rather than three. Every one of
# them visibly changes the whole project - Perspective chrome, stock
# components, and the 3D cell together.
THEMES = [("dark", "Dark"), ("dark-cool", "Dark cool"),
          ("dark-warm", "Dark warm"),
          ("light", "Light"), ("light-cool", "Light cool"),
          ("light-warm", "Light warm")]
# Three to a row on the Setup page - six across is 45px a button at 1024.
ROWS = [("Themes", THEMES[:3]), ("Themes2", THEMES[3:])]


def find(node, name):
    if node.get("meta", {}).get("name") == name:
        return node
    for child in node.get("children", []) or []:
        hit = find(child, name)
        if hit:
            return hit
    return None


def stamp(view_dir):
    path = os.path.join(view_dir, "resource.json")
    r = json.load(open(path))
    mod = r.setdefault("attributes", {}).setdefault("lastModification", {})
    mod["actor"] = "external"
    mod["timestamp"] = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r.pop("lastModificationSignature", None)
    mod.pop("lastModificationSignature", None)
    json.dump(r, open(path, "w"), indent=2)


def dropdown():
    return {
        "type": "ia.input.dropdown",
        "version": 0,
        "meta": {"name": "Theme"},
        "position": {"grow": 0, "shrink": 0, "basis": "138px"},
        "props": {
            "options": [{"value": v, "label": l} for v, l in THEMES],
            "placeholder": "Theme",
            "style": {"classes": "hdr-theme", "minWidth": "0px"},
        },
        "propConfig": {
            "props.value": {
                "binding": {
                    "type": "property",
                    # bidirectional INSIDE config, or the dropdown reads the
                    # session theme and never writes one back.
                    "config": {"path": "session.props.theme",
                               "bidirectional": True},
                }
            }
        },
    }


def button(value, label):
    return {
        "type": "ia.input.button",
        "version": 0,
        "meta": {"name": "Theme" + "".join(w.capitalize() for w in value.split("-"))},
        "position": {"grow": 1, "shrink": 1, "basis": "0px"},
        "props": {
            "text": label,
            "style": {"fontSize": "11.5px", "fontWeight": 700,
                      "letterSpacing": "0.4px", "borderRadius": "6px",
                      "border": "1px solid var(--md-line, #2c343d)",
                      "backgroundColor": "var(--md-face, #252c34)",
                      "color": "var(--md-ink-body, #cfd8df)",
                      "padding": "0px", "minWidth": "0px",
                      "alignItems": "center", "whiteSpace": "nowrap"},
        },
        "events": {
            "dom": {
                "onClick": {
                    "type": "script",
                    "config": {
                        "script": "\tself.session.props.theme = %r\n" % str(value)
                    },
                    "scope": "G",
                }
            }
        },
    }


# --- 1. the header dropdown, on every view that has the nav bar --------------
touched = []
for name in sorted(os.listdir(VIEWS)):
    view_dir = os.path.join(VIEWS, name)
    view_file = os.path.join(view_dir, "view.json")
    if not os.path.isfile(view_file):
        continue
    view = json.load(open(view_file))
    bar = find(view["root"], "TopBar")
    if bar is None or find(view["root"], "Nav") is None:
        continue
    existing = find(bar, "Theme")
    if existing is None:
        # Between the nav tabs and the user block: it belongs with the other
        # session-level controls, not among the page links.
        names = [c["meta"]["name"] for c in bar["children"]]
        bar["children"].insert(names.index("User") if "User" in names
                               else len(names), dropdown())
    else:
        # Already there: refresh the list. Skipping would leave a dropdown
        # offering yesterday's themes and look exactly like a working one.
        existing["props"]["options"] = dropdown()["props"]["options"]
    json.dump(view, open(view_file, "w"), indent=2)
    stamp(view_dir)
    touched.append(name)

# --- 2. the Setup page row ---------------------------------------------------
setup_dir = os.path.join(VIEWS, "Setup")
setup_file = os.path.join(setup_dir, "view.json")
setup = json.load(open(setup_file))

speed = find(setup["root"], "Speed")
if speed is None:
    raise SystemExit("Setup has no Speed panel to sit beside")
body = find(speed, "Body")

# Rebuilt every run rather than added once: the row count follows THEMES, and
# a guard on "is it there" would have left three buttons behind when the list
# went to six.
OWNED = ["ThemeK"] + [row for row, _ in ROWS]
body["children"] = [c for c in body["children"]
                    if c["meta"]["name"] not in OWNED]

# The panel is sized for exactly what it holds: 206px of speed and simulation
# rows, a 22px caption, and 34px for each row of theme buttons.
speed["position"]["basis"] = "%dpx" % (206 + 22 + 34 * len(ROWS))
body["children"].append({
    "type": "ia.container.flex", "version": 0,
    "meta": {"name": "ThemeK"},
    "position": {"grow": 0, "shrink": 0, "basis": "22px"},
    "props": {"style": {"minWidth": "0px", "minHeight": "0px"}},
    "children": [{
        "type": "ia.display.label", "version": 0, "meta": {"name": "K"},
        "position": {"grow": 1, "shrink": 1, "basis": "auto"},
        "props": {"text": "Theme — Perspective and the 3D cell together",
                  "style": {"fontSize": "10px",
                            "color": "var(--md-ink-dim, #74808a)",
                            "letterSpacing": "0.6px",
                            "whiteSpace": "nowrap", "overflow": "hidden",
                            "textOverflow": "ellipsis"}},
    }],
})
for row, pairs in ROWS:
    body["children"].append({
        "type": "ia.container.flex", "version": 0,
        "meta": {"name": row},
        "position": {"grow": 0, "shrink": 0, "basis": "34px"},
        "props": {"direction": "row",
                  "style": {"gap": "6px", "padding": "0 10px 6px",
                            "minWidth": "0px", "minHeight": "0px"}},
        "children": [button(v, l) for v, l in pairs],
    })

json.dump(setup, open(setup_file, "w"), indent=2)
stamp(setup_dir)

print("theme dropdown in the header of: %s" % ", ".join(touched))
print("theme buttons added to the Setup page")
