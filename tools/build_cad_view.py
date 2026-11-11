#!/usr/bin/env python3
"""Build Machine/CadModel and Machine/CadModels - the customer's own CAD.

The page itself is the WebDev resource `cadview` (source src/cadview/page.html):
the model, orbit/zoom/pan/pick and the part alarm panel. Machine/CadModel is
the Perspective wrapper: the project's standard header carrying a model
selector and a Models button, and an iframe. Machine/CadModels is the popup
that uploads and deletes models - through the session, because HTTP stays
read-only (docs/CONTRACT.md).

The header is DEEP-COPIED from Machine/Cell3D rather than rebuilt, so the three
full-bleed model screens cannot drift apart - same heights, same fonts, same
Back button, same event shape. The Geometry toggle is dropped: it edits the
palletising cell's [MachineDemo]Config tags, which have nothing to do with an
arbitrary customer model.

Cell3D must be generated first (tools/build_cell3d_view.py) - this reads it.

Run: python3 tools/build_cad_view.py
"""

import copy
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.join(HERE, os.pardir, "project",
                     "com.inductiveautomation.perspective", "views", "Machine")
SRC = os.path.join(VIEWS, "Cell3D", "view.json")
OUT = os.path.join(VIEWS, "CadModel")

COL_BG = "var(--md-bg, #171b20)"

WEBDEV_RES = "cadview"

TITLE = "Zone 2 · Robot Cell 2 — CAD model"
SUBTITLE = "Built-in or uploaded STL / STEP - alarms linked by part number"

POPUP_VIEW = "Machine/CadModels"
SIM_VIEW = "Machine/CadSim"
SIM_ID = "cadSim"
POPUP_ID = "cadModels"
MSG = "cadModelChanged"
BUILTIN = "_builtin"


def find(node, name):
    if node.get("meta", {}).get("name") == name:
        return node
    for child in node.get("children", []):
        hit = find(child, name)
        if hit:
            return hit
    return None


def drop(node, name):
    """Remove a named child anywhere below `node`. Quiet if it is not there."""
    kids = node.get("children")
    if kids is None:
        return False
    for i, child in enumerate(kids):
        if child.get("meta", {}).get("name") == name:
            del kids[i]
            return True
        if drop(child, name):
            return True
    return False


src = json.load(open(SRC))
header_slot = copy.deepcopy(find(src["root"], "HeaderSlot"))
if header_slot is None:
    raise SystemExit("Cell3D has no HeaderSlot - run build_cell3d_view.py first")

# HeaderSlot's own visibility is bound to Cell3D's `header` param, which this
# view does not declare. A binding on a param that does not exist evaluates to
# null and the header disappears - silently. This view is always its own page,
# so the switch is simply removed rather than reproduced.
header_slot.pop("propConfig", None)

drop(header_slot, "GeomToggle")
find(header_slot, "Heading")["props"]["text"] = TITLE
find(header_slot, "Subheading")["props"]["text"] = SUBTITLE
# RobotState reads the cell's own tags; a CAD model has none.
drop(header_slot, "RobotState")

cad_iframe = {
    "type": "ia.display.iframe",
    "meta": {"name": "CadModel"},
    "position": {"grow": 1, "basis": "0px"},
    "props": {
        "src": "",
        # WCAG 2.1 AA: ia.display.iframe has no `title` prop to set (checked
        # against PerspectiveComponents' own IFrame render - it destructures
        # only style/src/srcDoc/sandbox/allowFullScreen/referrerPolicy) and
        # Chromium does not paint an `outline` on a focused <iframe> at all,
        # even forced with an injected !important rule (a11y.json exceptions
        # axe:frame-title and focus:no-focus-ring).
        "style": {"height": "100%", "width": "100%",
                  "border": "none", "minHeight": "0"},
    },
    "propConfig": {
        # rev changes after every upload/delete, so a re-uploaded model of the
        # same name reloads instead of showing the old one.
        "props.src": {
            "binding": {
                "type": "expr",
                "config": {"expression": '"?v=" + {view.custom.rev}'
                                         + ' + if({view.custom.model} = "' + BUILTIN + '" ||'
                                         + ' {view.custom.model} = "", "",'
                                         + ' "&model=" + {view.custom.model})'},
                # The project name is only known at runtime, under any import name.
                "transforms": [{"type": "script", "code":
                                '\treturn MachineDemo.ui.webdevUrl("%s", value)' % WEBDEV_RES}],
            }
        }
    },
}

# Header controls, between the title and the Overview button. Same well, line
# and height as the Overview button so the header reads as one row.
BTN_STYLE = copy.deepcopy(find(header_slot, "BackToOverview")["props"]["style"])
header = find(header_slot, "Header")
back = find(header_slot, "BackToOverview")
model_pick = {
    "type": "ia.input.dropdown",
    "meta": {"name": "ModelPick"},
    "position": {"shrink": 0, "basis": "260px"},
    "props": {
        "placeholder": "Model",
        "showClearIcon": False,
        "style": {"minHeight": "38px", "fontSize": "12.5px",
                  "backgroundColor": BTN_STYLE["backgroundColor"],
                  "color": BTN_STYLE["color"], "border": BTN_STYLE["border"],
                  "borderRadius": BTN_STYLE["borderRadius"]},
    },
    "propConfig": {
        # view.custom.rev changes after an upload or delete, which re-reads the list.
        "props.options": {"binding": {"type": "property", "config": {"path": "view.custom.rev"}, "transforms": [{"type": "script", "code": "\treturn MachineDemo.cad.options(value)"}]}},
        "props.value": {"binding": {"type": "property", "config": {
            "path": "view.custom.model", "bidirectional": True}}},
    },
}
models_btn = {
    "type": "ia.input.button",
    "meta": {"name": "ManageModels"},
    "position": {"shrink": 0},
    "props": {"text": "Upload / delete", "style": copy.deepcopy(BTN_STYLE)},
    "events": {"component": {"onActionPerformed": {
        "type": "script", "scope": "G",
        "config": {"script": (
            "\tsystem.perspective.openPopup(%r, %r, title=%r, modal=True,\n"
            "\t\tshowCloseIcon=True, draggable=False, resizable=False,\n"
            "\t\tviewportBound=True, position={'width': 560, 'height': 500})\n"
            % (POPUP_ID, POPUP_VIEW, "CAD models"))}}}},
}
sim_btn = {
    "type": "ia.input.button",
    "meta": {"name": "SimulateAlarm"},
    "position": {"shrink": 0},
    "props": {"text": "Simulate alarm", "style": copy.deepcopy(BTN_STYLE)},
    "events": {"component": {"onActionPerformed": {
        "type": "script", "scope": "G",
        "config": {"script": (
            "\tsystem.perspective.openPopup(%r, %r, title=%r, modal=True,\n"
            "\t\tparams={'model': self.view.custom.model},\n"
            "\t\tshowCloseIcon=True, draggable=False, resizable=False,\n"
            "\t\tviewportBound=True, position={'width': 600, 'height': 420})\n"
            % (SIM_ID, SIM_VIEW, "Simulate a part alarm"))}}}},
}
kids = header["children"]
kids.insert(kids.index(back), model_pick)
kids.insert(kids.index(back), models_btn)
kids.insert(kids.index(back), sim_btn)

view = {
    "custom": {"model": BUILTIN, "rev": 0},
    "params": {},
    "propConfig": {},
    "props": {"defaultSize": {"width": 1366, "height": 768}},
    "root": {
        "type": "ia.container.flex",
        "meta": {"name": "Page"},
        "scripts": {
            "customMethods": [],
            "extensionFunctions": None,
            "messageHandlers": [{
                "messageType": MSG,
                "pageScope": True,
                "sessionScope": False,
                "viewScope": False,
                "script": (
                    "\tMachineDemo.ui.applyModelChange(self.view.custom, payload)\n"),
            }],
        },
        "props": {
            "direction": "column",
            "style": {"height": "100%", "overflow": "hidden",
                      "minHeight": "0", "backgroundColor": COL_BG},
        },
        "children": [
            header_slot,
            {
                "type": "ia.container.flex",
                "meta": {"name": "Body"},
                "position": {"grow": 1, "shrink": 1, "basis": "0px"},
                "props": {"direction": "row", "style": {"minHeight": "0px"}},
                "children": [cad_iframe],
            },
        ],
    },
}

resource = {
    "scope": "G",
    "version": 1,
    "restricted": False,
    "overridable": True,
    "files": ["view.json"],
    # A stale timestamp makes the scan skip the resource silently, and a
    # lastModificationSignature key does the same even when it is wrong.
    "attributes": {
        "lastModification": {
            "actor": "external",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    },
}

os.makedirs(OUT, exist_ok=True)
json.dump(view, open(os.path.join(OUT, "view.json"), "w"), indent=2)
json.dump(resource, open(os.path.join(OUT, "resource.json"), "w"), indent=2)
print("wrote %s" % OUT)


# ---------------------------------------------------------------------------
# Machine/CadModels - the upload / delete popup
# ---------------------------------------------------------------------------

INK = "var(--md-ink-mid, #cdd6dd)"
QUIET = "var(--md-ink-quiet, #8b98a3)"


def label(name, text, **style):
    st = {"fontSize": "12.5px", "color": INK}
    st.update(style)
    return {"type": "ia.display.label", "meta": {"name": name},
            "position": {"shrink": 0}, "props": {"text": text, "style": st}}


def heading(name, text):
    return label(name, text, fontSize="12px", fontWeight="bold",
                 letterSpacing="1.2px", textTransform="uppercase", color=QUIET)


UPLOAD_SCRIPT = """\tmsg = MachineDemo.ui.uploadModel(self.view.custom, event.file)
\tif msg:
\t\tsystem.perspective.sendMessage("@MSG@", payload=msg, scope="page")
""".replace("@MSG@", MSG)

# Two presses: the first arms the button for that model, the second deletes.
# A confirm popup over a popup is one more thing to dismiss on a touch panel.
DELETE_SCRIPT = """\tmsg = MachineDemo.ui.deleteModel(self.view.custom)
\tif msg:
\t\tsystem.perspective.sendMessage("@MSG@", payload=msg, scope="page")
""".replace("@MSG@", MSG)

popup = {
    "custom": {"status": "", "ok": True, "armed": "", "rev": 0,
               "name": "", "delModel": None},
    "params": {},
    "propConfig": {},
    "props": {"defaultSize": {"width": 560, "height": 460}},
    "root": {
        "type": "ia.container.flex",
        "meta": {"name": "root"},
        "props": {"direction": "column", "style": {
            "padding": "14px 18px", "gap": "9px", "overflow": "hidden",
            "backgroundColor": "var(--md-panel, #1d232a)"}},
        "children": [
            heading("UploadHead", "Upload a model"),
            label("UploadHelp",
                  "A binary STL (one part), a zip of STLs (one part per file, "
                  "named from the file) or a STEP file (.step/.stp - parts from "
                  "its assembly). Up to 50 MB. A model of the same name is "
                  "replaced.", color=QUIET, whiteSpace="normal",
                  lineHeight="1.45"),
            {"type": "ia.input.text-field", "meta": {"name": "Name"},
             "position": {"shrink": 0},
             # deferUpdates off: the upload fires while the field still has
             # focus, before a deferred value would be committed.
             "props": {"placeholder": "Model name - leave empty to use the file name",
                       "deferUpdates": False,
                       "style": {"minHeight": "36px", "fontSize": "12.5px"}},
             "propConfig": {"props.text": {"binding": {"type": "property", "config": {
                 "path": "view.custom.name", "bidirectional": True}}}}},
            {"type": "ia.input.fileupload", "meta": {"name": "Upload"},
             "position": {"shrink": 0, "basis": "150px"},
             "props": {"supportedFileTypes": ["stl", "zip", "step", "stp"],
                       "fileSizeLimit": 50, "maxUploads": 1},
             "events": {"component": {"onFileReceived": {
                 "type": "script", "scope": "G",
                 "config": {"script": UPLOAD_SCRIPT}}}}},
            heading("DeleteHead", "Delete an uploaded model"),
            {"type": "ia.container.flex", "meta": {"name": "DeleteRow"},
             "position": {"shrink": 0},
             "props": {"direction": "row", "alignItems": "center",
                       "style": {"gap": "10px"}},
             "children": [
                 {"type": "ia.input.dropdown", "meta": {"name": "DelModel"},
                  "position": {"grow": 1, "basis": "0px"},
                  "props": {"placeholder": "Uploaded models",
                            "style": {"minHeight": "38px", "fontSize": "12.5px"}},
                  "propConfig": {
                      "props.options": {"binding": {"type": "property", "config": {"path": "view.custom.rev"}, "transforms": [{"type": "script", "code": "\treturn MachineDemo.cad.uploadedOptions(value)"}]}},
                      "props.value": {"binding": {"type": "property", "config": {
                          "path": "view.custom.delModel", "bidirectional": True}}}}},
                 {"type": "ia.input.button", "meta": {"name": "Delete"},
                  "position": {"shrink": 0, "basis": "190px"},
                  "props": {"style": copy.deepcopy(BTN_STYLE)},
                  "propConfig": {"props.text": {"binding": {
                      "type": "expr", "config": {"expression":
                          'if({view.custom.armed} != "" && {view.custom.armed} = '
                          '{view.custom.delModel}, "Press again to delete", "Delete")'}}}},
                  "events": {"component": {"onActionPerformed": {
                      "type": "script", "scope": "G",
                      "config": {"script": DELETE_SCRIPT}}}}},
             ]},
            {"type": "ia.display.label", "meta": {"name": "Status"},
             "position": {"shrink": 0},
             "props": {"style": {"fontSize": "12.5px", "whiteSpace": "normal",
                                 "lineHeight": "1.45"}},
             "propConfig": {
                 "props.text": {"binding": {"type": "property",
                                            "config": {"path": "view.custom.status"}}},
                 "props.style.color": {"binding": {"type": "expr", "config": {
                     "expression": 'if({view.custom.ok}, "' + INK + '", '
                                   '"var(--md-fault-ink, #ff8d92)")'}}}}},
            label("Where", "Uploads are kept on the gateway in data/machine-demo-cad, "
                  "outside the project.", color=QUIET, fontSize="11.5px"),
        ],
    },
}

POP_OUT = os.path.join(VIEWS, "CadModels")
os.makedirs(POP_OUT, exist_ok=True)
json.dump(popup, open(os.path.join(POP_OUT, "view.json"), "w"), indent=2)
json.dump(resource, open(os.path.join(POP_OUT, "resource.json"), "w"), indent=2)
print("wrote %s" % POP_OUT)


# ---------------------------------------------------------------------------
# Machine/CadSim - simulate an alarm on any part of the model on screen
# ---------------------------------------------------------------------------

SLOTS = 4  # MachineDemo.tagdata.CAD_SIM_SLOTS

RAISE_SCRIPT = "\tMachineDemo.ui.simRaise(self.view.custom)\n"


def action(call, *args):
    return "\tMachineDemo.ui.simCommand(self.view.custom, %s)\n" % ", ".join((call,) + args)


def small_btn(name, text, script, enabled_path=None):
    b = {"type": "ia.input.button", "meta": {"name": name},
         "position": {"shrink": 0, "basis": "96px"},
         "props": {"text": text, "style": dict(copy.deepcopy(BTN_STYLE),
                                               minHeight="32px")},
         "events": {"component": {"onActionPerformed": {
             "type": "script", "scope": "G", "config": {"script": action(*script)}}}}}
    if enabled_path:
        b["propConfig"] = {"props.enabled": {"binding": {
            "type": "property", "config": {"path": enabled_path}}}}
    return b


def slot_row(i):
    return {"type": "ia.container.flex", "meta": {"name": "Slot%d" % i},
            "position": {"shrink": 0},
            "props": {"direction": "row", "alignItems": "center",
                      "style": {"gap": "8px"}},
            "children": [
                {"type": "ia.display.label", "meta": {"name": "Text"},
                 "position": {"grow": 1, "basis": "0px"},
                 "props": {"style": {"fontSize": "12.5px", "color": INK,
                                     "fontFamily": "monospace"}},
                 "propConfig": {"props.text": {"binding": {"type": "property",
                     "config": {"path": "view.custom.slots[%d].text" % (i - 1)}}}}},
                small_btn("Ack", "Ack", ("MachineDemo.cad.simAck", str(i)),
                          "view.custom.slots[%d].active" % (i - 1)),
                small_btn("Clear", "Clear", ("MachineDemo.cad.simClear", str(i)),
                          "view.custom.slots[%d].active" % (i - 1)),
            ]}


sim = {
    "custom": {"part": None, "priority": "High", "status": "", "ok": True, "rev": 0},
    "params": {"model": BUILTIN},
    "propConfig": {
        "params.model": {"paramDirection": "input", "persistent": True},
        "custom.slots": {"binding": {"type": "property", "config": {"path": "view.custom.rev"}, "transforms": [{"type": "script", "code": "\treturn MachineDemo.cad.simSlots(value)"}]}},
    },
    "props": {"defaultSize": {"width": 600, "height": 430}},
    "root": {
        "type": "ia.container.flex",
        "meta": {"name": "root"},
        "props": {"direction": "column", "style": {
            "padding": "14px 18px", "gap": "9px", "overflow": "hidden",
            "backgroundColor": "var(--md-panel, #1d232a)"}},
        "children": [
            heading("RaiseHead", "Raise an alarm on a part"),
            label("RaiseHelp",
                  "A real alarm on the demo's own tags, linked to the part by "
                  "its CadPart: it shows in the part alarm panel, tints the "
                  "part and is acknowledged like any other. %d at once." % SLOTS,
                  color=QUIET, whiteSpace="normal", lineHeight="1.45"),
            {"type": "ia.container.flex", "meta": {"name": "RaiseRow"},
             "position": {"shrink": 0},
             "props": {"direction": "row", "alignItems": "center",
                       "style": {"gap": "10px"}},
             "children": [
                 {"type": "ia.input.dropdown", "meta": {"name": "Part"},
                  "position": {"grow": 1, "basis": "0px"},
                  "props": {"placeholder": "Part of the model on screen",
                            "search": {"enabled": True},
                            "style": {"minHeight": "38px", "fontSize": "12.5px"}},
                  "propConfig": {
                      "props.options": {"binding": {"type": "expr-struct", "config": {
                          "struct": {"model": "{view.params.model}", "rev": "{view.custom.rev}"},
                          "waitOnAll": True}, "transforms": [{"type": "script", "code":
                          "\treturn MachineDemo.cad.partOptions(value.model, value.rev)"}]}},
                      "props.value": {"binding": {"type": "property", "config": {
                          "path": "view.custom.part", "bidirectional": True}}}}},
                 {"type": "ia.input.dropdown", "meta": {"name": "Priority"},
                  "position": {"shrink": 0, "basis": "130px"},
                  "props": {"options": [{"value": n, "label": n} for n in
                                        ["Diagnostic", "Low", "Medium", "High", "Critical"]],
                            "showClearIcon": False,
                            "style": {"minHeight": "38px", "fontSize": "12.5px"}},
                  "propConfig": {"props.value": {"binding": {"type": "property", "config": {
                      "path": "view.custom.priority", "bidirectional": True}}}}},
                 {"type": "ia.input.button", "meta": {"name": "Raise"},
                  "position": {"shrink": 0, "basis": "100px"},
                  "props": {"text": "Raise", "style": copy.deepcopy(BTN_STYLE)},
                  "events": {"component": {"onActionPerformed": {
                      "type": "script", "scope": "G",
                      "config": {"script": RAISE_SCRIPT}}}}},
             ]},
            heading("SlotsHead", "Simulated alarms"),
        ] + [slot_row(i) for i in range(1, SLOTS + 1)] + [
            {"type": "ia.container.flex", "meta": {"name": "AllRow"},
             "position": {"shrink": 0},
             "props": {"direction": "row", "alignItems": "center",
                       "style": {"gap": "8px"}},
             "children": [
                 {"type": "ia.display.label", "meta": {"name": "Status"},
                  "position": {"grow": 1, "basis": "0px"},
                  "props": {"style": {"fontSize": "12.5px", "whiteSpace": "normal"}},
                  "propConfig": {
                      "props.text": {"binding": {"type": "property",
                                                 "config": {"path": "view.custom.status"}}},
                      "props.style.color": {"binding": {"type": "expr", "config": {
                          "expression": 'if({view.custom.ok}, "' + INK + '", '
                                        '"var(--md-fault-ink, #ff8d92)")'}}}}},
                 small_btn("AckAll", "Ack all", ("MachineDemo.cad.simAck",)),
                 small_btn("ClearAll", "Clear all", ("MachineDemo.cad.simClear",)),
             ]},
        ],
    },
}

SIM_OUT = os.path.join(VIEWS, "CadSim")
os.makedirs(SIM_OUT, exist_ok=True)
json.dump(sim, open(os.path.join(SIM_OUT, "view.json"), "w"), indent=2)
json.dump(resource, open(os.path.join(SIM_OUT, "resource.json"), "w"), indent=2)
print("wrote %s" % SIM_OUT)
