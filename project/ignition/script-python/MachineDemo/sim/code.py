"""The palletising cell, simulated: a real pick-and-place cycle in task space, solved to joints.
Line/SimSpeed scales machine time only; the tick integrates measured real time.
Sub-cycle state lives in a module dict, rebuilt from the tags after a project scan.
Faults and the fifteen Config/* geometry tags are read every tick; geometry is cached.
"""

import math
import random

from java.lang import System as JSystem
from java.util import Calendar

P = MachineDemo.plant
LOG = system.util.getLogger("MachineDemo.sim")


# World frame: robot base at the origin, Y up, metres. J1 = atan2(-Z, X);
# J2 is the upper arm from horizontal, J3 the forearm relative to it, both positive up.
L1 = 1.35            # shoulder to elbow, m
L2 = 1.15            # elbow to wrist, m
BASE_Y = 0.34        # carriage height at Lift_mm = 0, m
LIFT_MAX_MM = 1200.0
D_MIN = 0.20         # clamp on the carriage-to-wrist distance, m
D_MAX = 2.45

# The carriage tracks the wrist from this far above it, m; a fixed lift runs
# out of reach by layer four.
CARRIAGE_ABOVE = 0.30

# A pose is task space (J1 deg, radius m, wrist height m, J4 deg) and is interpolated
# there: interpolating joint angles dips the wrist through the conveyor on a long swing.

def _task(x, z, wristY, j4=0.0):
	"""A world point (X, Z, wrist height) as (J1, radius, wristY, J4)."""
	return (math.degrees(math.atan2(-z, x)), math.hypot(x, z), wristY, j4)


# Fixed, not Config: the page grows the conveyor away from the pick end.
INFEED_XZ = (1.62, 0.10)          # pick point off the infeed conveyor
HOME_XZ = (1.10, 0.0)
HOME_WRIST_Y = 1.35

# These three match how the 3D page draws the rollers, deck boards and gripper;
# a mismatch sets every placed case into the layer below and every pick through the belt.
ROLLER_TOP_M = 0.045
DECK_TOP_M = 0.02
WRIST_TO_CASE_TOP_M = 0.23
CASE_INSET = 0.94                 # the page draws the pattern 6% inside its span

SAFE_CLEAR_M = 0.35               # wrist clearance over the tallest stack while swinging

# The 3D page draws the same queue from these numbers; if they differ, a beam
# reads clear with a carton standing in it.
QUEUE_STOP_GAP_M = 0.35           # stop line, back from the near end
QUEUE_GAP_M = 0.05                # between one carton and the next


def _eyeOffsets(convLen):
	"""Each eye's distance upstream of the stop line, m; four move with the belt length."""
	return {
		"PE_InPos2": -0.10,
		"PE_InPos1": 0.25,
		"PE_Carton": convLen - 3.45,
		"PE_Length2": convLen - 2.65,
		"PE_Length1": convLen - 2.05,
		"PE_Infeed": convLen - 0.70,
	}


REACH_TOL_M = 0.05                # a solved wrist further off than this is an unbuildable slot

# Derived geometry, cached by _geo() until a Config value changes.
_G = None
_G_KEY = None


def _solve(r, wristY):
	"""(J2, J3, Lift_mm) putting the wrist at radius r, height wristY; elbow-down, clamped."""
	lift = _clamp((wristY - (BASE_Y - CARRIAGE_ABOVE)) * 1000.0, 0.0,
	              LIFT_MAX_MM)
	carriageY = BASE_Y + lift / 1000.0
	dx = r
	dy = wristY - carriageY
	d = _clamp(math.hypot(dx, dy), D_MIN, D_MAX)
	c3 = _clamp((d * d - L1 * L1 - L2 * L2) / (2.0 * L1 * L2), -1.0, 1.0)
	j3 = -math.degrees(math.acos(c3))
	c2 = _clamp((d * d + L1 * L1 - L2 * L2) / (2.0 * d * L1), -1.0, 1.0)
	j2 = math.degrees(math.atan2(dy, dx) + math.acos(c2))
	return _clamp(j2, -60.0, 90.0), _clamp(j3, -140.0, 40.0), lift


def _forward(j2, j3, lift):
	"""Wrist (radius, y) for a solved pose; differs from the request where _solve clamped."""
	a = math.radians(j2)
	b = math.radians(j2 + j3)
	r = L1 * math.cos(a) + L2 * math.cos(b)
	y = BASE_Y + lift / 1000.0 + L1 * math.sin(a) + L2 * math.sin(b)
	return r, y


HOME = _task(HOME_XZ[0], HOME_XZ[1], HOME_WRIST_Y)


def _grid(count):
	"""(rows, cols) for a layer: the factor pair closest to square, as the 3D page does; (3, 4) if invalid."""
	try:
		count = int(count)
	except:
		count = 0
	if count <= 0:
		return 3, 4
	a = 1
	d = 1
	while d * d <= count:
		if count % d == 0:
			a = d
		d += 1
	return a, count // a


def _layout(g, rot):
	"""Station-local (x, z) of each case in a layer, column by column as the page fills them."""
	cw = g["caseD"] if rot else g["caseW"]
	cd = g["caseW"] if rot else g["caseD"]
	rows, cols = g["rows"], g["cols"]
	spanX = cols * cw
	spanZ = rows * cd
	out = []
	for q in range(cols):
		for r in range(rows):
			out.append(((-spanX / 2.0 + cw * (q + 0.5)) * CASE_INSET,
			            (-spanZ / 2.0 + cd * (r + 0.5)) * CASE_INSET))
	return out


def _geometry(raw):
	"""Derived geometry from {Config key: int mm}; distances leave as metres."""
	mm = lambda k: raw[k] / 1000.0
	g = {
		"raw": dict(raw),
		"caseW": mm("caseW_mm"), "caseD": mm("caseD_mm"),
		"caseH": mm("caseH_mm"),
		"palletW": mm("palletW_mm"), "palletD": mm("palletD_mm"),
		"perLayer": max(1, int(raw["casesPerLayer"])),
		"layers": max(1, int(raw["layers"])),
		"convY": mm("convHeight_mm"),
		"stations": {1: (mm("station1X_mm"), mm("station1Z_mm")),
		             2: (mm("station2X_mm"), mm("station2Z_mm"))},
	}
	g["rows"], g["cols"] = _grid(g["perLayer"])
	# A pick is one column of the pattern.
	g["pick"] = g["rows"]
	g["perPallet"] = g["perLayer"] * g["layers"]
	g["deck"] = mm("palletH_mm") + DECK_TOP_M
	g["pickWristY"] = g["convY"] + g["caseH"] + ROLLER_TOP_M + WRIST_TO_CASE_TOP_M
	g["pickLow"] = _task(INFEED_XZ[0], INFEED_XZ[1], g["pickWristY"])
	# Each pick lands at the centroid of its cases, per layer parity; a short last column is what is left.
	slots = {}
	for parity in (0, 1):
		lay = _layout(g, parity == 1)
		cents = []
		for k in range(0, len(lay), g["pick"]):
			grp = lay[k:k + g["pick"]]
			cents.append((sum(c[0] for c in grp) / len(grp),
			              sum(c[1] for c in grp) / len(grp)))
		slots[parity] = cents
	g["slots"] = slots
	g["picksPerLayer"] = len(slots[0])
	g["pattern"] = "%d x %d interlock" % (g["layers"], g["perLayer"])
	# Infeed 8% faster than the robot consumes: at exactly matched rates the buffer
	# grazes zero between cycles and Line/Running flickers false.
	g["cartonPitch"] = (P.CYCLE_S / float(g["pick"])) * 0.92
	g["bufferMax"] = 2 * g["pick"]
	g["reach"] = _reach(g)
	return g


def _reach(g):
	"""Solve the pick, every placement and the clearing heights; report any the arm cannot reach."""
	bad = []
	worst = 0.0

	def check(where, pose):
		_, r, y, _ = pose
		j2, j3, lift = _solve(r, y)
		r2, y2 = _forward(j2, j3, lift)
		err = math.hypot(r - r2, y - y2)
		if err > REACH_TOL_M:
			bad.append("%s (%.0f mm short)" % (where, err * 1000.0))
		return err

	worst = max(worst, check("infeed pick", g["pickLow"]))
	for n in sorted(g["stations"].keys()):
		for layer in range(g["layers"]):
			for slot in range(g["picksPerLayer"]):
				pose = _placePoseG(g, n, slot, layer, None)
				worst = max(worst, check("station %d layer %d slot %d"
				                         % (n, layer + 1, slot + 1), pose))
	# A pallet the arm can build but not clear is one it hits on the last retract.
	top = g["deck"] + g["layers"] * g["caseH"] + SAFE_CLEAR_M
	for n in sorted(g["stations"].keys()):
		x, z = g["stations"][n]
		worst = max(worst, check("clearing station %d" % n, _task(x, z, top)))
	if bad:
		note = "%d of %d placements beyond reach - first: %s" % (
			len(bad), 1 + 2 * g["layers"] * g["picksPerLayer"] + 2, bad[0])
	else:
		note = "every placement within reach (worst %.0f mm)" % (worst * 1000.0)
	return {"ok": not bad, "unreachable": len(bad), "worst_mm":
	        int(round(worst * 1000.0)), "note": note, "detail": bad[:8]}


def _rawFromRead(values):
	"""{key: int} from the read Config values, defaulting any missing or bad one so the cycle never stops."""
	raw = {}
	for (_, key, default), v in zip(P.GEOMETRY, values):
		try:
			raw[key] = int(v) if v is not None else int(default)
		except:
			raw[key] = int(default)
	return raw


def _geo(values=None):
	"""Current derived geometry from the tick's Config values, or the cache (else a read) when None."""
	global _G, _G_KEY
	if values is None:
		if _G is not None:
			return _G
		values = P.read([c[0] for c in P.GEOMETRY])
	raw = _rawFromRead(values)
	key = tuple(raw[c[1]] for c in P.GEOMETRY)
	if key != _G_KEY:
		old = _G
		_G = _geometry(raw)
		_G_KEY = key
		if old is not None:
			changed = [c[1] for c in P.GEOMETRY
			           if old["raw"][c[1]] != raw[c[1]]]
			LOG.info("geometry changed (%s): %s, %d cases a pallet, %d a "
			         "pick; %s" % (", ".join(changed), _G["pattern"],
			                        _G["perPallet"], _G["pick"],
			                        _G["reach"]["note"]))
			if not _G["reach"]["ok"]:
				LOG.warn("geometry: %s" % _G["reach"]["note"])
			if _S is not None:
				_onGeometryChange(_S, _G)
	return _G


def _onGeometryChange(s, g):
	"""Re-aim the running cycle at new geometry, keeping pallet counts clamped to the new capacity."""
	for n in P.STATIONS:
		st = s["st"][n]
		st["cases"] = min(g["perPallet"], st["cases"])
		if st["cases"] >= g["perPallet"]:
			st["complete"] = True
	st = s["st"][s["active"]]
	s["layer"] = min(g["layers"] - 1, st["cases"] // g["perLayer"])
	s["slot"] = (st["cases"] % g["perLayer"]) // g["pick"]
	s["buf"] = min(g["bufferMax"], s["buf"])
	s["safeY"] = _safeWristY(s, s["layer"])
	s["named"] = False


def infeedInfo():
	"""Infeed queue for the 3D page: cartons on the belt, capacity, pitch and stop gap in mm."""
	s = _state()
	g = _geo()
	return {"queue": int(s["buf"] + _staged(s)), "max": int(g["bufferMax"]),
	        "pitch_mm": int(round((g["caseD"] + QUEUE_GAP_M) * 1000.0)),
	        "stopGap_mm": int(round(QUEUE_STOP_GAP_M * 1000.0))}


def geometryInfo():
	"""Derived pattern, pick sizes, heights and reach report for ?cmd=state."""
	g = _geo()
	return {
		"pattern": g["pattern"],
		"rows": g["rows"], "cols": g["cols"],
		"casesPerPick": g["pick"],
		"picksPerLayer": g["picksPerLayer"],
		"casesPerPallet": g["perPallet"],
		"pickWristY_mm": int(round(g["pickWristY"] * 1000.0)),
		"stackTop_mm": int(round((g["deck"] + g["layers"] * g["caseH"]) * 1000.0)),
		"reach": g["reach"],
	}


def _stackTopM(s):
	"""Top of the taller of the two stacks, m; a part-built layer counts as whole."""
	g = _geo()
	top = g["deck"]
	for n in P.STATIONS:
		c = s["st"][n]["cases"]
		layers = (c + g["perLayer"] - 1) // g["perLayer"]
		top = max(top, g["deck"] + layers * g["caseH"])
	return top


def _safeWristY(s, layer):
	"""Travel height for this cycle: clear of both stacks, never below the pick height."""
	g = _geo()
	top = max(_stackTopM(s), g["deck"] + (layer + 1) * g["caseH"])
	return max(g["pickWristY"], top + SAFE_CLEAR_M)

# (name, machine-seconds at nominal, robot state); they sum to P.CYCLE_S.
# Swings change only J1 at the safe height; a diagonal takes the forearm through the stack.
PHASES = [
	("Approach", 1.6, "Picking"),    # swing back over to the infeed, up high
	("Descend", 1.2, "Picking"),     # straight down onto the case set
	("Grip", 1.0, "Picking"),        # cups seal, vacuum pulls
	("Lift", 1.3, "Picking"),        # straight up to safe height
	("Traverse", 3.0, "Placing"),    # swing to the pallet, height held
	("Lower", 1.8, "Placing"),       # straight down onto the layer
	("Release", 0.8, "Placing"),     # vacuum breaks, cases are set
	("Retract", 1.9, "Placing"),     # straight up, clear of the stack
]

JOG_RATE_MM_S = 120.0     # per machine-second

# The axis lags its command, so the Manual screen's commanded and actual differ during a move.
JOG_LAG_S = 0.25

# Real seconds: a browser tab closing mid-jog is a wall-clock event.
JOG_WATCHDOG_S = 30.0

HOLD_VACUUM_KPA = -66.0
LOW_VACUUM_KPA = -17.0

DISCHARGE_LIFT_S = 3.0     # pallet leaves the station
DISCHARGE_TOTAL_S = 8.0    # a fresh pallet is in place


_S = None


def _blank():
	# Solved, so the jog axis starts where the column really is at HOME.
	homeLift = _solve(HOME[1], HOME[2])[2]
	return {
		"t": JSystem.currentTimeMillis(),
		"ticks": 0,
		"phase": 0,
		"pf": 0.0,
		"cycleTime": P.CYCLE_S,
		"pose": list(HOME),
		"from": list(HOME),
		"idle": True,
		"safeY": _geo()["pickWristY"],
		"homing": 0.0,
		"wasBlocked": False,
		"active": 1,
		"slot": 0,
		"layer": 0,
		"buf": _geo()["bufferMax"],
		"carton": 0.0,
		"barcode": 0,
		"lastBarcode": "",
		"scanOK": True,
		"cpm": 0.0,
		"casesTotal": 0,
		"shiftIndex": -1,
		"cycleCount": 0,
		"zclock": 0.0,
		"named": False,
		"jogLift": homeLift,
		"jogTarget": homeLift,
		"jogHeld": 0.0,
		"guardWasHeld": False,
		"st": dict((n, {"present": True, "cases": 0, "complete": False,
		                "disch": 0.0}) for n in P.STATIONS),
	}


def _state():
	"""The live sim state, rehydrated from the tags on first use (e.g. after a project scan)."""
	global _S
	if _S is not None:
		return _S
	s = _blank()
	try:
		want = {"casesTotal": "Line/CasesTotal",
		        "shiftIndex": "Line/ShiftIndex",
		        "cycleCount": "Robot/CycleCount",
		        "lift": "Robot/Lift_mm",
		        "liftTarget": "Robot/LiftTarget_mm",
		        "barcode": "Conveyor/LastBarcode"}
		for n in P.STATIONS:
			want["p%d" % n] = "Pallet/Station%d/Present" % n
			want["c%d" % n] = "Pallet/Station%d/CasesPlaced" % n
			want["k%d" % n] = "Pallet/Station%d/Complete" % n
		v = P.readDict(want)
		s["casesTotal"] = int(v.get("casesTotal") or 0)
		s["shiftIndex"] = int(v.get("shiftIndex", -1) if v.get("shiftIndex") is not None else -1)
		s["cycleCount"] = int(v.get("cycleCount") or 0)
		if v.get("lift") is not None:
			s["jogLift"] = float(v.get("lift"))
			s["jogTarget"] = float(v.get("liftTarget") or v.get("lift"))
		bc = v.get("barcode") or ""
		if bc.startswith("T") and bc[1:].isdigit():
			s["barcode"] = int(bc[1:])
			s["lastBarcode"] = bc
		perPallet = _geo()["perPallet"]
		for n in P.STATIONS:
			st = s["st"][n]
			if v.get("p%d" % n) is not None:
				st["present"] = bool(v.get("p%d" % n))
			st["cases"] = min(perPallet, int(v.get("c%d" % n) or 0))
			st["complete"] = bool(v.get("k%d" % n))
			if st["cases"] >= perPallet:
				st["complete"] = True
		for n in P.STATIONS:
			if s["st"][n]["present"] and not s["st"][n]["complete"]:
				s["active"] = n
				break
	except:
		import traceback
		LOG.warn("could not rehydrate from tags, starting clean: %s"
		         % traceback.format_exc())
	_S = s
	return _S


def ticks():
	"""Number of simulation ticks run since this module last loaded."""
	return 0 if _S is None else _S.get("ticks", 0)


def info():
	"""Simulator internals (pose, phase, buffer, counts, geometry) for ?cmd=status."""
	s = _state()
	_, radius, wristY, _ = s["pose"]
	_, _, lift = _solve(radius, wristY)
	carriageY = BASE_Y + lift / 1000.0
	return {
		"wristY_m": round(wristY, 3),
		"safeY_m": round(s.get("safeY") or _geo()["pickWristY"], 3),
		"stackTop_m": round(_stackTopM(s), 3),
		"radius_m": round(radius, 3),
		"solveD_m": round(math.hypot(radius, wristY - carriageY), 3),
		"carriageY_m": round(carriageY, 3),
		"ticks": s["ticks"],
		"phase": PHASES[s["phase"]][0] if not s["idle"] else "Waiting",
		"activeStation": s["active"],
		"slot": s["slot"],
		"layer": s["layer"],
		"infeedBuffer": s["buf"],
		"infeedStaged": _staged(s),
		"infeedOnBelt": s["buf"] + _staged(s),
		"cycleTime": round(s["cycleTime"], 2),
		"casesTotal": s["casesTotal"],
		"cycleCount": s["cycleCount"],
		"geometry": geometryInfo(),
	}


def clearInternals():
	"""Drop the sub-cycle state so the next tick rebuilds it from the tags."""
	global _S
	_S = None


def _smooth(x):
	"""Smoothstep ease in and out, so joints accelerate rather than move at constant speed."""
	if x <= 0.0:
		return 0.0
	if x >= 1.0:
		return 1.0
	return x * x * (3.0 - 2.0 * x)


def _lerp(a, b, t):
	return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def _clamp(v, lo, hi):
	return lo if v < lo else (hi if v > hi else v)


def _placePose(station, slot, layer, safeY=None):
	"""Wrist pose over this slot: at the placement height, or at safeY with the same J1 and radius."""
	return _placePoseG(_geo(), station, slot, layer, safeY)


def _placePoseG(g, station, slot, layer, safeY):
	"""_placePose against an explicit geometry, for the reach report."""
	x, z = g["stations"].get(station, g["stations"][1])
	dx, dz = g["slots"][layer % 2][slot % g["picksPerLayer"]]
	if safeY is None:
		wristY = g["deck"] + layer * g["caseH"] + g["caseH"] + WRIST_TO_CASE_TOP_M
	else:
		wristY = safeY
	j4 = 90.0 if (layer % 2) else 0.0    # every second layer interlocks
	return _task(x + dx, z + dz, wristY, j4)


def _target(s, phase):
	"""Where the wrist is going by the end of this phase."""
	name = PHASES[phase][0]
	g = _geo()
	safeY = s.get("safeY") or g["pickWristY"]
	if name == "Approach":
		# At the higher of start and safe height, so the swing stays level after the stack has grown.
		return _task(INFEED_XZ[0], INFEED_XZ[1],
		             max(safeY, s["from"][2] if s.get("from") else safeY))
	if name == "Lift":
		return _task(INFEED_XZ[0], INFEED_XZ[1], safeY)
	if name in ("Descend", "Grip"):
		return g["pickLow"]
	if name in ("Traverse", "Retract"):
		return _placePose(s["active"], s["slot"], s["layer"], safeY)
	if name in ("Lower", "Release"):
		return _placePose(s["active"], s["slot"], s["layer"], None)
	return HOME


def _phaseSeconds(s, phase):
	return PHASES[phase][1] * (s["cycleTime"] / P.CYCLE_S)


def tick():
	"""Run one simulation step; a failure is logged, never raised."""
	# A gateway timer whose script throws can stop being scheduled.
	try:
		_tick()
	except:
		import traceback
		LOG.warn("tick failed: %s" % traceback.format_exc())


def _shiftIndex(now):
	"""8-hour shift number for an epoch-ms time, in the gateway's local zone."""
	# Calendar, not epoch arithmetic: dividing the millis gives UTC hours and
	# moves the shift boundaries off local time.
	cal = Calendar.getInstance()
	cal.setTimeInMillis(now)
	day = cal.get(Calendar.YEAR) * 366 + cal.get(Calendar.DAY_OF_YEAR)
	return int(day * 3 + cal.get(Calendar.HOUR_OF_DAY) // 8)


def _rollShift(s, now):
	"""Zero the shift total when the shift changes; ShiftIndex -1 (never recorded) counts as a change."""
	idx = _shiftIndex(now)
	if s["shiftIndex"] == idx:
		return
	if s["casesTotal"]:
		LOG.info("shift %d -> %d: cases this shift reset from %d"
		         % (s["shiftIndex"], idx, s["casesTotal"]))
	s["casesTotal"] = 0
	s["shiftIndex"] = idx


def _tick():
	s = _state()

	now = JSystem.currentTimeMillis()
	_rollShift(s, now)
	dtr = (now - s["t"]) / 1000.0
	s["t"] = now
	if dtr <= 0.0:
		dtr = 0.5
	if dtr > 2.0:
		# A pause, a busy gateway or a reload: integrating the whole gap teleports the arm.
		dtr = 2.0

	want = {
		"enabled": "Line/SimEnabled",
		"speed": "Line/SimSpeed",
		"mode": "Line/Mode",
		"jogUp": "Robot/JogUp",
		"jogDown": "Robot/JogDown",
		"guards": "Safety/GuardsClosed",
	}
	for path, key, default in P.GEOMETRY:
		want[key] = path
	ctl = P.readDict(want)
	f = dict(zip(P.FAULTS, P.read(["Faults/%s" % n for n in P.FAULTS])))
	for k in f:
		f[k] = bool(f[k])

	if ctl.get("enabled") is None:
		# The provider is not there yet: setup has not been run.
		return

	# A geometry change re-aims the cycle here, before anything below moves.
	_geo([ctl.get(key) for path, key, default in P.GEOMETRY])

	speed = _clamp(float(ctl.get("speed") or 1.0), 0.1, 20.0)
	dt = dtr * speed
	s["ticks"] += 1
	s["zclock"] += dt

	# GuardsClosed is an input: anyone writing it false holds the cell, not only the fault.
	held = f["GuardOpen"] or (ctl.get("guards") is False)
	robotFault = f["RobotAxisFault"] or f["VacuumLow"]
	blocked = held or robotFault

	if not ctl.get("enabled"):
		# The auto cycle stops; manual jog of the lift still runs.
		_jog(s, dt, dtr, ctl, blocked, False, None)
		_writeStopped(s, f, blocked, robotFault, held)
		return

	state = _motion(s, dt, f, blocked, robotFault, held)
	_material(s, dt, f, held)
	_stations(s, dt, f)
	_write(s, dt, dtr, f, ctl, state, blocked, robotFault, held)


def _motion(s, dt, f, blocked, robotFault, held):
	"""Advance the arm, and say what state the robot is in."""
	if blocked:
		s["wasBlocked"] = True
		return "Fault" if robotFault else "Held"

	if s["wasBlocked"]:
		# Re-home after a stop, and give the reserved but unpicked cases back to the buffer.
		s["buf"] = min(_geo()["bufferMax"], s["buf"] + _staged(s))
		s["wasBlocked"] = False
		s["homing"] = 2.5
		s["idle"] = True
		s["phase"] = 0
		s["pf"] = 0.0
		s["from"] = list(s["pose"])

	if s["homing"] > 0.0:
		s["homing"] -= dt
		s["pose"] = _lerp(s["pose"], HOME, min(1.0, dt / 1.2))
		return "Homing"

	if s["idle"]:
		s["pose"] = _lerp(s["pose"], HOME, min(1.0, dt / 1.5))
		if _startCycle(s, f):
			return PHASES[0][2]
		return "Idle"

	s["pf"] += dt
	guard = 0
	while s["pf"] >= _phaseSeconds(s, s["phase"]) and guard < 20:
		guard += 1
		s["pf"] -= _phaseSeconds(s, s["phase"])
		s["pose"] = list(_target(s, s["phase"]))
		_endPhase(s)
		s["phase"] += 1
		if s["phase"] >= len(PHASES):
			s["phase"] = 0
			s["cycleCount"] += 1
			if not _startCycle(s, f):
				s["idle"] = True
				s["pf"] = 0.0
				return "Idle"
		s["from"] = list(s["pose"])

	dur = _phaseSeconds(s, s["phase"])
	frac = _clamp(s["pf"] / dur, 0.0, 1.0) if dur > 0 else 1.0
	s["pose"] = _lerp(s["from"], _target(s, s["phase"]), _smooth(frac))
	s["frac"] = frac
	return PHASES[s["phase"]][2]


def _staged(s):
	"""Cases the running cycle has reserved that are still on the belt, until the cups seal."""
	if s["idle"]:
		return 0
	name = PHASES[s["phase"]][0]
	if name in ("Approach", "Descend"):
		return _geo()["pick"]
	if name == "Grip":
		# The same 0.35 the vacuum seals at in _grip().
		return 0 if s.get("frac", 0.0) > 0.35 else _geo()["pick"]
	return 0


def _endPhase(s):
	"""Side effects that happen exactly at a phase boundary."""
	name = PHASES[s["phase"]][0]
	if name != "Release":
		return
	g = _geo()
	st = s["st"][s["active"]]
	placed = min(g["pick"], g["perPallet"] - st["cases"])
	st["cases"] = min(g["perPallet"], st["cases"] + g["pick"])
	s["casesTotal"] += max(0, placed)
	if st["cases"] >= g["perPallet"]:
		st["complete"] = True

	# Raise the travel height now, so the extra rise for the taller stack
	# happens on the vertical retract and not part-way through the swing back.
	nextLayer = min(g["layers"] - 1, st["cases"] // g["perLayer"])
	s["safeY"] = max(s["safeY"], _safeWristY(s, nextLayer))


def _availableStation(s):
	"""The station to build on, preferring the current one; None if neither can take cases."""
	order = [s["active"]] + [n for n in P.STATIONS if n != s["active"]]
	for n in order:
		st = s["st"][n]
		if st["present"] and not st["complete"]:
			return n
	return None


def _startCycle(s, f):
	"""Begin a pick, if there is product staged and a pallet to build on."""
	g = _geo()
	if s["buf"] < g["pick"]:
		return False
	n = _availableStation(s)
	if n is None:
		return False
	s["active"] = n
	st = s["st"][n]
	s["layer"] = min(g["layers"] - 1, st["cases"] // g["perLayer"])
	s["slot"] = (st["cases"] % g["perLayer"]) // g["pick"]
	# Once per cycle: a travel height that moved mid-swing would jerk the wrist.
	s["safeY"] = _safeWristY(s, s["layer"])
	s["buf"] -= g["pick"]
	s["idle"] = False
	s["phase"] = 0
	s["pf"] = 0.0
	s["from"] = list(s["pose"])
	s["cycleTime"] = P.CYCLE_S * (0.97 + 0.09 * random.random())
	return True


def _material(s, dt, f, held):
	"""Cartons arriving on the infeed, and the photo-eyes they break."""
	s["c1"] = (not f["ConveyorJam"]) and (not held)
	s["c2"] = not held
	if not s["c1"]:
		return
	g = _geo()
	s["carton"] += dt
	guard = 0
	while s["carton"] >= g["cartonPitch"] and guard < 20:
		guard += 1
		s["carton"] -= g["cartonPitch"]
		# Staged cases still take room in the zone. The barcode advances either
		# way: the scanner is upstream of the zone that is full.
		if s["buf"] < g["bufferMax"] - _staged(s):
			s["buf"] += 1
		s["barcode"] += 1
		s["lastBarcode"] = "T%05d" % s["barcode"]
		s["scanOK"] = (s["barcode"] % 37) != 0


def _covered(g, buf, offset):
	"""True if one of `buf` queued cartons stands over this offset from the stop line."""
	pitch = g["caseD"] + QUEUE_GAP_M
	# Half a case plus half the gap: on the default belt PE_Carton sits on the
	# join between two boxes and would otherwise never read blocked.
	half = g["caseD"] / 2.0 + QUEUE_GAP_M / 2.0
	for i in range(int(buf)):
		if abs(offset - i * pitch) <= half:
			return True
	return False


def _eyes(s, f):
	"""The six photo-eyes and PE_Clear, blocked by the cartons actually on the belt."""
	g = _geo()
	buf = s["buf"] + _staged(s)
	if f["ConveyorJam"]:
		# A jam latches its eyes: which ones are made tells the operator where the carton stopped.
		return {"PE_Infeed": True, "PE_Carton": True, "PE_Length1": True,
		        "PE_Length2": False, "PE_Clear": False,
		        "PE_InPos1": buf >= 1, "PE_InPos2": buf >= 1}
	off = _eyeOffsets(g["raw"]["convLength_mm"] / 1000.0)
	eyes = {}
	for key, d in off.items():
		eyes[key] = _covered(g, buf, d)
	# Only the three run eyes: the staging eyes are made whenever a set is waiting.
	eyes["PE_Clear"] = not (eyes["PE_Carton"] or eyes["PE_Length1"]
	                        or eyes["PE_Length2"])
	return eyes


def _stations(s, dt, f):
	"""Discharge a finished pallet and put an empty one in its place, unless WrapperFilmFeed blocks it."""
	for n in P.STATIONS:
		st = s["st"][n]
		if not st["complete"]:
			st["disch"] = 0.0
			continue
		if f["WrapperFilmFeed"]:
			continue
		st["disch"] += dt
		if st["disch"] >= DISCHARGE_TOTAL_S:
			st["present"] = True
			st["cases"] = 0
			st["complete"] = False
			st["disch"] = 0.0
		elif st["disch"] >= DISCHARGE_LIFT_S:
			st["present"] = False


def _discharging(s, n):
	st = s["st"][n]
	return st["complete"] and st["disch"] > 0.0


def _grip(s, state, f):
	"""(gripper closed, vacuum kPa), following the phase."""
	if f["VacuumLow"]:
		return True, LOW_VACUUM_KPA + random.uniform(-1.5, 1.5)
	if state not in ("Picking", "Placing"):
		return False, 0.0
	name = PHASES[s["phase"]][0]
	frac = s.get("frac", 0.0)
	if name in ("Approach", "Descend"):
		return False, 0.0
	if name == "Grip":
		return frac > 0.35, HOLD_VACUUM_KPA * min(1.0, frac / 0.8)
	if name == "Release":
		return frac < 0.4, HOLD_VACUUM_KPA * (1.0 - min(1.0, frac / 0.6))
	if name == "Retract":
		return False, 0.0
	return True, HOLD_VACUUM_KPA + random.uniform(-1.8, 1.8)


def _jog(s, dt, dtr, ctl, blocked, autoRunning, solvedLift):
	"""Hold-to-run jog on the lift axis. Returns (Lift_mm, LiftTarget_mm)."""
	# Interlocks are checked here even though the screen greys the button:
	# the panel and the controller are separate safeguards.
	up = bool(ctl.get("jogUp"))
	down = bool(ctl.get("jogDown"))

	# The watchdog runs first and in every mode: a stuck bit is cleared even in auto.
	if up or down:
		s["jogHeld"] += dtr
	else:
		s["jogHeld"] = 0.0
	if s["jogHeld"] > JOG_WATCHDOG_S:
		P.write({"Robot/JogUp": False, "Robot/JogDown": False})
		LOG.warn("jog watchdog: a jog bit was held for more than %.0f s and "
		         "has been cleared - the session that set it is gone"
		         % JOG_WATCHDOG_S)
		s["jogHeld"] = 0.0
		up = down = False

	if autoRunning:
		# Auto owns the axis; track it so a drop into manual starts where the column is.
		s["jogLift"] = solvedLift
		s["jogTarget"] = solvedLift
		return solvedLift, solvedLift

	if up and down:
		# Both directions at once is a fault, not a race; the bits are left for the panel to clear.
		direction = 0
	elif blocked:
		direction = 0
	elif up:
		direction = 1
	elif down:
		direction = -1
	else:
		direction = 0

	target = s["jogTarget"]
	if direction:
		target = _clamp(target + direction * JOG_RATE_MM_S * dt,
		                0.0, LIFT_MAX_MM)
	lift = s["jogLift"]
	lift = lift + (target - lift) * min(1.0, dt / JOG_LAG_S)
	s["jogTarget"] = target
	s["jogLift"] = lift
	return lift, target


def _zoneRow(state, running, fault):
	if fault:
		return "Fault"
	if state == "held":
		return "Held"
	return "Running" if running else "Idle"


def _writeStopped(s, f, blocked, robotFault, held):
	"""Publish the stopped cell; lift, motors and fault stay live because Manual jogs."""
	state = "Fault" if robotFault else ("Held" if held else "Idle")
	paths = ["Line/Running", "Line/CasesPerMin", "Robot/State",
	         "Robot/Lift_mm", "Robot/LiftTarget_mm",
	         "Robot/MotorsOn", "Robot/Ready", "Robot/Fault",
	         "Conveyor/C1_Run", "Conveyor/C2_Run", "Conveyor/C3_Run",
	         "Conveyor/C1_Speed_mpm", "Conveyor/C2_Speed_mpm",
	         "Conveyor/C3_Speed_mpm"]
	vals = [False, 0.0, state,
	        round(s["jogLift"], 0), round(s["jogTarget"], 0),
	        (not blocked), False, bool(robotFault),
	        False, False, False, 0.0, 0.0, 0.0]
	paths, vals = _guardWrite(s, f, held, paths, vals)
	for zid in P.ZONE_IDS:
		paths += ["Zones/%s/State" % zid, "Zones/%s/Running" % zid]
		vals += ["Idle", False]
	P.writePaths(paths, vals)


def _guardWrite(s, f, held, paths, vals):
	"""Force GuardsClosed false while GuardOpen stands and true once after; otherwise leave it alone."""
	if f["GuardOpen"]:
		s["guardWasHeld"] = True
		paths.append("Safety/GuardsClosed")
		vals.append(False)
	elif s.get("guardWasHeld"):
		s["guardWasHeld"] = False
		paths.append("Safety/GuardsClosed")
		vals.append(True)
	return paths, vals


def _write(s, dt, dtr, f, ctl, state, blocked, robotFault, held):
	"""Everything the cell is, written in one round trip."""
	# The only place joint angles exist, solved from the wrist, so every pose the page gets is reachable.
	j1, radius, wristY, j4 = s["pose"]
	j2, j3, solvedLift = _solve(radius, wristY)
	grip, vac = _grip(s, state, f)
	eyes = _eyes(s, f)

	g = _geo()
	producing = state in ("Picking", "Placing")
	inst = (g["pick"] * 60.0 / s["cycleTime"]) if producing else 0.0
	# Eight machine-seconds of smoothing: no flicker between phases, a jam still shows within a cycle.
	s["cpm"] += (inst - s["cpm"]) * min(1.0, dt / 8.0)

	air = 620.0 + 6.0 * math.sin(s["zclock"] / 11.0) + random.uniform(-3.0, 3.0)
	airOK = air >= 550.0

	d1 = _discharging(s, 1)
	d2 = _discharging(s, 2)
	c3 = d1 or d2

	faultText = ""
	if f["RobotAxisFault"]:
		faultText = P.ROBOT_FAULT_TEXT["RobotAxisFault"]
	elif f["VacuumLow"]:
		faultText = P.ROBOT_FAULT_TEXT["VacuumLow"]

	paths = [
		"Line/Running", "Line/CasesPerMin", "Line/CycleTime_s",
		"Line/CasesTotal", "Line/ShiftIndex",
		"Robot/State", "Robot/J1_deg", "Robot/J2_deg", "Robot/J3_deg",
		"Robot/J4_deg", "Robot/Lift_mm", "Robot/GripperClosed",
		"Robot/Vacuum_kPa", "Robot/MotorsOn", "Robot/Homed", "Robot/Ready",
		"Robot/Healthy", "Robot/CycleCount", "Robot/CycleTime_s",
		"Robot/Fault", "Robot/FaultText",
		"Robot/LiftTarget_mm",
		"Safety/EStopOK", "Safety/AirPressureOK",
		"Safety/InterfacesOK", "Safety/AirPressure_kPa",
		"Conveyor/C1_Run", "Conveyor/C2_Run", "Conveyor/C3_Run",
		"Conveyor/C1_Speed_mpm", "Conveyor/C2_Speed_mpm",
		"Conveyor/C3_Speed_mpm",
		"Conveyor/Gate1_Up", "Conveyor/Gate2_Up", "Conveyor/Clamp_Extended",
		"Conveyor/LastBarcode", "Conveyor/ScanOK",
	]
	# Running means producing; "not faulted" is Safety/'s question.
	running = (not blocked) and (not s["idle"])

	lift, liftTarget = _jog(s, dt, dtr, ctl, blocked, running, solvedLift)

	vals = [
		bool(running), round(s["cpm"], 1), round(s["cycleTime"], 2),
		int(s["casesTotal"]), int(s["shiftIndex"]),
		state, round(j1, 1), round(j2, 1), round(j3, 1),
		round(j4, 1), round(lift, 0), bool(grip),
		round(vac, 1), (not blocked), (not robotFault),
		(not blocked) and s["homing"] <= 0.0,
		(not robotFault) and airOK, int(s["cycleCount"]),
		round(s["cycleTime"], 2),
		bool(robotFault), faultText,
		round(liftTarget, 0),
		True, bool(airOK), (not f["WrapperFilmFeed"]),
		round(air, 0),
		bool(s.get("c1")), bool(s.get("c2")), bool(c3),
		round(18.0 + random.uniform(-0.4, 0.4), 1) if s.get("c1") else 0.0,
		round(14.0 + random.uniform(-0.3, 0.3), 1) if s.get("c2") else 0.0,
		round(9.0 + random.uniform(-0.2, 0.2), 1) if c3 else 0.0,
		bool(d1), bool(d2),
		bool(s["st"][s["active"]]["present"] and not _discharging(s, s["active"])),
		s["lastBarcode"], bool(s["scanOK"]),
	]

	paths, vals = _guardWrite(s, f, held, paths, vals)

	for key in ("PE_Infeed", "PE_Carton", "PE_Length1", "PE_Length2",
	            "PE_InPos1", "PE_InPos2", "PE_Clear"):
		paths.append("Conveyor/%s" % key)
		vals.append(bool(eyes[key]))

	for n in P.STATIONS:
		st = s["st"][n]
		paths += ["Pallet/Station%d/Present" % n,
		          "Pallet/Station%d/CasesPlaced" % n,
		          "Pallet/Station%d/Layer" % n,
		          "Pallet/Station%d/Complete" % n]
		vals += [bool(st["present"]), int(st["cases"]),
		         int(min(g["layers"], st["cases"] // g["perLayer"])),
		         bool(st["complete"])]

	# Only Robot 1 is modelled; the other zones are animated so their rows move.
	zst = "held" if held else ""
	zone = {}
	zone["Z1"] = (state in ("Picking", "Placing"), robotFault)
	for i, zid in enumerate(("Z2", "Z3", "Z4")):
		o = (s["zclock"] + (i + 1) * 4.1) % P.CYCLE_S
		zone[zid] = ((not held) and o < 9.6, False)
	zone["Z5"] = ((not held) and not f["WrapperFilmFeed"], f["WrapperFilmFeed"])
	zone["Z6"] = (not held, False)
	zone["Z7"] = (bool(c3), False)
	zone["Z8"] = (bool(s.get("c1")), f["ConveyorJam"])

	if not s["named"]:
		# After a reload or a geometry change: zone names, and each station's pattern from Config.
		for zid in P.ZONE_IDS:
			paths.append("Zones/%s/Name" % zid)
			vals.append(P.ZONE_NAME[zid])
		for n in P.STATIONS:
			paths.append("Pallet/Station%d/PatternName" % n)
			vals.append(g["pattern"])
		s["named"] = True

	for zid in P.ZONE_IDS:
		running, fault = zone[zid]
		paths += ["Zones/%s/State" % zid, "Zones/%s/Running" % zid,
		          "Zones/%s/Fault" % zid]
		vals += [_zoneRow(zst, running, fault), bool(running), bool(fault)]

	P.writePaths(paths, vals)
