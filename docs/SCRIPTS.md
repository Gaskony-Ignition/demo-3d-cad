# Script library notes

Design reasons behind the `MachineDemo` script modules that the code itself does not say.

## MachineDemo.sim

- Motion is up, across, down. Approach and Traverse change only J1 at the safe height; Descend, Lift, Lower and Retract change only height with J1 parked. A straight line from pick to place is valid at both ends and takes the forearm through the stack in the middle.
- Poses are interpolated in task space (J1, planar radius, wrist height, J4) and solved to joints only in `_write()`. Interpolating joint angles follows the linkage's own curve and dips the wrist through the conveyor on a long swing.
- IK frame: base at the origin, Y up, metres. J1 = atan2(-Z, X), r = |XZ|; carriage at BASE_Y + Lift_mm/1000; wrist at r = L1 cos J2 + L2 cos(J2+J3), y = carriage + L1 sin J2 + L2 sin(J2+J3). Elbow-down branch. The carriage tracks the wrist from CARRIAGE_ABOVE above it; with a fixed lift the arm runs out of reach by layer four.
- `Line/SimSpeed` scales machine time, not the machine: the nominal cycle stays 12.6 machine-seconds and about 14.3 cases/min at any speed. The tick integrates measured real time (gaps capped at 2 s), so a late tick costs smoothness, never counts.
- The infeed runs 8% faster than the robot consumes (cartonPitch = cycle/pick x 0.92). At exactly matched rates the buffer grazes zero between cycles and Line/Running flickers false. `bufferMax` is two picks, so a ConveyorJam starves the robot about 25 machine-seconds later: cause visible first, then effect.
- The shift index comes from `java.util.Calendar` in the gateway's zone, not epoch-ms arithmetic, which gives UTC hours. It is derived from the clock, so a gateway that was off overnight comes back on the right shift.
- The CellSim timer runs every 500 ms on the shared thread at a fixed delay. The shortest phase is 0.8 machine-seconds, so it still gets samples at 1x; the 3D page polls at 250 ms and interpolates.
- WrapperFilmFeed blocks discharge only, so the cell stops one station at a time.

## MachineDemo.plant

Default pattern: 12 cases a layer in a 4 x 3 grid, placed a column of 3 at a time, 5 layers a pallet. A 12.6 s cycle gives about 14.3 cases a minute, typical of a mid-size case palletiser.

## MachineDemo.api

- `quality.stale`: every tag is a memory tag, so it stays Good when the simulator stops and only the timestamps stop moving. A memory tag's timestamp also does not move on a write of the same value, so one representative tag (Robot/CycleCount changes once a ~12 s cycle) would read stale on a healthy robot. Staleness is the age of the newest timestamp across the whole snapshot, against `STALE_AFTER_MS` (5000, ten missed ticks). `quality.bad` lists tags that read bad quality: in practice deleted, renamed or never created.
- `setFault` waits 700 ms before returning so the caller's next read already shows the cell's reaction.
- `reset()` keeps the pallets and the shift total, as a real cell carries on with the pallet it was building after a fault reset.

## MachineDemo.tagdata

- Alarm on-delays are zero on every digital alarm and 2 s on the one analog (air pressure). The alarm engine counts on-delays in real seconds, so with the simulator sped up a longer on-delay would never let the alarm raise.
- Safety booleans alarm on equality-false, so each tag reads the way its circuit is named (`GuardsClosed`).
- `Line/ShiftIndex` and the pallet counts are tags, not module state, because a project scan drops script-module globals.

## MachineDemo.setup

The demo owns its SQLite connection and alarm journal rather than sharing the gateway's. Filtering a shared journal by source only looks like isolation: the rows interleave with every other project's in one `alarm_events` table and the retention belongs to someone else. In its own file the history is this demo's alone and goes when the file is deleted.
