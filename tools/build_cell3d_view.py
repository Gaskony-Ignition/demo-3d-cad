#!/usr/bin/env python3
"""Build Machine/Cell3D - the 3D palletising cell as a genuinely embeddable
Perspective view.

The view is a header, an ia.display.iframe pointed at the WebDev-served 3D
page, and a geometry panel (toggled from the header) of fifteen numeric fields
bound bidirectionally to the [MachineDemo]Config tags. This generator adds four view params so the same view can be
dropped into any screen as an Embedded View, aimed at a chosen camera, with
its own title bar switched off:

    camera  string   default "overview"          which 3D camera the page starts on
    hud     boolean  default true                 overlay cards + camera buttons
    watermark boolean default true                 the "WebDev, not Perspective" label
    header  boolean  default true                 this view's OWN header row
    theme   string   default {session.props.theme} which colour set the page renders in

The iframe's props.src is bound to an expression that appends
?camera=<camera>&hud=<1|0>&theme=<theme> to the same relative WebDev path
used before - never an absolute URL, so the view keeps working on any
host/port. With no params overridden (the plain page route uses this view
with defaults) the rendered src is exactly what it always was, plus the
params the page already treats as its defaults - see docs/CONTRACT.md's
page-URL-params section, which the T+Q package implements on the page side.

`theme`'s DEFAULT is bound to {session.props.theme} rather than a literal
string, so an embed with nothing overridden follows the Perspective session's
own theme; passing a literal string in an Embedded View's param override still
wins, same as camera/hud/header.

The header-visibility switch lives on a WRAPPER ("HeaderSlot") around the
plain "Header" node, not on "Header" itself, so a copy of "Header" never
drags a param binding into a view that has not declared the param.
tools/build_cad_view.py is the current consumer: it takes "HeaderSlot"
wholesale for Machine/CadModel's header and strips the propConfig itself,
since that view is always its own page and never needs to hide it.

Binding a view param into an expression is a KNOWN silent-failure mode (see
knowledge/perspective-bindings.md and the "view params can fail silently"
note): the binding can render with every literal correct and the parameter
value simply missing, with no error anywhere. There is no way to avoid that
risk here (the whole point is a runtime-supplied camera/hud/header), so this
generator's caller MUST verify the rendered `src` attribute in the live DOM
before calling the work done - do not trust the JSON alone.

Run: python3 tools/build_cell3d_view.py
"""

import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.join(HERE, os.pardir, "project",
                     "com.inductiveautomation.perspective", "views", "Machine")
OUT = os.path.join(VIEWS, "Cell3D")

COL_BG = "var(--md-bg, #171b20)"

# The project NAME is not knowable at build time. The standard zip imports as
# Machine_HMI_Demo, the Edge one lands in whatever single project that Edge is
# configured to run, and a Designer import lets the operator type anything at
# all - which is exactly how this page came to 404 on a customer's gateway
# ("Project \"Machine_HMI_Demo\" not found"). So the project segment is
# resolved at RUNTIME, in the binding, by the session's own project.
#
# There is no session prop for it, so MachineDemo.ui.webdevUrl() asks
# system.project.getProjectName() in a script transform.
WEBDEV_RES = "cell3d"
PROVIDER = "MachineDemo"


def tag_binding(path, bidirectional=False):
    """A direct tag binding. `bidirectional` goes INSIDE config - at binding
    level it is accepted and silently never writes back."""
    cfg = {"mode": "direct", "tagPath": "[%s]%s" % (PROVIDER, path),
           "fallbackDelay": 2.5}
    if bidirectional:
        cfg["bidirectional"] = True
    return {"type": "tag", "config": cfg}


def expr_binding(expression):
    return {"type": "expr", "config": {"expression": expression}}


def bind(node, prop_path, expression):
    node.setdefault("propConfig", {})[prop_path] = {
        "binding": expr_binding(expression)
    }
    return node


# --- header (kept byte-for-byte identical to what CadModel expects to find) -
# t1/t2 text, the RobotState badge and the Overview button are unchanged from
# before params existed - tools/build_cad_view.py's find() calls still land on
# the same names, and the copied node still carries the Overview button's own
# event config (the one place a missing "scope" key would 500 the project).
header = {
    "type": "ia.container.flex",
    "meta": {"name": "Header"},
    "position": {"shrink": 0},
    "props": {
        "direction": "row",
        "alignItems": "center",
        "style": {
            "backgroundColor": "var(--md-panel, #1d232a)",
            "borderBottom": "1px solid var(--md-line, #2c343d)",
            "padding": "9px 16px",
            "gap": "14px",
        },
    },
    "children": [
        {
            "type": "ia.container.flex",
            "meta": {"name": "Title"},
            "position": {"grow": 1},
            "props": {"direction": "column", "style": {"gap": "1px"}},
            "children": [
                {
                    "type": "ia.display.label",
                    "meta": {"name": "t1"},
                    "props": {
                        "text": "Zone 2 · Robot Cell 2 — Live 3D",
                        "style": {
                            "fontSize": "16px",
                            "color": "var(--md-ink-max, #f2f6f8)",
                            "fontWeight": "bold",
                        },
                    },
                    "position": {"shrink": 0},
                },
                {
                    "type": "ia.display.label",
                    "meta": {"name": "t2"},
                    "props": {
                        "text": "Built from the parts list in Machine/Scene\u2019s custom props, driven by the same [MachineDemo] tags as every other screen",
                        "style": {
                            "fontSize": "11.5px",
                            "color": "var(--md-ink-quiet, #8b98a3)",
                            "fontWeight": "normal",
                        },
                    },
                    "position": {"shrink": 0},
                },
            ],
        },
        {
            "type": "ia.display.label",
            "meta": {"name": "RobotState"},
            "position": {"shrink": 0},
            "props": {
                "text": "",
                "style": {
                    "fontSize": "11px",
                    "fontWeight": "bold",
                    "letterSpacing": ".06em",
                    "textTransform": "uppercase",
                    "borderRadius": "4px",
                    "padding": "3px 9px",
                    "backgroundColor": "var(--md-info-bg-2, #14313e)",
                    "color": "var(--md-info, #6cc4e8)",
                    "border": "1px solid var(--md-info-line, #1e546c)",
                },
            },
            "propConfig": {
                "props.text": {
                    "binding": {
                        "type": "tag",
                        "config": {
                            "mode": "direct",
                            "tagPath": "[MachineDemo]Robot/State",
                        },
                    }
                }
            },
        },
        {
            # Opens the geometry panel beside the 3D view. CadModel's builder
            # copies this header and strips THIS node by name - a toggle for a
            # panel that view does not have would be an inert button.
            "type": "ia.input.button",
            "meta": {"name": "GeomToggle"},
            "position": {"shrink": 0},
            "props": {
                "text": "Geometry",
                "style": {
                    "backgroundColor": "var(--md-well, #262e36)",
                    "color": "var(--md-ink-mid, #cdd6dd)",
                    "border": "1px solid var(--md-line-soft, #38424c)",
                    "borderRadius": "7px",
                    "fontWeight": "bold",
                    "fontSize": "12.5px",
                    "minHeight": "38px",
                    "padding": "0 16px",
                    "alignItems": "center",
                },
            },
            # Lit while the drawer is out, the same way the page's own camera
            # buttons show which one is selected. A toggle that looks identical
            # in both states is a toggle nobody trusts.
            "propConfig": {
                "props.style.backgroundColor": {"binding": expr_binding(
                    'if({view.custom.geometry}, "var(--md-info-bg-2, #14313e)", "var(--md-well, #262e36)")')},
                "props.style.color": {"binding": expr_binding(
                    'if({view.custom.geometry}, "var(--md-info-ink, #9fdcf5)", "var(--md-ink-mid, #cdd6dd)")')},
                "props.style.borderColor": {"binding": expr_binding(
                    'if({view.custom.geometry}, "var(--md-info-line, #1e546c)", "var(--md-line-soft, #38424c)")')},
            },
            "events": {
                "component": {
                    "onActionPerformed": {
                        "type": "script",
                        "scope": "G",
                        "config": {"script": "\tself.view.custom.geometry = not self.view.custom.geometry\n"},
                    }
                }
            },
        },
        {
            "type": "ia.input.button",
            "meta": {"name": "BackToOverview"},
            "position": {"shrink": 0},
            "props": {
                "text": "Overview",
                "style": {
                    "backgroundColor": "var(--md-well, #262e36)",
                    "color": "var(--md-ink-mid, #cdd6dd)",
                    "border": "1px solid var(--md-line-soft, #38424c)",
                    "borderRadius": "7px",
                    "fontWeight": "bold",
                    "fontSize": "12.5px",
                    "minHeight": "38px",
                    "padding": "0 16px",
                    # This is the only button in the project that fixes
                    # minHeight rather than growing to fit its content, and
                    # ia.input.button renders as display:flex with
                    # align-items:normal - its inner content wrapper (a fixed
                    # 25px) then sits at the TOP of the 38px box instead of
                    # centred, riding the label 5.5px high. Every other
                    # button has min-height 0 and centres by construction, so
                    # only this one needs the explicit override. Measured on
                    # /cell3d at 1366x768, 02/09/2026.
                    "alignItems": "center",
                },
            },
            "events": {
                "component": {
                    "onActionPerformed": {
                        "type": "script",
                        "scope": "G",
                        "config": {"script": "\tsystem.perspective.navigate(page='/')\n"},
                    }
                }
            },
        },
    ],
}

# The wrapper is the ONLY place the header param is consulted. It is a plain
# pass-through flex container: unstyled, single child, "shrink": 0 so a
# column-direction parent never stretches it - the header keeps its natural
# height when shown and disappears (and gives its space back to the iframe)
# when the header param is false.
header_slot = {
    "type": "ia.container.flex",
    "meta": {"name": "HeaderSlot"},
    "position": {"shrink": 0},
    "props": {"direction": "column"},
    "children": [header],
}
bind(header_slot, "meta.visible", "{view.params.header}")

# --- the embeddable 3D panel --------------------------------------------------
# The relative WebDev path never changes; only the query string does, built
# entirely from view params so the SAME view produces a different URL per
# embed. if() rather than a numeric cast keeps the "1"/"0" the page's own
# ?hud= parsing already expects (see docs/CONTRACT.md).
cell_iframe = {
    "type": "ia.display.iframe",
    "meta": {"name": "Cell3D"},
    "position": {"grow": 1, "basis": "0px"},
    "props": {
        # Left empty on purpose: the binding below is the only thing that ever
        # produces a working URL, and a plausible-looking literal here would
        # just be a second project name to get wrong.
        "src": "",
        # WCAG 2.1 AA: ia.display.iframe has no `title` prop to set (checked
        # against PerspectiveComponents' own IFrame render - it destructures
        # only style/src/srcDoc/sandbox/allowFullScreen/referrerPolicy) and
        # Chromium does not paint an `outline` on a focused <iframe> at all,
        # even forced with an injected !important rule (a11y.json exceptions
        # axe:frame-title and focus:no-focus-ring).
        "style": {
            "height": "100%",
            "width": "100%",
            "border": "none",
            "minHeight": "0",
        },
    },
}
bind(
    cell_iframe,
    "props.src",
    '"?camera=" + {view.params.camera}'
    ' + "&hud=" + if({view.params.hud}, "1", "0")'
    ' + "&theme=" + {view.params.theme}'
    ' + "&watermark=" + if({view.params.watermark}, "1", "0")'
    ' + if({view.params.scene} = "", "", "&scene=" + {view.params.scene})',
)
cell_iframe["propConfig"]["props.src"]["binding"]["transforms"] = [
    {"type": "script", "code": '\treturn MachineDemo.ui.webdevUrl("%s", value)' % WEBDEV_RES}]

# --- the geometry panel ------------------------------------------------------
# Fifteen numeric entry fields, each bound BIDIRECTIONALLY to one of the
# [MachineDemo]Config tags. No script anywhere in it: typing 350 into CaseH
# writes the tag, the simulator re-derives the pattern on its next tick and the
# 3D page rebuilds on its next poll. That is the whole mechanism, and it is the
# demo's argument - the 3D model is fed by tags exactly the way a Perspective
# component is, and here it is being edited from Perspective.

INK = "var(--neutral-90, #dde4e9)"
DIM = "var(--neutral-60, #8b98a3)"
PANEL = "var(--neutral-20, #1d232a)"
LINE = "var(--neutral-40, #2c343d)"


def label(name, text, size="11px", color=DIM, extra=None, basis="auto"):
    style = {"fontSize": size, "color": color, "whiteSpace": "nowrap",
             "overflow": "hidden", "textOverflow": "ellipsis"}
    if extra:
        style.update(extra)
    return {"type": "ia.display.label", "version": 0, "meta": {"name": name},
            "position": {"grow": 0, "shrink": 0, "basis": basis},
            "props": {"text": text, "style": style}}


def field(tag, caption):
    """One geometry value: a caption over a numeric entry field bound to the tag."""
    name = tag.replace("_mm", "")
    return {
        "type": "ia.container.flex", "version": 0,
        "meta": {"name": "F_" + name},
        "position": {"grow": 1, "shrink": 1, "basis": "0px"},
        "props": {"direction": "column", "style": {"gap": "2px", "minWidth": "0px"}},
        "children": [
            label("K", caption, "11px", DIM, {"letterSpacing": "0.4px"}, "15px"),
            {
                "type": "ia.input.numeric-entry-field", "version": 0,
                "meta": {"name": "V"},
                "position": {"grow": 0, "shrink": 0, "basis": "32px"},
                "props": {
                    "inputType": "integer",
                    "value": 0,
                    "style": {"fontSize": "13px", "fontWeight": "bold",
                              "minWidth": "0px"},
                },
                "propConfig": {
                    "props.value": {"binding": tag_binding("Config/" + tag, True)}
                },
            },
        ],
    }


def group(title, fields):
    return {
        "type": "ia.container.flex", "version": 0,
        "meta": {"name": "G_" + title.split(" ")[0].replace("(", "")},
        "position": {"grow": 0, "shrink": 0, "basis": "auto"},
        "props": {"direction": "column", "style": {"gap": "3px"}},
        "children": [
            label("H", title, "11px", INK, {"fontWeight": "bold",
                  "letterSpacing": "0.6px", "textTransform": "uppercase"}, "16px"),
            {
                "type": "ia.container.flex", "version": 0,
                "meta": {"name": "Row"},
                "position": {"grow": 0, "shrink": 0, "basis": "auto"},
                "props": {"direction": "row", "style": {"gap": "8px"}},
                "children": [field(t, c) for t, c in fields],
            },
        ],
    }


def preset(key, text):
    return {
        "type": "ia.input.button", "version": 0,
        "meta": {"name": "P_" + key.replace("-", "_")},
        "position": {"grow": 1, "shrink": 1, "basis": "0px"},
        "props": {
            "text": text,
            "style": {"fontSize": "11px", "fontWeight": 700,
                      "letterSpacing": "0.3px", "borderRadius": "6px",
                      "border": "1px solid var(--md-line, #2c343d)",
                      "backgroundColor": "var(--md-face, #252c34)", "color": "var(--md-ink-body, #cfd8df)",
                      "padding": "0px", "minWidth": "0px", "minHeight": "34px",
                      "alignItems": "center", "whiteSpace": "nowrap"},
        },
        "events": {"component": {"onActionPerformed": {
            "type": "script", "scope": "G",
            "config": {"script": "\tMachineDemo.api.setGeometry(%r)\n" % key},
        }}},
    }


# The drawer is TWO containers, and it has to be.
#
# `meta.visible: false` was the obvious way to close it and it does not work
# here: Perspective renders a meta-hidden component with the class
# `component-meta-hidden`, which is `visibility: hidden` and NOT
# `display: none`. The panel disappears and keeps its 312px of the flex row
# for ever, so the 3D view sat at 1054px whether the panel was open or shut -
# measured on the gateway 04/09/2026, identical iframe AND canvas widths in
# both states. It hides the drawer; it never gives the space back.
#
# So the OUTER container owns the width (0 or 312, bound to the same custom
# prop, with a transition so it slides) and clips what does not fit, while the
# INNER one keeps a fixed 312px and carries everything that makes the panel
# look like a panel - the background, the border and the padding. Padding on
# the outer would hold it open at 28px when collapsed, because a border-box
# element cannot be narrower than its own padding.
#
# meta.visible stays, on the inner: with the outer collapsed the content is
# clipped, but its fifteen fields would still be reachable by Tab, and a form
# nobody can see is not one anybody should be able to type into.

geom_body = {
    "type": "ia.container.flex",
    "meta": {"name": "GeomBody"},
    "position": {"grow": 1, "shrink": 0, "basis": "auto"},
    "props": {
        "direction": "column",
        "style": {
            "width": "312px",
            "minWidth": "312px",
            "backgroundColor": PANEL,
            "borderLeft": "1px solid " + LINE,
            "padding": "12px 14px",
            "gap": "8px",
            "overflow": "auto",
            "minHeight": "0px",
        },
    },
    "propConfig": {
        "meta.visible": {"binding": {"type": "property",
                                     "config": {"path": "view.custom.geometry"}}}
    },
    "children": [
        label("T", "Machine geometry", "13px", INK, {"fontWeight": "bold"}, "18px"),
        label("S", "[%s]Config \u2014 15 tags. Edit one and the cell, the "
              "pattern and the arm follow." % PROVIDER, "11px", DIM,
              {"whiteSpace": "normal", "lineHeight": "15px"}, "30px"),
        {
            "type": "ia.container.flex", "version": 0,
            "meta": {"name": "Presets"},
            "position": {"grow": 0, "shrink": 0, "basis": "34px"},
            "props": {"direction": "row", "style": {"gap": "6px"}},
            "children": [preset("default", "Default"),
                         preset("euro-tall", "Euro, tall"),
                         preset("small-dense", "Small, dense")],
        },
        group("Case (mm)", [("CaseW_mm", "WIDTH"), ("CaseD_mm", "DEPTH"),
                            ("CaseH_mm", "HEIGHT")]),
        group("Pallet (mm)", [("PalletW_mm", "WIDTH"), ("PalletD_mm", "DEPTH"),
                              ("PalletH_mm", "DECK")]),
        group("Pattern", [("CasesPerLayer", "CASES / LAYER"), ("Layers", "LAYERS")]),
        group("Infeed conveyor (mm)", [("ConvHeight_mm", "HEIGHT"),
                                       ("ConvLength_mm", "LENGTH"),
                                       ("ConvWidth_mm", "WIDTH")]),
        # One row of four, not two groups of two: measured at 1024x600 the
        # panel content was 643px in a 543px column and Station 2 sat below
        # the fold. Four 65px fields hold "-1,300" at 13px bold with room.
        group("Stations (mm from robot)", [("Station1_X_mm", "1 \u00b7 X"),
                                           ("Station1_Z_mm", "1 \u00b7 Z"),
                                           ("Station2_X_mm", "2 \u00b7 X"),
                                           ("Station2_Z_mm", "2 \u00b7 Z")]),
        {
            "type": "ia.display.label", "version": 0,
            "meta": {"name": "Derived"},
            "position": {"grow": 0, "shrink": 0, "basis": "auto"},
            "props": {"text": "", "style": {"fontSize": "11px", "color": DIM,
                                            "whiteSpace": "normal",
                                            "lineHeight": "15px",
                                            "paddingTop": "4px",
                                            "borderTop": "1px solid " + LINE}},
            "propConfig": {"props.text": {"binding": expr_binding(
                '"Pallet of " + toStr({[%s]Config/CasesPerLayer} * {[%s]Config/Layers})'
                ' + " cases, pattern " + {[%s]Pallet/Station1/PatternName}'
                ' + ". Reach is checked by the simulator and shown on the 3D view."'
                % (PROVIDER, PROVIDER, PROVIDER))}},
        },
    ],
}

geom_panel = {
    "type": "ia.container.flex",
    "meta": {"name": "GeomPanel"},
    # basis auto, not a width: a flex-basis outranks the bound style width
    # below and would pin the drawer open at whatever the basis said.
    "position": {"grow": 0, "shrink": 0, "basis": "auto"},
    "props": {
        "direction": "column",
        "style": {
            "width": "0px",
            "overflow": "hidden",
            "minWidth": "0px",
            "minHeight": "0px",
            # Slides rather than jumps. It is a menu, and a menu that appears
            # instantly at full width reads as the page breaking.
            "transition": "width .22s ease",
        },
    },
    "propConfig": {
        "props.style.width": {"binding": expr_binding(
            'if({view.custom.geometry}, "312px", "0px")')}
    },
    "children": [geom_body],
}

body = {
    "type": "ia.container.flex",
    "meta": {"name": "Body"},
    "position": {"grow": 1, "shrink": 1, "basis": "0px"},
    "props": {"direction": "row", "style": {"minHeight": "0px"}},
    "children": [cell_iframe, geom_panel],
}

view = {
    "custom": {"geometry": False},
    "params": {
        "camera": "overview",
        "hud": True,
        "header": True,
        # Static fallback only - never what actually resolves when nothing
        # overrides the param. The binding below is what makes this follow
        # the session by default; this literal only matters if that binding
        # itself somehow fails to evaluate.
        "theme": "dark-cool",
        # The page says, quietly, that it is WebDev and three.js rather than a
        # Perspective component. Every other screen in this project IS
        # Perspective and this one is deliberately styled to match, so the one
        # architectural fact a viewer cannot see from the screen is the one
        # worth printing on it. Off for a clean screenshot, or when the view is
        # embedded somewhere the distinction has already been made.
        "watermark": True,
        # "" leaves the page on its own default, which is the scene document -
        # the parts list in Machine/Scene's custom props, the one a machine
        # builder can edit in the Designer. "code" selects the hand-written
        # JavaScript build instead; tools/verify/scene_parity.js asserts the
        # two produce the same objects.
        "scene": "",
    },
    # A view's declared params are just default values unless each one is ALSO
    # marked paramDirection "input" here - the Designer does this invisibly
    # when a param is added through its Params editor, but a hand-authored
    # view.json has to say it explicitly, or the value an embedder passes in
    # never reaches view.params: it silently stays on its own default with no
    # error anywhere (see the popup-params gotcha in perspective-bindings.md,
    # and reference-perspective-popup-params-and-table-events.md - the same
    # trap, at the view-embedding boundary instead of openPopup).
    "propConfig": {
        "params.camera": {"paramDirection": "input", "persistent": True},
        "params.hud": {"paramDirection": "input", "persistent": True},
        "params.header": {"paramDirection": "input", "persistent": True},
        # theme carries a BINDING as well as paramDirection: input. The
        # binding is what makes an unembedded/no-override view follow
        # {session.props.theme} - a param with only a static default would
        # sit on "dark-cool" forever even as the session theme changed. An
        # Embedded View's own param override still wins over this binding,
        # same as it wins over camera/hud/header's static defaults.
        "params.theme": {
            "paramDirection": "input",
            "persistent": True,
            "binding": expr_binding("{session.props.theme}"),
        },
        "params.watermark": {"paramDirection": "input", "persistent": True},
        "params.scene": {"paramDirection": "input", "persistent": True},
    },
    "props": {"defaultSize": {"width": 1366, "height": 768}},
    "root": {
        "type": "ia.container.flex",
        "meta": {"name": "Page"},
        "props": {
            "direction": "column",
            "style": {
                "height": "100%",
                "overflow": "hidden",
                "minHeight": "0",
                "backgroundColor": COL_BG,
            },
        },
        "children": [header_slot, body],
    },
}

resource = {
    "scope": "G",
    "version": 1,
    "restricted": False,
    "overridable": True,
    "files": ["view.json"],
    # A timestamp that does not move makes the scan skip the resource on
    # every rebuild after the first - the file changes and the gateway never
    # notices. No lastModificationSignature key - its presence, even stale,
    # makes the scan treat the resource as already-known and skip it too.
    "attributes": {
        "lastModification": {
            "actor": "external",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    },
}

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "view.json"), "w") as f:
    json.dump(view, f, indent=2)
with open(os.path.join(OUT, "resource.json"), "w") as f:
    json.dump(resource, f, indent=2)

print("wrote %s" % OUT)
