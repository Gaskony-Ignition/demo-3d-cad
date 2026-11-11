# Driving the 3D cell from a real machine

*What changes, what does not, and the one question that decides the size of
the job.*

## The short answer

Nothing in the 3D page talks to the simulator. It reads **tags**, through one
endpoint, and it cannot tell where their values come from. Feeding it a real
machine is a change of tag source, not a rewrite.

```
  today          simulator  ->  [MachineDemo] tags  ->  api.state()  ->  3D page
  real machine   PLC / OPC  ->  [MachineDemo] tags  ->  api.state()  ->  3D page
                              ^^^^^^^^^^^^^^^^^^^^
                              the only thing that changes
```

The tag tree is the contract, and it was built to be one. Every screen, the
alarms and the 3D view read the same paths, so a value that becomes real
becomes real everywhere at once.

## What actually changes

| | Today | On a real machine |
| --- | --- | --- |
| `[MachineDemo]Robot/*` | memory tags written by the simulator | OPC tags on the robot controller or the PLC |
| `Robot` UDT | one instance, no device | one instance **per arm**, parameterised with the device name |
| `Line/SimEnabled`, `SimSpeed` | control the simulation | deleted, they mean nothing |
| `CellSim` timer script | runs the model and publishes the alarm summary tags twice a second | `sim.tick()` removed; `ui.publishAlarms()` stays, the alarm screens read its tags |
| `MachineDemo.api` | unchanged | unchanged |
| `cell3d` page | unchanged | unchanged |
| Screens, alarms | unchanged | unchanged |

`Robot` being a **UDT instance** is what makes the multi-arm case cheap. The
type already carries the nineteen members, their engineering ranges and the
fault alarm. Pointing it at a real controller is done once on the type;
a four-robot cell is four instances.

## The question that decides the job

**Where the arm's actual position comes from.** Establish this first, because
it changes the work by an order of magnitude. There are three tiers.

### Tier 1 — the controller publishes joint positions

Fanuc, ABB, KUKA and Yaskawa can all expose live joint angles, usually as
position registers mapped into the PLC, or directly over OPC UA from the
controller. Six values, mapped onto `J1_deg`..`J4_deg` and `Lift_mm`.

This is the direct case. The model genuinely shows where the arm is, and the
work is the mapping layer below.

### Tier 2 — the PLC knows the commanded position, not the actual

Common, and perfectly usable. The model shows an idealised arm that leads or
lags the real one slightly and never shows a following error as movement.

Worth **saying out loud** to whoever is watching. A 3D view that implies
position feedback it does not have is the kind of thing that gets discovered
during a fault, which is the worst moment.

### Tier 3 — only sequence state is available

You know the cell is picking, working station 2, on layer 3, and nothing about
where the arm is between those points.

This is where today's simulator stops being a stand-in and becomes the
**renderer**. Its motion model already turns *(station, slot, layer)* into a
pose through inverse kinematics, and already interpolates smoothly between
waypoints. Drive that from real counters instead of its own, and you have an
honest, useful animation built from data the PLC certainly has.

That code exists today. It is the part of this demo most likely to survive
into a product.

## Faults and manual movement are the easy half

Both already work the way a real machine works, which was deliberate.

- **Faults** are tags. Injecting one in the demo writes `Faults/ConveyorJam`;
  a real cell writes the same tag from the PLC. The alarms, the banner, the
  zone colours and the pulsing highlight on the 3D model all follow from
  there with no change.
- **Manual movement** already has the correct split. The HMI sets a momentary
  bit (`Robot/JogUp`) and something else owns the motion. Today that is the
  simulator; on a real cell it is the PLC. The screen does not change at all,
  including the watchdog that clears a jog bit if the session that set it
  disappears.

This matters in the meeting: the demo is not pretending about the control
model. A screen that moved an axis itself would carry on moving it after the
interlock dropped, and machine people know it.

## What still needs engineering

**Update rate.** The simulator writes twice a second and the page polls four
times a second, with damping to smooth between samples. That is right for a
model and marginal for a fast arm.

| | Today | Real cell |
| --- | --- | --- |
| Source update | 500 ms timer | 50 to 100 ms OPC subscription |
| Page update | 250 ms poll | subscription, no poll |

The polling loop is the weakest part of the current architecture and it is
the strongest argument for the component module in
[3D-AS-PERSPECTIVE.md](3D-AS-PERSPECTIVE.md): a Perspective component uses the
session's own tag subscription, so values arrive when they change and there is
no HTTP request per client per quarter second.

**Joint convention mapping.** Real controllers differ on zero positions, sign
conventions and occasionally units. The page assumes one convention, which is
written down in `docs/CONTRACT.md`. The mapping belongs in the **tag layer**,
as expression or derived tags on the UDT, never inside the page. Put it in the
page and every future machine needs a JavaScript edit.

**Fault to geometry mapping.** The page pulses three groups of parts, keyed by
fault name. Real fault codes need a small lookup deciding what lights up, and
a sensible default for a code nobody has mapped yet.

**Reach and calibration.** The simulator's reach report solves the pattern
against the arm's link lengths. For a real machine those become the real
arm's dimensions, and the report turns into something genuinely useful: a
check that the pattern an engineer just typed is one the machine can build.

**What already handles the real world.** Tag quality is judged on every poll
and the model desaturates with a banner when values go bad or stale. On a
simulator that is a nicety. On a real cell with a comms link it is the
difference between a frozen picture and a picture that admits it is frozen.

## One thing worth raising

The fifteen geometry tags do not have to be typed by hand. Fed from the PLC's
recipe or pattern selection, **the 3D model reshapes itself on changeover** and
shows the pattern the line is actually running, with the reach check
confirming the arm can build it.

That is a small amount of work on top of what exists, and it is the point at
which the 3D view stops being a picture of a machine and starts being an
instrument.
