# The CAD viewer — showing a customer's own 3D model

A machine builder has CAD. This page puts it on a Perspective screen, lets an
operator turn it around, and shows which part of the machine an alarm is on —
without a third-party module, a licence or an internet connection.

It is deliberately **not** the palletising cell page. That one is a machine
that moves, driven by tags. This one shows a model, and colours the parts that
have alarms standing.

It has its own tab — **CAD** — on the project's nav bar, and its own page route
`/cad`. Directly, it is:

    http://<gateway>/system/webdev/<project>/cadview[?model=<name>]

No `model` is the built-in model; `?model=<name>` is an uploaded one.

## The screen

- **Model selector** (header) — the built-in model and every uploaded one.
  Switching it reloads the frame with `?model=`.
- **Upload / delete** (header) — opens the *CAD models* popup.
- **Part alarms** (right of the model) — the standing alarms whose part number
  is a part of the model on screen: part, alarm, priority, acknowledged or not,
  time. Polled every 2 s.
  - Click a row: the part is highlighted and framed.
  - Click a part in the model: the panel shows only that part's alarms. Click
    empty space, or the `part: …  ✕` chip, to show all again.
  - A part with an alarm standing is tinted red — pulsing while unacknowledged,
    steady once acknowledged, the same look as a fault on the 3D cell.
  - Rows that do not fit are counted (`+3 more`), not scrolled. Filter by part
    to see them.

## Uploading a model

From the popup, three kinds of file, up to 50 MB:

| File | Becomes | Part names |
| --- | --- | --- |
| `.stl` (binary) | a one-part model | the model name |
| `.zip` of binary `.stl` files | one model, one part per STL | each STL's file name |
| `.step` / `.stp` | one model, parts from its assembly tree | the STEP product names |

The model name defaults to the file name; type one in the popup to override
it. Names keep letters, digits, `-` and `_`; anything else becomes `_`. An
upload with the name of an existing model replaces it — re-uploading an
updated export is the normal case.

**Where uploads live:** `<gateway data dir>/machine-demo-cad/<model>/` — on the
Docker image, `/usr/local/bin/ignition/data/machine-demo-cad/`. Outside the
project, so an upload shows at once with no project scan, and a project export
or import neither carries nor overwrites them. Back them up with the gateway's
data directory; whether a gateway backup (`.gwbk`) includes them has not been
checked.

Delete is in the same popup and takes two presses. The built-in model cannot be
deleted from the screen; it is part of the project.

Upload and delete go through the Perspective session (`MachineDemo.cad.save` /
`.delete`, gateway scope). There is no HTTP write: the `cad` route only reads,
like every other route in this project.

What the upload refuses, with the reason on screen: ASCII STL, a zip with no
STL in it, a zip that unpacks to more than 200 MB or holds more than 500 STLs,
a STEP file without an `ISO-10303-21` header, and anything else by extension.
Zip entries are named from their base name only, so no entry path can write
outside the model's folder.

## Simulating an alarm on a part

**Simulate alarm** (header) opens a popup that raises a real alarm on any part
of the model on screen — built-in, zip, single STL or STEP:

1. Choose the part (the list is the shown model's parts) and a priority.
2. **Raise.** The alarm appears in the part alarm panel within 2 s and the
   part pulses red, exactly like a machine alarm — it *is* one.
3. **Ack** / **Clear** per slot, or **Ack all** / **Clear all**. RESET DEMO
   on Setup clears them too. They also show, and can be acknowledged, on the
   Alarms screen.

Behind it is a pool of four slots, `[MachineDemo]CadSim/Sim1..Sim4`, each a
`Part` string, a `Priority` integer (0 Diagnostic … 4 Critical) and an
`Active` boolean carrying the alarm *Simulated Part Alarm*. The alarm's
`CadPart` and priority are **bound** to the two sibling tags
(`{"bindType": "Tag", "value": "[.]Part"}`). A bound alarm property is read
when the alarm goes active and the standing event keeps it, so a raise
writes `Part` and `Priority` first and `Active` last (`MachineDemo.cad
.simRaise`).

- Raising the same part again re-uses its slot with the new priority.
- With all four slots holding other parts, Raise refuses — *all 4 simulation
  slots are in use - clear one first* — rather than take one over.
- Writes go through the Perspective session only.

**STEP part names are known only to the page**, which parses the file. After
parsing it POSTs the list of names to `cad?f=parts&model=<name>`, stored as
`parts.json` beside the model; that is where the popup's part list comes from
for a STEP model. It is the one HTTP write in the project: names only, into a
fixed file of an existing STEP model. So show a STEP model once before
simulating on it.

## Linking alarms to parts

An alarm names its part in **associated data** called **`CadPart`**. The CAD
page matches it — ignoring case — against the part names of the model on
screen: the STL file name, or the STEP product name.

The sample does it for three robot alarms, written by Setup with the tags
(`MachineDemo.tagdata.CAD_PARTS`):

| Alarm | `CadPart` | Raise it from Setup → presenter console |
| --- | --- | --- |
| Robot Fault (on the `RobotArm` UDT) | `base` | any robot fault below |
| Robot Axis Following Error | `upperarm` | Robot axis following error → INJECT |
| Gripper Vacuum Low | `wrist3` | Gripper vacuum low → INJECT |

So with the UR5 sample showing, **INJECT** on the robot axis fault lights
`upperarm` and `base`, and both appear in the panel.

To link your own alarms:

1. In the Designer, open the tag's alarm, add associated data
   (**+** under *Associated Data*), name it `CadPart`, value = the part
   name in your model. A UDT alarm takes it once on the type.
2. Or with `system.tag.configure`, put it on the alarm dict as a plain key:

   ```python
   {"name": "Spindle Overtemp", "mode": "AboveValue", "setpointA": 80.0,
    "priority": "High", "CadPart": "spindle-housing"}
   ```

3. Name the parts to match. For STL, that is the file name in the zip
   (`spindle-housing.stl`). For STEP, it is the product name in your CAD
   system — the name in the assembly tree. Click a part on the CAD page to see
   the name it was given.

The panel reads alarms from this demo's own tag provider
(`system.alarm.queryStatus`, source `prov:<provider>:/tag:*`), standing and
active only. An alarm on another provider is not shown — point
`MachineDemo.cad.alarms()` at it if your alarms live elsewhere.

The `alarms` row on Setup goes red if the three sample links are missing,
which is what a gateway set up before 1.19.0 shows until RUN SETUP is pressed
again.

## STEP in the browser

STEP is read on the page, not on the gateway, by
[occt-import-js](https://github.com/kovacsv/occt-import-js) 0.0.23 — the
OpenCASCADE STEP reader compiled to WebAssembly. It is vendored in the `lib`
resource and served by `lib?f=occt` and `lib?f=occt-wasm`, so it works with no
internet. Licence: **LGPL-2.1** (OCCT adds the Open CASCADE exception) — see
[NOTICE](../NOTICE).

- The `.wasm` is 7.6 MB and is fetched only when a STEP model is shown; the
  browser caches it after that.
- Each solid is named from its STEP product name — the name in the CAD
  assembly tree. Solids of one product (six identical bolts) are one part and
  light up together, which is what a part number means. The CAx-IF `as1` test
  assembly comes in as five parts from 18 solids: `plate`, `l-bracket`,
  `bolt`, `nut`, `rod`.
- STEP colours are kept where the file has them.
- Reading a large assembly takes seconds and happens on the page's own thread;
  the page says *Reading STEP…* until it is done.

## Changing the built-in model

1. Copy the `.stl` files into the project at
   `com.inductiveautomation.webdev/resources/cad/`
2. Add each filename to `files[]` in that folder's `resource.json` — a file on
   disk that is not listed there is skipped by the scan, silently, for good.
3. Config → Platform → Projects → **Scan File System**

To put the viewer on a screen of your own, drop an `ia.display.iframe` into a
Perspective view and build its `src` the way `Machine/CadModel` does, so it
keeps working when the project is called something else:

    MachineDemo.ui.webdevUrl("cadview", "")    # a script transform on the src binding

A literal project name in that `src` is the one mistake that turns this page
into `HTTP ERROR 404 Project "..." not found` on somebody else's gateway.

## Where the model sits

On load the whole model is moved once — centred on the grid in plan, its
lowest point on the grid — and the grid is sized to its footprint. Parts keep
their places relative to each other. CAD origins are wherever the designer
left them; three UR5 wrist parts arrived well off a grid drawn at the origin
before this.

## What STL costs you

- **Binary STL only.** ASCII STL is refused at upload. Most CAD exports binary
  by default; check the export dialog.
- **One file per part you want to select.** A single STL of a whole assembly is
  one pickable lump — STL carries no names, no colours and no structure. STEP
  does; upload STEP when you have it.
- **No units.** A model under 20 units across is read as metres (the UR5
  sample), anything bigger as millimetres. The size readout shows which way it
  went.
- **Where the parts land is a CAD export choice.** Parts exported from one
  assembly share that assembly's origin and arrive already fitted together.
  Parts exported individually each sit at their own origin and stack up.

## Three things that cost time, all of which fail silently

- **WebDev corrupts binary if you return it as `response`.** It encodes the
  byte array as text: a 28,984-byte STL arrived as 39,156 bytes of mojibake,
  with no error anywhere. Write to
  `request['servletResponse'].getOutputStream()` and return `None`. The STLs,
  the STEP file and the 7.6 MB `.wasm` are all served that way, verified
  byte-identical by md5.
- **Ignore the STL's own face normals** — `computeVertexNormals()` instead.
  Exporters write them inconsistently and an inverted set renders as a perfect
  black silhouette, which reads as a lighting or material bug and is neither.
- **A text field's value arrives on blur.** The popup's name field has
  `deferUpdates: false`; without it, a name typed and followed straight by a
  file drop is not there when the upload script reads it.

three.js r150+ removed the non-module `examples/js` loaders, so there is no
`STLLoader` or `OrbitControls` to vendor for the r160 UMD build this project
uses. Both are written out in the page instead.

## Where it is built

| Piece | Source |
| --- | --- |
| The page (`cadview` text resource) | `src/cadview/page.html` → `python3 tools/webdev_page.py build cadview` |
| `Machine/CadModel`, `Machine/CadModels` | `python3 tools/build_cad_view.py` |
| Storage, upload checks, part alarms | `MachineDemo.cad` |
| The routes | `cad` (models, parts, alarms), `lib` (three.js, occt-import-js) |

## The sample meshes

The seven UR5 meshes shipped in `resources/cad/` are from
**[ros-industrial/universal_robot](https://github.com/ros-industrial/universal_robot)**,
`ur_description`, and are licensed **BSD-3-Clause**. Authors: Wim Meeussen,
Kelsey Hawkins, Mathias Ludtke, Felix Messmer.

They are there so the page has something to show out of the box. Delete them and
drop your own in; nothing in the code refers to them by name except the three
sample alarm links above.

**If you take more meshes from that package, check the licence first.** The
UR20, UR30, UR8 Long, UR15 and UR18 meshes are **not** BSD — they are covered by
Universal Robots A/S' own Terms and Conditions for Use of Graphical
Documentation. UR5 and UR10 are BSD.
