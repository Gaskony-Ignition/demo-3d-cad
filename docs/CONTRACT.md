# Machine_HMI_Demo — build contract

A demonstration for machine builders evaluating Ignition as an HMI replacement
(Edge Panel on small machines, standard Ignition where there are two panels).
It must look and behave like **machine-level operator control**, not a
dashboard.

Gateway: Ignition 8.3.8 in Docker. The container name, projects directory and
URL are per-person and live in the gitignored `tools/env.local.sh` — copy
`tools/env.example.sh`. Nothing in this document should name a host.

Project name: **`Machine_HMI_Demo`** for the standard build. It is NOT fixed:
the Edge build lands in whatever single project that Edge runs, and a Designer
import lets the operator type any name at all — so nothing in the project may
hard-code it. See "WebDev routes" below.
Title/description carry the version, stamped by `tools/package.sh` from
`MachineDemo.plant.VERSION`: title `Machine HMI Demo <version>`, description
ending `· v<version>` (or `(dev)` and `· dev` for a development build).

## Hard rules

- **No gateway restart.** Apply project resources with a Projects "Scan File System"
  (`tools/scan.sh`), config resources with the Platform Overview scan.
- Every resource dir needs a `resource.json` listing its `files` with a
  `lastModification` block, or the scan silently ignores it.
- `doGet` must be the **first byte** of a WebDev `doGet.py` — no docstring, no
  comment above it, or the route returns an empty 200.
- Project declares `color-scheme` in the stylesheet.
- Perspective app bar hidden (`appBar.togglePosition: hidden`).
- Tab-indented, pure-ASCII Python in script resources.
- Files copied into the container must be chowned to **the account the gateway
  runs as** — `ignition:ignition` on both rigs in `dockers/`. A wrong owner
  stops the scan silently. Chown ONLY the project folder you wrote, never
  `data/projects` itself.

## Tag contract — provider `MachineDemo` (STANDARD, created by setup)

All paths below are relative to `[MachineDemo]`. Types are Ignition dataTypes.
129 tags in nine top-level nodes: eight folders and one UDT instance.

```
Config/        CaseW_mm 300 | CaseD_mm 250 | CaseH_mm 220                (Int4, mm)
               PalletW_mm 1200 | PalletD_mm 1000 | PalletH_mm 140        (Int4, mm)
               CasesPerLayer 12 | Layers 5                               (Int4)
               ConvHeight_mm 900 | ConvLength_mm 3300 | ConvWidth_mm 620 (Int4, mm)
               Station1_X_mm -1300 | Station1_Z_mm -1500                 (Int4, mm)
               Station2_X_mm -1300 | Station2_Z_mm 1500                  (Int4, mm)
               (defaults; the ONE list is MachineDemo.plant.GEOMETRY)

Line/          Running Bool | Mode String("Auto"/"Manual") | CasesPerMin Float8
               CycleTime_s Float8 | CasesTotal Int4 | SimEnabled Bool
               SimSpeed Float8 | ShiftTarget Int4
               AlarmTotals | AlarmMessages | AlarmBanner Document
                 (written by the CellSim timer via MachineDemo.ui.publishAlarms;
                 the Alarms, Manual and Overview views bind to them)

Safety/        EStopOK Bool | GuardsClosed Bool | AirPressureOK Bool
               InterfacesOK Bool | AirPressure_kPa Float8

Robot/         a UdtInstance of _types_/RobotArm — see below
               State String("Idle"/"Picking"/"Placing"/"Homing"/"Fault")
               J1_deg Float8 (-170..170)   base rotation
               J2_deg Float8 (-60..90)     shoulder
               J3_deg Float8 (-140..40)    elbow
               J4_deg Float8 (-180..180)   wrist
               Lift_mm Float8 (0..1200) | LiftTarget_mm Float8 (0..1200)
               JogUp Bool | JogDown Bool
               GripperClosed Bool | Vacuum_kPa Float8 (-80..0)
               MotorsOn Bool | Homed Bool | Ready Bool | Healthy Bool
               CycleCount Int4 | CycleTime_s Float8
               Fault Bool | FaultText String

Pallet/Station1/  Present Bool | CasesPlaced Int4 | Layer Int4
                  Complete Bool | PatternName String
Pallet/Station2/  (identical)

Conveyor/      C1_Run Bool | C2_Run Bool | C3_Run Bool
               (PE_* below are GEOMETRIC: an eye is blocked when a carton in
                the accumulation queue stands on it - see "The infeed queue")
               C1_Speed_mpm Float8 | C2_Speed_mpm Float8 | C3_Speed_mpm Float8
               PE_Infeed Bool | PE_Carton Bool | PE_Length1 Bool | PE_Length2 Bool
               PE_InPos1 Bool | PE_InPos2 Bool | PE_Clear Bool
               Gate1_Up Bool | Gate2_Up Bool | Clamp_Extended Bool
               LastBarcode String | ScanOK Bool

Zones/Z1..Z8/  Name String | State String | Running Bool | Fault Bool
               (Z1 Robot 1, Z2 Robot 2, Z3 Robot 3, Z4 Robot 4,
                Z5 Wrapper, Z6 Shuttle, Z7 Pallet Outfeed, Z8 Tray Conveyors)

Faults/        WrapperFilmFeed Bool | ConveyorJam Bool | VacuumLow Bool
               GuardOpen Bool | RobotAxisFault Bool

CadSim/Sim1..Sim4/  Part String | Priority Int4 (0..4) | Active Bool
               (simulated part alarms for the CAD screen; the alarm on Active
                binds CadPart and priority to Part and Priority)

_types_/RobotArm   the UDT definition — the nineteen Robot/ members above
```

Alarms are configured on the `Faults/*` tags, the `Safety/*` booleans
(alarm when false) and `Robot/Fault`, with real display paths and notes.
Three carry associated data `CadPart` naming a part of the UR5 sample model —
Robot Fault `base`, Robot Axis Following Error `upperarm`, Gripper Vacuum Low
`wrist3` — which the CAD page's alarm panel matches against the model on
screen (docs/CAD-VIEWER.md). The `alarms` setup row checks the links.
`Robot/Fault`’s is defined once on the **type** and inherited by the instance;
it reads back at `[MachineDemo]Robot/Fault` and raises on the same alarm source
it always did, `prov:MachineDemo:/tag:Robot/Fault:/alm:Robot Fault`.

### `Config/` — the machine’s geometry, as tags

The case, the pallet, the infeed conveyor and where the two build stations sit.
Three readers, one set of numbers, all live (since v1.9.0, 03/09/2026):

- **The simulator** reads all fifteen every tick, in the same round trip as
  the controls, and derives the pattern from them in `MachineDemo.sim
  ._geometry()`: rows × cols (the factor pair closest to square, larger along
  X), **cases a pick = one column**, the placement height of every layer, the
  centroid every pick lands on, the safe travel height, and whether the arm
  can **reach** each of those — every placement is solved and run forward
  again, and anything more than 50 mm off is reported. A change re-aims the
  running cycle within a tick and re-writes `Pallet/*/PatternName`.
- **The 3D page** gets them as the `config` block of `?cmd=state` and
  **rebuilds its geometry the moment the block changes** — inside the 250 ms
  poll — naming the change on screen. It fills each layer column by column,
  the same order the simulator places, so the picture and the arm agree on
  where case *n* is.
- **The screens** bind to them: pallet capacity on Overview and Manual is
  `CasesPerLayer * Layers`, not a literal.

Re-sizing the machine is therefore fifteen tag writes from the Designer on a
running gateway, and the **Geometry panel on the 3D page** is exactly that:
fifteen `ia.input.numeric-entry-field`s bound bidirectionally to the tags,
plus three whole-machine presets (`MachineDemo.api.setGeometry`) that write
all fifteen at once. Int4 millimetres throughout — a machine drawing is in
whole millimetres, and a float invites a geometry that is 299.9999 wide.

Robot **link lengths** are deliberately not here: they are the arm, not the
job. The reach report is what says whether *this* arm can build *this*
pattern — the default and all three presets solve with 0 mm error against
stations set 1.98 m from the robot base, close enough that a pallet's far
column stays inside a 2.5 m arm's reach.

### The infeed queue — one model, two consumers

The infeed is an **accumulation** conveyor: cartons run to a stop line 350 mm
back from the near end of the belt and queue nose-to-tail behind each other at
one case depth plus a 50 mm gap. `MachineDemo.sim` owns the queue length
(`Line`'s buffer, `bufferMax` = two picks) and the 3D page draws exactly that
many cartons at exactly that pitch, from the `infeed` block of `?cmd=state`.

**The photo-eyes are decided from that same queue**, in `_eyes()`: an eye is
blocked when a carton is standing on it, with a tolerance of half the gap so
that an eye sited on the join between two boxes does not read clear with
product in front of it. `PE_Clear` is the three eyes along the run, not the two
staging eyes at the pick point, which are made whenever a set is waiting.

Before 04/09/2026 the eyes were a phase model - each made and broke on a
fraction of the carton pitch - and the page ran its cartons the length of the
belt and wrapped them back to the far end. Both looked right in isolation and
disagreed on screen: beams reading CLEAR with a box sitting in them. The two
sides share the queue now, so they cannot.

`ConveyorJam` still latches its eyes rather than following the queue: which
eyes are made is the diagnosis that says where the carton stopped.

**Which end the queue empties from is the behaviour, and a count does not say
it.** `infeed.queue` is a number, and the page's first reading of it keyed each
carton to a fixed index and drew the first *n*. A pick takes a whole column -
three cases at the default pattern - so the three cartons that disappeared were
the three furthest **upstream**, while the one standing at the pick point never
moved. Two symptoms, one line: cartons vanishing at random near the far end of
the belt, and a robot that picked without anything leaving the queue.

The page holds an ordered list now, index 0 at the stop line. A pick shifts off
the **front** and the line steps forward one pitch behind it; an arrival pushes
on at the back.

**And the queue is not the buffer.** `_startCycle` debits `buf` the moment it
commits, because it has to know it has product before it will move - but the
cases do not leave the belt until the cups seal, Approach + Descend + a third
of Grip later, about 3.1 s. Publishing `buf` alone would have deleted the
cartons before the arm arrived. So `_staged(s)` derives from the phase what a
cycle has reserved and not yet lifted, and **`infeed.queue` = `buf` +
`staged`** - the number the page draws and the number `_eyes()` reads. Both
consumers see what is physically on the belt; `buf` on its own is scheduling.

Two consequences worth keeping:

- An interrupted cycle **gives its cases back** on the homing reset. Before
  this, every injected fault silently ate a pick's worth of product: debited at
  `_startCycle`, never placed, never returned.
- `bufferMax` is a physical length, so staged cases take room in it. Capping
  arrivals on the logical buffer alone let the belt draw eight cartons in a
  zone stated to hold six.

The gripper carries `casesPerPick` cases, not one. The head is drawn the length
of the column it takes, which is the other half of the same disagreement: three
cartons left the belt, one appeared under the gripper, and three landed on the
pallet.

### `Robot` is a UDT instance, and the paths did not change

`_types_/RobotArm` defines the arm once — nineteen members with their
engineering ranges, units, formats and the fault alarm. `Robot` is an instance
of it. The members are named **exactly** as the old folder’s tags were, so
`[MachineDemo]Robot/J2_deg` and the other eighteen resolve unchanged: the
simulator still writes them twice a second, the screens still bind them and the
3D page still reads them through `?cmd=state`. A second arm is a second
instance, not nineteen more tags to copy.

Written with `system.tag.configure`, verified against the live gateway rather
than guessed:

```python
# the definition, into the _types_ folder, BEFORE the tree that instances it
system.tag.configure("[MachineDemo]_types_",
    [{"name": "RobotArm", "tagType": "UdtType",
      "documentation": "...",
      "tags": [ ...ordinary AtomicTag dicts, alarms included... ]}], "o")

# the instance, at the provider root, carrying no members of its own
system.tag.configure("[MachineDemo]",
    [{"name": "Robot", "tagType": "UdtInstance", "typeId": "RobotArm",
      "documentation": "..."}], "o")
```

`typeId` is the definition’s name relative to `_types_`. Everything the type’s
members carry — range, unit, format, documentation, tooltip, **alarms** — is
inherited and reads back on the instance’s own member path.

### The upgrade trap: never write an instance over an existing folder

A gateway that ran an earlier build has `Robot` as a plain **folder**.
`system.tag.configure` with collision policy `"o"` will write a `UdtInstance`
straight over it and **answer `Good`**. Afterwards the node browses as a
`UdtInstance`, `getConfiguration` returns all nineteen inherited members with
their alarms, and a check that only reads configuration is green — while every
member sits at `Uncertain_InitialValue` for ever and answers `Bad_Unsupported`
to every write. The tag tree is perfect and the machine is dead, with nothing in
any log. Measured on this gateway, 02/09/2026.

`MachineDemo.setup` therefore **deletes the node first** when what is standing
there is not already a live instance, then creates the instance
(`_clearStaleRobot`). Overwriting an instance that is already healthy is safe —
also measured — so the delete fires once on a gateway being upgraded and never
again. No restart, and nothing outside this provider is touched.

The `udt` row of `?cmd=check` asks the only question that separates the two
states: not “is it an instance” but “do its members carry a value”.

### Setup items

`?cmd=check` reports eight items, each independently, none stopping at the
first failure: `tagProvider`, `tags`, `udt`, `config`, `alarms`, `database`,
`journal`, `simulation`. `udt` and `config` are fixed by the same `_tagsFix`
that writes the tree — they are separate rows because a tree that wrote its
values while dropping its UDT, its geometry or its alarms looks perfect from
every screen and reports nothing.

### Edge Panel permits ONE concurrent Perspective session

Measured 09/09/2026 on 8.3.8 Edge Panel. A second session is served Ignition's
**Sessions Exceeded** page:

    Sessions Exceeded
    The number of running client sessions has exceeded the permitted number.

It is an ordinary HTML page with a 200, no Perspective components and no error
in the gateway log, so a headless check that opens a browser context per page
measures it happily and reports a pass. Both sweeps in `tools/verify` therefore
use ONE page for the whole run and refuse to measure a document with zero
`[data-component]` elements. The session also outlives the page that opened it
by about a minute, so consecutive gate runs against an Edge need a gap.

For the demo itself this means: on Edge, the HMI is open on one screen at a
time. That is the edition, not the project.

### `database` and `journal` are edition-aware, not unconditional

This demo argues for Ignition Edge Panel on a builder's small,
single-panel machines, and Edge Panel has **no database connectivity at all**
— not a licence restriction, the SQL Bridge gateway module that provides it
is simply absent from the Edge build. `MachineDemo.setup._hasDatabaseModule()`
asks the gateway directly rather than guessing: is `('ignition',
'database-connection')` among the resource types `system.config
.getResourceTypes()` returns. That type (and `database-driver`,
`database-translator` beside it) is registered by SQL Bridge; on a gateway
without it, the type is never registered and the check answers `False` with
nothing to catch. Verified live against a standard 8.3.8 gateway (a
STANDARD gateway) 03/09/2026: 57 resource types are registered including
`database-connection`, and `ModuleManager.getModuleInfoAsJson()` independently
confirms SQL Bridge is `ACTIVE`.

- **With a database** (standard Ignition or Maker): unchanged from before —
  setup creates its own `MachineDemoDB` SQLite connection and a `DATASOURCE`
  alarm-journal profile named `MachineDemo` writing into it. `database`
  reports the connection exists and answers `SELECT 1`; `journal` reports the
  profile is `DATASOURCE` and points at `MachineDemoDB`.
- **Without one** (Edge Panel): no connection is attempted — `database`
  reports green, `"not applicable on this edition"`, not red `"missing"`, and
  `fix("database")` is a reported no-op rather than an attempt that would
  fail. The `MachineDemo` alarm-journal profile is instead created with
  `profile.type: "LOCAL"` — Edge's own internal journal, confirmed live by
  creating one on the module-testing gateway: `system.config.create` accepts
  it with the same `dataFilters`/`eventData`/`events`/`pruning` shape as the
  `DATASOURCE` profile, minus `advanced` (table names) and `datasource`
  (there is nothing to point at), and the persisted config round-trips
  byte-for-byte. Alarms are still journalled; only the storage mechanism
  changes.

Both branches keep the row count at eight - nothing is added or removed, only
what `database`/`journal` report and what their `fix` does.

**Measured on a real Edge Panel gateway.** On a fresh one, the eight rows read
green from one press of RUN SETUP.

- `_hasDatabaseModule()` was right: a real Edge registers **55** resource types
  and `database-connection` is genuinely not among them (a standard gateway
  registers more - 60 on a stock 8.3.8, and the number moves with the installed
  modules, so only the presence of the type is a sound test). The `database`
  row reads "not applicable on this edition".

- **Edge is detected by `edge-sync-settings`, not `edge-system-properties`.**
  The first answer used the latter and was wrong: a standard gateway registers
  it too, so every Edge branch fired on standard - the journal was never
  created there. Diffing both editions gives exactly one Edge-exclusive type:

      only on standard   database-connection, database-driver,
                         database-translator, cobranding,
                         sfc/chart-settings, sip-notification/script-settings
      only on Edge       edge-sync-settings

  Found only by installing the standard build on a standard gateway after the
  Edge one had passed. One edition passing proves nothing about the other.
- **The `tagProvider` row was a false green.** Edge permits exactly one realtime
  tag provider. A second written through `system.config` is accepted as a
  resource and then refused at startup - `Unable to start provider:
  'MachineDemo', an Edge Gateway Provider is already registered` - so the row
  reported the resource existed while all 113 tags failed underneath it with
  `Bad_NotFound`. It now browses the provider instead of trusting the resource.
- **The LOCAL journal branch does not exist on Edge.** `system.config.create`
  for typeId `alarm-journal` throws `java.lang.UnsupportedOperationException:
  Cannot create Alarm Journal on Edge`. Edge keeps exactly one, `EdgeJournal`,
  and setup adopts it. The LOCAL profile was "confirmed live" on a STANDARD
  gateway, where the restriction is simply absent - which is how a reasoned
  claim survived looking measured.

Edge is detected structurally, the same way the database is:
`('ignition', 'edge-system-properties')` is in `getResourceTypes()` only on
Edge. `alarm-journal` is registered on Edge too, so the journal cannot be
detected that way - the type is there and the CREATE is what fails.

**Edge journals alarms perfectly well**, and an earlier note here claiming
otherwise was wrong twice over. Edge cannot use an EXTERNAL database for the
journal, and its internal store is bounded (about 35 days) - that is the whole
of the difference. The HISTORICAL tab reading empty was two defects of ours:

- The journal table's `name` was bound with a `type: "tag"` binding, an idiom
  this project uses nowhere else. It silently did not apply, so the prop fell
  back to its literal default - and querying a journal profile that does not
  exist THROWS, which the component renders as an empty table with no error.
  It is an expression binding now, the same `{[provider]Path}` form as the
  other 396 bindings in the project.
- The Edge build substituted `[MachineDemo]` but not `prov:MachineDemo:`, so
  the table's source filter named a provider that did not exist there.

Verified on a real Edge: inject a fault and the events appear with their state
transitions.

### The CAD page on Edge — not tested on Edge

1.19.0 (CAD upload, model selector, part alarms) was verified on a STANDARD
8.3.8 gateway only. What it relies on, and what is known about each on Edge:

- Uploads are written by gateway-scope Jython to
  `<data dir>/machine-demo-cad/`, the directory from
  `IgnitionGateway.get().getSystemManager().getDataDir()`. Nothing about that
  is edition-specific, but it has not been run on Edge.
- `ia.input.fileupload` is a stock Perspective component. Not tried on Edge.
- The part alarm panel uses `system.alarm.queryStatus` with
  `prov:<provider>:/tag:*`, the same call `MachineDemo.plant.liveAlarms`
  makes for the screens' alarm counts. The `CadPart` associated data is
  written with the rest of the tag configuration by Setup. Neither has been
  read back on Edge.
- The STEP reader is a 7.6 MB `.wasm` in the project. Loading it in a panel's
  own browser is untested; STL models do not need it.

Until it is run on Edge, do not claim the CAD upload or STEP for Edge.

## WebDev routes — the project name is NOT fixed

Base: `<gateway>/system/webdev/<project>/<name>` (`$GW_URL` from
`tools/env.local.sh`). `<project>` is whatever the project is CALLED on that
gateway — `Machine_HMI_Demo` for the standard zip, the Edge gateway's single
project name for the Edge one, and anything at all if it was imported through
the Designer, where the operator types the name.

**Nothing in the project may hard-code it.** The Perspective views that embed
these pages resolve it at runtime: an expression builds the query string and a script transform,
`MachineDemo.ui.webdevUrl("cell3d", value)`, puts
`"/system/webdev/" + system.project.getProjectName() + "/cell3d"` in front of it.

There is no session property for it — `session.props` has no `projectName` — so
`system.project.getProjectName()` is the mechanism. A literal here produced
`HTTP ERROR 404 Project "Machine_HMI_Demo" not found` on a customer's gateway
while every other screen in the project worked, because only the 3D and CAD
pages leave Perspective. Inside a page, every asset URL is RELATIVE
(`lib?f=three`, `admin?cmd=state`) and so is unaffected.

| Resource | Method | Route | Purpose |
| --- | --- | --- | --- |
| `admin` | GET | `?cmd=state` | **compact live JSON the 3D page polls** |
| `admin` | GET | `?cmd=status\|version\|check\|faults\|alarms\|alarmcheck&tag=` | read the cell, change nothing |
| `admin` | GET | any write `cmd` | **405** — refused, tag untouched |
| `admin` | POST | anything | **405** — refused; the write path is gone |
| `cell3d` | GET | (no query) | the 3D palletising cell, built from `Machine/Scene`'s parts list |
| `cell3d` | GET | `?scene=code` | the same cell, built from the page's own JavaScript |
| `cadview` | GET | (no query) | the CAD viewer — the built-in model (every STL in the `cad` folder) |
| `cadview` | GET | `?model=<name>` | the CAD viewer — one uploaded model |
| `cad` | GET | `?f=list[&model=<name>]` | the model's kind (`stl`/`step`) and part files, as JSON |
| `cad` | GET | `?f=<part>[&model=<name>]` | one part file (STL or STEP), as bytes |
| `cad` | GET | `?f=alarms` | standing alarms on the provider that carry `CadPart`, as JSON |
| `cad` | POST | `?f=parts&model=<name>` | the CAD page reports a STEP model's part names (JSON list) into `parts.json` - the one HTTP write: names only, existing STEP models only, never a tag |
| `lib` | GET | `?f=three` | vendored three.js (proves it works with no internet) |
| `lib` | GET | `?f=occt` / `?f=occt-wasm` | vendored occt-import-js, the STEP reader (LGPL-2.1, see NOTICE) |

### HTTP is read-only. Writes go through the session or the console.

Nothing on the network can change this cell with a URL — not jog the arm, not open
the guard circuit, not inject a fault — and that is true with or without a
credential, because the write path was removed rather than guarded:

- A write `cmd` on GET (`setup fix fault clear reset speed mode jog guards`)
  returns **405** `{"ok": false, "error": "writes are not accepted on GET"}`.
- **Every** POST returns **405** `{"ok": false, "error": "writes are not accepted
  over HTTP; use the Setup screen or the Designer Script Console"}`.
- `config.json` keeps `require-auth: false` on every method and an empty
  `user-source`, so the project ships with nothing gateway-specific in it.
- CAD model upload and delete, and simulated part alarms, are the same: the
  popups call `MachineDemo.cad.*` in the session. `cad` accepts one POST,
  `?f=parts`, which writes a STEP model's part-name list and nothing else.

The two ways to drive the demo:

1. **The Setup screen.** Its buttons call `MachineDemo.api.*` and
   `MachineDemo.setup.*` in gateway scope, as the signed-in Perspective session —
   the native path, no HTTP hop.
2. **The Designer Script Console** (Tools → Script Console), same functions:

```python
MachineDemo.setup.run()                       # one-button install / repair
MachineDemo.setup.check()                     # the eight install rows
MachineDemo.api.setFault("ConveyorJam", True) # also WrapperFilmFeed VacuumLow GuardOpen RobotAxisFault
MachineDemo.api.setFault("ConveyorJam", False)
MachineDemo.api.reset()                       # every fault cleared, steady state
MachineDemo.api.setSpeed(2)                   # machine time as a multiple of real time (api clamps at 10)
MachineDemo.api.setMode("Auto")               # or "Manual"
MachineDemo.api.setGuards(False)              # open the guard circuit; True closes it
MachineDemo.api.setJog("up", True)            # momentary bit; send False to release
MachineDemo.api.setGeometry("euro-tall")      # all 15 Config tags at once; also "default", "small-dense"
```

Why not authenticated POST: WebDev authentication on 8.3.8 is HTTP Basic against a
**named user source**, and `user-source: ""` is a `500`, not a default. A project
that ships one gateway's source name answers `500 No user source for project` on
every other gateway. Dropping the path was chosen over shipping a name
(decision 02/09/2026).

### The cell is built from the SCENE DOCUMENT, not from the page's JavaScript

Since 1.16.0 the shipped path is the document: 45 parts in `Machine/Scene`'s
custom properties, served by `admin?cmd=scene` and assembled by `buildScene()`.
`?scene=code` selects the hand-written `buildCell()` instead. It is kept for two
reasons and neither is "in case we change our minds":

- **`tools/verify/scene_parity.js` needs it as the control.** That gate builds
  the expected tree itself from `src/cell3d/scene.json` + `scene-render.js` and
  compares it to what the page rendered, so the page must render the *other*
  path or the comparison is the document against itself. The gate therefore
  loads `?scene=code` explicitly.
- **It is the fallback.** A document that fails to build says so on screen and
  the page falls back to code, rather than showing an empty cell in front of a
  customer.

**An edit to the document reaches a running session.** `?cmd=state` carries
`sceneRev` — mtime and size of `Machine/Scene`'s `view.json`, a `stat` not a
read, so the 4 Hz poll pays almost nothing for it. When it moves, the page
re-fetches `?cmd=scene`, rebuilds and says so on the toast the geometry changes
already use. The granularity is a **Designer save**, because that is when the
gateway writes the file.

`MachineDemo.scene` reads that file DIRECTLY rather than through the project
resource system, so a document change needs no project scan — but it also means
the file is the source of truth, not the gateway's in-memory project.

**A bad edit must not take the cell down mid-demonstration.** `bindFromDocument`
resolves every part it needs BEFORE it mutates anything, and
`buildFromDocument` runs it as a dry run against the new build first. A document
that has lost a part therefore fails while the old cell is still whole: the page
says "showing the previous cell", keeps the one that is standing, and accepts
the revision so the same broken document is not re-fetched four times a second.
Measured by renaming `Shoulder` under a running page — 396 meshes before and
after, joints still moving.

**A geometry change has to rebuild through the DOCUMENT too.** Calling
`buildCell()` unconditionally, in document mode, disposes the document's
conveyor and pallet stations and replaces them with hand-built ones while
leaving the document's robot and guarding standing — a hybrid that looks
identical on screen because the two paths render the same way by design. The
whole document root is torn down and rebuilt instead.

### `cell3d` is a Text Resource, and that is deliberate

It began as a `doGet.py` that read a `page.html` sitting beside it. That worked
and the Designer could not see it — Web Dev lists resources, and a loose file
inside a resource folder is not one, so anyone opening `cell3d` in the Designer
found the Python and no way to reach the page.

A **text-resource** appears in Web Dev, opens in the Designer's editor with
HTML, CSS and JavaScript all syntax-highlighted, and is served directly at the
same URL with no Python in the way. Its on-disk form is:

```json
{ "resource-type": "text-resource", "content-type": "text/html", "text": "…" }
```

— the whole page as one JSON string, with `files: ["config.json"]` and nothing
else in the directory.

That is unreadable in git, so **`src/cell3d/page.html` is the source of truth**
and the resource is generated:

```
python3 tools/webdev_page.py build      # src/cell3d/page.html -> the resource
python3 tools/webdev_page.py extract    # the resource -> src/cell3d/page.html
```

**Run `extract` after editing in the Designer, before committing.** The two
directions are not automatic, and the next `build` overwrites whatever was typed
in the Designer. This is the one cost of the split, and it buys the thing the
demo is trying to prove: that the buyer can maintain the 3D page in the
Designer without a web toolchain.

`admin` and `lib` remain python-resources — they are code, not pages.

### `?cmd=state` response shape — FROZEN, the 3D page depends on it

```json
{
  "ok": true, "ts": 1756800000000,
  "line": {"running": true, "mode": "Auto", "cpm": 14.2, "cycle": 12.6,
           "cases": 1284, "target": 1800},
  "robot": {"state": "Placing", "j1": -42.0, "j2": 18.5, "j3": -61.0,
            "j4": 12.0, "lift": 340.0, "grip": true, "vac": -62.4,
            "cycles": 812, "fault": false, "faultText": ""},
  "pallets": [{"present": true, "cases": 37, "layer": 3, "complete": false,
               "pattern": "5 x 12 interlock"}, {...}],
  "conv": {"c1": true, "c2": true, "c3": false,
           "pe": {"infeed": true, "carton": false, "len1": true, "len2": false,
                  "inpos1": true, "inpos2": false, "clear": true},
           "gate1": false, "gate2": true, "clamp": true,
           "barcode": "T12783", "scanOK": true},
  "safety": {"estop": true, "guards": true, "air": true, "interfaces": true},
  "faults": {"WrapperFilmFeed": false, "ConveyorJam": false, "VacuumLow": false,
             "GuardOpen": false, "RobotAxisFault": false},
  "zones": [{"id":"Z1","name":"Robot 1","state":"Running","running":true,"fault":false}, ...],
  "config":   {"caseW_mm": 300, ... the fifteen Config tags, always complete},
  "quality":  {"ok": true, "bad": [], "stale": false, "worst": "Good"},
  "geometry": {"pattern": "5 x 12 interlock", "rows": 3, "cols": 4,
               "casesPerPick": 3, "picksPerLayer": 4, "casesPerPallet": 60,
               "pickWristY_mm": 1395, "stackTop_mm": 1260,
               "reach": {"ok": true, "unreachable": 0, "worst_mm": 0,
                         "note": "every placement within reach (worst 0 mm)",
                         "detail": []}}
}
```

`config`, `quality`, `geometry`, `infeed` and `sceneRev` are **additive** beside
the frozen shape. `infeed` is the accumulation queue - `{"queue": 4, "max": 6,
"pitch_mm": 300, "stopGap_mm": 350}` - and the 3D page draws exactly that many
cartons at that pitch. `geometry` is what the simulator derived from `config`, cached until a
Config tag changes; the page rebuilds when `config` changes and shows
`geometry.pattern` and `geometry.reach` on the HUD.

Robot joint convention for the 3D page (right-handed, Y up, mm):
`j1` rotates the base about **Y**; `j2` is the shoulder about **Z** (positive
lifts the upper arm); `j3` is the elbow about **Z** relative to the upper arm;
`j4` rotates the wrist about **Y**; `lift` raises the whole column in mm.

## Generated resources — rebuild, do not hand-edit

Several resources are written by a generator and any manual edit is lost on the
next run:

| Resource | Generator |
| --- | --- |
| `com.inductiveautomation.webdev/resources/cell3d` | `tools/webdev_page.py build` (source: `src/cell3d/page.html`) |
| `perspective/views/Machine/Cell3D` | `tools/build_cell3d_view.py` |
| `com.inductiveautomation.webdev/resources/cadview` | `tools/webdev_page.py build cadview` (source: `src/cadview/page.html`) |
| `perspective/views/Machine/CadModel`, `Machine/CadModels` | `tools/build_cad_view.py` (reads Cell3D) |
| the nav bar in every view that has one | `tools/add_nav_tab.py` |
| `perspective/views/Machine/ManualAccess`, and which containers may scroll in Overview, Manual and Setup | `tools/fit_scrollbars.py` (checked by `tools/verify/scrollbar_sweep.js`, a `package.sh` gate) |
| `project.json` title and description | `tools/package.sh` |

`tools/webdev_page.py extract` brings a Designer edit of the 3D page back into
`src/` before it is overwritten. It is the one direction that is not automatic.
