"""
The state snapshot the 3D page polls at 4 Hz, and the presenter's controls.
state() is one readBlocking of a cached path list plus indexing; its shape is
frozen (docs/CONTRACT.md). The controls only write tags the simulator reads.
"""

from java.lang import System as JSystem

P = MachineDemo.plant
LOG = system.util.getLogger("MachineDemo.api")


# state() indexes every list below by position.
LINE = ["Line/Running", "Line/Mode", "Line/CasesPerMin", "Line/CycleTime_s",
        "Line/CasesTotal", "Line/ShiftTarget"]

# APPEND ONLY: state() reads these by position.
ROBOT = ["Robot/State", "Robot/J1_deg", "Robot/J2_deg", "Robot/J3_deg",
         "Robot/J4_deg", "Robot/Lift_mm", "Robot/GripperClosed",
         "Robot/Vacuum_kPa", "Robot/CycleCount", "Robot/Fault",
         "Robot/FaultText",
         "Robot/JogUp", "Robot/JogDown", "Robot/LiftTarget_mm"]

STATION = ["Present", "CasesPlaced", "Layer", "Complete", "PatternName"]

CONV = ["Conveyor/C1_Run", "Conveyor/C2_Run", "Conveyor/C3_Run",
        "Conveyor/PE_Infeed", "Conveyor/PE_Carton", "Conveyor/PE_Length1",
        "Conveyor/PE_Length2", "Conveyor/PE_InPos1", "Conveyor/PE_InPos2",
        "Conveyor/PE_Clear", "Conveyor/Gate1_Up", "Conveyor/Gate2_Up",
        "Conveyor/Clamp_Extended", "Conveyor/LastBarcode",
        "Conveyor/ScanOK"]

SAFETY = ["Safety/EStopOK", "Safety/GuardsClosed", "Safety/AirPressureOK",
          "Safety/InterfacesOK"]

FAULTS = ["Faults/%s" % n for n in
          ["WrapperFilmFeed", "ConveyorJam", "VacuumLow", "GuardOpen",
           "RobotAxisFault"]]

# (tag path, response key, default); the default fills in for a missing or bad Config tag.
CONFIG = P.GEOMETRY

_PLAN = None

# ms with no write to any tag before the snapshot is stale: ten missed 500 ms sim ticks.
STALE_AFTER_MS = 5000


def _plan():
	"""(paths, offsets), built on first use and cached."""
	# Lazy, not at import: touching a sibling module during import depends on load order.
	global _PLAN
	if _PLAN is not None:
		return _PLAN
	zones = []
	for z in P.ZONE_IDS:
		zones += ["Zones/%s/Name" % z, "Zones/%s/State" % z,
		          "Zones/%s/Running" % z, "Zones/%s/Fault" % z]
	pallet = []
	for n in P.STATIONS:
		pallet += ["Pallet/Station%d/%s" % (n, k) for k in STATION]

	config = [c[0] for c in CONFIG]
	groups = [("line", LINE), ("robot", ROBOT), ("pallet", pallet),
	          ("conv", CONV), ("safety", SAFETY), ("faults", FAULTS),
	          ("zones", zones), ("config", config)]
	paths = []
	off = {}
	for name, group in groups:
		off[name] = len(paths)
		paths += group
	off["_pallet"] = pallet
	off["_zones"] = zones
	_PLAN = (paths, off)
	return _PLAN


def _f(v, default=0.0):
	try:
		return round(float(v), 1)
	except:
		return default


def _i4(v):
	try:
		return int(v)
	except:
		return 0


def _b(v):
	return bool(v)


def _s(v):
	return u"" if v is None else unicode(v)


def _ci(v, default):
	"""One Config/* value as an int, or default if missing or unconvertible."""
	if v is None:
		return default
	try:
		return int(v)
	except:
		return default


def _readQ(paths):
	"""Like plant.read() (bad quality -> None), but also return the QualifiedValues."""
	full = [P.tag(p) for p in paths]
	try:
		qvs = system.tag.readBlocking(full)
	except:
		import traceback
		LOG.warn("read failed: %s" % traceback.format_exc())
		return [None] * len(paths), [None] * len(paths)
	vals = []
	for q in qvs:
		try:
			vals.append(q.value if q.quality.isGood() else None)
		except:
			vals.append(None)
	return vals, list(qvs)


def _quality(paths, qvs):
	"""The `quality` block for ?cmd=state: bad tag paths, staleness, worst quality."""
	# Memory tags stay Good when the sim stops, so staleness is the age of the
	# newest timestamp across the whole read (one tag alone can sit unchanged).
	bad = []
	worst_name = u"Good"
	worst_rank = 2   # 0 Bad, 1 Uncertain, 2 Good - lower is worse
	newest = None
	for path, qv in zip(paths, qvs):
		if qv is None:
			bad.append(path)
			if worst_rank > 0:
				worst_rank = 0
				worst_name = u"Bad_Failure"
			continue
		try:
			q = qv.quality
			good = q.isGood()
		except:
			bad.append(path)
			if worst_rank > 0:
				worst_rank = 0
				worst_name = u"Bad_Failure"
			continue
		if not good:
			bad.append(path)
		rank = 2
		try:
			if q.isBad():
				rank = 0
			elif q.isUncertain():
				rank = 1
		except:
			rank = 0
		if rank < worst_rank:
			worst_rank = rank
			worst_name = unicode(q)
		try:
			if qv.timestamp is not None:
				t = qv.timestamp.getTime()
				if newest is None or t > newest:
					newest = t
		except:
			pass

	stale = True
	if newest is not None:
		age = JSystem.currentTimeMillis() - newest
		stale = age > STALE_AFTER_MS

	return {
		"ok": (not bad) and (not stale),
		"bad": bad,
		"stale": stale,
		"worst": worst_name,
	}


def state():
	"""The whole cell in one dict for ?cmd=state; shape FROZEN, add keys only."""
	# A null in j1..j4 or lift stops the page's animation without an error.
	paths, o = _plan()
	v, qvs = _readQ(paths)

	line = v[o["line"]:o["line"] + len(LINE)]
	rb = v[o["robot"]:o["robot"] + len(ROBOT)]
	cv = v[o["conv"]:o["conv"] + len(CONV)]
	sf = v[o["safety"]:o["safety"] + len(SAFETY)]
	fl = v[o["faults"]:o["faults"] + len(FAULTS)]
	pl = v[o["pallet"]:o["pallet"] + len(o["_pallet"])]
	zn = v[o["zones"]:o["zones"] + len(o["_zones"])]
	cf = v[o["config"]:o["config"] + len(CONFIG)]

	pallets = []
	for k in range(len(P.STATIONS)):
		b = k * len(STATION)
		pallets.append({
			"present": _b(pl[b + 0]),
			"cases": _i4(pl[b + 1]),
			"layer": _i4(pl[b + 2]),
			"complete": _b(pl[b + 3]),
			"pattern": _s(pl[b + 4]),
		})

	zones = []
	for k, zid in enumerate(P.ZONE_IDS):
		b = k * 4
		zones.append({
			"id": zid,
			"name": _s(zn[b + 0]) or P.ZONE_NAME[zid],
			"state": _s(zn[b + 1]) or u"Idle",
			"running": _b(zn[b + 2]),
			"fault": _b(zn[b + 3]),
		})

	return {
		"ok": True,
		"ts": JSystem.currentTimeMillis(),
		"line": {
			"running": _b(line[0]),
			"mode": _s(line[1]) or u"Auto",
			"cpm": _f(line[2]),
			"cycle": _f(line[3]),
			"cases": _i4(line[4]),
			"target": _i4(line[5]),
		},
		"robot": {
			"state": _s(rb[0]) or u"Idle",
			"j1": _f(rb[1]), "j2": _f(rb[2]), "j3": _f(rb[3]),
			"j4": _f(rb[4]), "lift": _f(rb[5]),
			"grip": _b(rb[6]), "vac": _f(rb[7]),
			"cycles": _i4(rb[8]),
			"fault": _b(rb[9]), "faultText": _s(rb[10]),
			"jogUp": _b(rb[11]), "jogDown": _b(rb[12]),
			"liftTarget": _f(rb[13]),
		},
		"pallets": pallets,
		"conv": {
			"c1": _b(cv[0]), "c2": _b(cv[1]), "c3": _b(cv[2]),
			"pe": {"infeed": _b(cv[3]), "carton": _b(cv[4]),
			       "len1": _b(cv[5]), "len2": _b(cv[6]),
			       "inpos1": _b(cv[7]), "inpos2": _b(cv[8]),
			       "clear": _b(cv[9])},
			"gate1": _b(cv[10]), "gate2": _b(cv[11]), "clamp": _b(cv[12]),
			"barcode": _s(cv[13]), "scanOK": _b(cv[14]),
		},
		"safety": {"estop": _b(sf[0]), "guards": _b(sf[1]),
		           "air": _b(sf[2]), "interfaces": _b(sf[3])},
		"faults": {"WrapperFilmFeed": _b(fl[0]), "ConveyorJam": _b(fl[1]),
		           "VacuumLow": _b(fl[2]), "GuardOpen": _b(fl[3]),
		           "RobotAxisFault": _b(fl[4])},
		"zones": zones,
		"config": dict((key, _ci(val, default))
		               for (path, key, default), val in zip(CONFIG, cf)),
		"quality": _quality(paths, qvs),
		"geometry": _geometry(),
		"infeed": _infeed(),
		# A stat of the scene view.json, not a read: this is on the 4 Hz poll.
		"sceneRev": _sceneRev(),
	}


def _sceneRev():
	try:
		return MachineDemo.scene.revision()
	except:
		return ""


def _infeed():
	try:
		return MachineDemo.sim.infeedInfo()
	except:
		return {"queue": 0, "max": 0}


def _geometry():
	try:
		return MachineDemo.sim.geometryInfo()
	except:
		import traceback
		LOG.warn("geometryInfo failed: %s" % traceback.format_exc())
		return {"reach": {"ok": True, "unreachable": 0, "note": u""}}


def faults():
	"""Every fault with its label, effect and whether it is active."""
	live = dict(zip(P.FAULTS, P.read(["Faults/%s" % n for n in P.FAULTS])))
	return [{"name": n, "label": P.FAULT_LABEL[n], "effect": P.FAULT_EFFECT[n],
	         "active": bool(live.get(n))} for n in P.FAULTS]


def setFault(name, on=True):
	"""Inject or clear one fault by name (case-insensitive); raise ValueError if unknown."""
	name = (name or "").strip()
	match = [n for n in P.FAULTS if n.lower() == name.lower()]
	if not match:
		raise ValueError("no such fault: '%s' - try one of %s"
		                 % (name, ", ".join(P.FAULTS)))
	n = match[0]
	P.write({"Faults/%s" % n: bool(on)})
	# Wait out a 500 ms sim tick so the caller's next read shows the cell's reaction.
	from java.lang import Thread as JThread
	JThread.sleep(700)
	LOG.info("%s fault %s" % ("injected" if on else "cleared", n))
	return {"fault": n, "active": bool(on), "label": P.FAULT_LABEL[n],
	        "effect": P.FAULT_EFFECT[n] if on else "cleared"}


def reset():
	"""Back to steady state: faults, jog bits, safety and CAD sim slots cleared, Auto; pallets kept."""
	mapping = dict(("Faults/%s" % n, False) for n in P.FAULTS)
	# A jog bit left set would move the axis as soon as the interlocks clear.
	mapping["Robot/JogUp"] = False
	mapping["Robot/JogDown"] = False
	mapping["Line/SimEnabled"] = True
	mapping["Line/Mode"] = "Auto"
	mapping["Robot/Fault"] = False
	mapping["Robot/FaultText"] = ""
	mapping["Safety/EStopOK"] = True
	mapping["Safety/GuardsClosed"] = True
	for i in range(1, MachineDemo.tagdata.CAD_SIM_SLOTS + 1):
		mapping["CadSim/Sim%d/Active" % i] = False
	P.write(mapping)
	MachineDemo.sim.clearInternals()
	LOG.info("reset to steady state")
	return {"cleared": list(P.FAULTS), "running": True}


def geometryPresets():
	"""The whole-machine geometry presets as name, label, detail and values."""
	return [{"name": n, "label": l, "detail": d, "values": v}
	        for n, l, d, v in P.GEOMETRY_PRESETS]


def setGeometry(preset="default"):
	"""Write every Config tag from the named preset over the defaults; raise ValueError if unknown."""
	key = (preset or "default").strip().lower()
	match = [p for p in P.GEOMETRY_PRESETS if p[0] == key]
	if not match:
		raise ValueError("no such geometry preset: '%s' - try one of %s"
		                 % (preset, ", ".join(p[0] for p in P.GEOMETRY_PRESETS)))
	name, label, detail, over = match[0]
	values = dict(P.GEOMETRY_DEFAULT)
	values.update(over)
	P.write(dict((path, int(values[k])) for path, k, d in P.GEOMETRY))
	LOG.info("geometry set to preset '%s' (%s)" % (name, detail))
	return {"preset": name, "label": label, "values": values}


def setSpeed(value):
	"""Set machine time as a multiple of real time, clamped to 0.25..10."""
	# Alarm on-delays count real seconds whatever this speed is.
	try:
		v = float(value)
	except:
		raise ValueError("speed must be a number, not '%s'" % value)
	v = max(0.25, min(10.0, v))
	P.write({"Line/SimSpeed": v})
	return {"speed": v}


def setMode(value):
	"""Auto or Manual. Manual stops the pattern; the arm holds where it is."""
	m = (value or "").strip().capitalize()
	if m not in ("Auto", "Manual"):
		raise ValueError("mode must be Auto or Manual, not '%s'" % value)
	P.write({"Line/Mode": m, "Line/SimEnabled": m == "Auto"})
	return {"mode": m}


def setJog(name, on=True):
	"""Set or clear the up or down jog bit; the simulator does the moving."""
	key = (name or "").strip().lower()
	if key not in ("up", "down"):
		raise ValueError("jog direction must be up or down, not '%s'" % name)
	tag = "Robot/Jog%s" % ("Up" if key == "up" else "Down")
	P.write({tag: bool(on)})
	return {"tag": tag, "on": bool(on)}


def setGuards(closed):
	"""Write Safety/GuardsClosed, a simulator input, as a guard switch would."""
	P.write({"Safety/GuardsClosed": bool(closed)})
	return {"guardsClosed": bool(closed)}


def status():
	"""A one-screen account of the cell, for ?cmd=status."""
	s = state()
	return {
		"cell": P.CELL_NAME,
		"owner": P.CELL_OWNER,
		"version": P.VERSION,
		"provider": P.PROVIDER,
		"line": s["line"],
		"robot": {"state": s["robot"]["state"], "cycles": s["robot"]["cycles"],
		          "fault": s["robot"]["fault"],
		          "faultText": s["robot"]["faultText"]},
		"pallets": s["pallets"],
		"safety": s["safety"],
		"faults": faults(),
		"zones": s["zones"],
		"alarms": P.alarmCounts(),
		"sim": MachineDemo.sim.info(),
	}
