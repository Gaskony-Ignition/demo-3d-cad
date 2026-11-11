"""
The palletising cell's names, tag paths, default geometry, faults and tag/alarm
helpers - the one place the provider name and machine constants are spelled out.
"""

VERSION = "1.19.2"

PROVIDER = "MachineDemo"

CELL_NAME = "Palletising Cell 1"
CELL_OWNER = "ACME Machine Works"
CELL_SUBTITLE = "Robotic case palletiser, two build stations"

LOG = system.util.getLogger("MachineDemo.plant")


def tag(path):
	"""Return path prefixed with this demo's provider, e.g. "[MachineDemo]Robot/J1_deg"."""
	return "[%s]%s" % (PROVIDER, path)


# (tag path, ?cmd=state key, default). Only the defaults the Config tags are
# created with; everything live reads the tags.
GEOMETRY = [
	("Config/CaseW_mm", "caseW_mm", 300),
	("Config/CaseD_mm", "caseD_mm", 250),
	("Config/CaseH_mm", "caseH_mm", 220),
	("Config/PalletW_mm", "palletW_mm", 1200),
	("Config/PalletD_mm", "palletD_mm", 1000),
	("Config/PalletH_mm", "palletH_mm", 140),
	("Config/CasesPerLayer", "casesPerLayer", 12),
	("Config/Layers", "layers", 5),
	("Config/ConvHeight_mm", "convHeight_mm", 900),
	("Config/ConvLength_mm", "convLength_mm", 3300),
	("Config/ConvWidth_mm", "convWidth_mm", 620),
	("Config/Station1_X_mm", "station1X_mm", -1300),
	("Config/Station1_Z_mm", "station1Z_mm", -1500),
	("Config/Station2_X_mm", "station2X_mm", -1300),
	("Config/Station2_Z_mm", "station2Z_mm", 1500),
]
GEOMETRY_DEFAULT = dict((key, default) for path, key, default in GEOMETRY)

# Overrides on the defaults, picked from the 3D page. Check any new preset
# against the arm's reach (MachineDemo.sim.geometryInfo).
GEOMETRY_PRESETS = [
	("default", "Default cell",
	 "300 x 250 x 220 mm cases, 12 a layer, 5 layers, 1200 x 1000 pallet", {}),
	("euro-tall", "Tall cases, Euro pallet",
	 "350 mm cases, 8 a layer, 4 layers, on a 1200 x 800 Euro pallet",
	 {"caseH_mm": 350, "palletD_mm": 800, "casesPerLayer": 8, "layers": 4}),
	# At most five layers: the Overview draws a fixed strip of five layer pips.
	("small-dense", "Small cases, dense",
	 "200 x 200 x 150 mm cases, 30 a layer, 5 layers",
	 {"caseW_mm": 200, "caseD_mm": 200, "caseH_mm": 150,
	  "casesPerLayer": 30, "layers": 5}),
]

# The DEFAULT machine only; MachineDemo.sim derives the live values from the
# Config tags every tick.
CASES_PER_PICK = 3
SLOTS_PER_LAYER = 4
CASES_PER_LAYER = GEOMETRY_DEFAULT["casesPerLayer"]                  # 12
LAYERS_PER_PALLET = GEOMETRY_DEFAULT["layers"]                       # 5
CASES_PER_PALLET = CASES_PER_LAYER * LAYERS_PER_PALLET               # 60

PATTERN_NAME = "%d x %d interlock" % (LAYERS_PER_PALLET, CASES_PER_LAYER)

# Nominal cycle in MACHINE seconds; SimSpeed scales machine time against the
# wall clock, so reported cycle time and cases/min hold at any speed.
CYCLE_S = 12.6

# Arm dimensions live only in MachineDemo.sim.

STATIONS = [1, 2]

ZONE_META = [
	("Z1", "Robot 1"),
	("Z2", "Robot 2"),
	("Z3", "Robot 3"),
	("Z4", "Robot 4"),
	("Z5", "Wrapper"),
	("Z6", "Shuttle"),
	("Z7", "Pallet Outfeed"),
	("Z8", "Tray Conveyors"),
]
ZONE_IDS = [z[0] for z in ZONE_META]
ZONE_NAME = dict(ZONE_META)

# Injectable faults, in control-strip order.
FAULTS = ["GuardOpen", "RobotAxisFault", "VacuumLow", "ConveyorJam",
          "WrapperFilmFeed"]

FAULT_LABEL = {
	"GuardOpen": "Guard door open",
	"RobotAxisFault": "Robot axis following error",
	"VacuumLow": "Gripper vacuum low",
	"ConveyorJam": "Infeed carton jam",
	"WrapperFilmFeed": "Wrapper film feed fault",
}

FAULT_EFFECT = {
	"GuardOpen": "Drops the guard circuit: motors off, robot HELD in place, "
	             "infeed and transfer conveyors stop.",
	"RobotAxisFault": "Robot faults on J3 and freezes. Motors off, the pallet "
	                  "stops building.",
	"VacuumLow": "Gripper vacuum collapses mid-carry. The robot faults rather "
	             "than drop the cases.",
	"ConveyorJam": "Carton jams on the infeed: C1 stops, the photo-eye stays "
	               "blocked and the robot starves.",
	"WrapperFilmFeed": "Wrapper cannot take a finished pallet, so completed "
	                   "pallets stop discharging. The cell keeps running on "
	                   "the other station until both are full.",
}

ROBOT_FAULT_TEXT = {
	"RobotAxisFault": "J3 servo following error - reset required at the pendant",
	"VacuumLow": "Gripper vacuum below hold threshold - cases at risk",
}


def read(paths):
	"""Read provider-relative paths in one call; a bad-quality tag reads as None, never raises."""
	full = [tag(p) for p in paths]
	try:
		qvs = system.tag.readBlocking(full)
	except:
		import traceback
		LOG.warn("read failed: %s" % traceback.format_exc())
		return [None] * len(paths)
	out = []
	for q in qvs:
		try:
			out.append(q.value if q.quality.isGood() else None)
		except:
			out.append(None)
	return out


def readOne(path, default=None):
	"""Read one tag; return default if it is missing or bad quality."""
	v = read([path])[0]
	return default if v is None else v


def readDict(mapping):
	"""Read {key: tagpath} in one call and return {key: value}."""
	keys = list(mapping.keys())
	vals = read([mapping[k] for k in keys])
	return dict(zip(keys, vals))


def write(mapping):
	"""Write {tagpath: value} in one call; return the number written, 0 on failure."""
	if not mapping:
		return 0
	keys = list(mapping.keys())
	try:
		system.tag.writeBlocking([tag(k) for k in keys],
		                         [mapping[k] for k in keys])
		return len(keys)
	except:
		import traceback
		LOG.warn("write failed: %s" % traceback.format_exc())
		return 0


def writePaths(paths, values):
	"""Write parallel lists of paths and values; return the number written, 0 on failure."""
	if not paths:
		return 0
	try:
		system.tag.writeBlocking([tag(p) for p in paths], values)
		return len(paths)
	except:
		import traceback
		LOG.warn("write failed: %s" % traceback.format_exc())
		return 0


def liveAlarms():
	"""Return this provider's standing alarms as dicts: active first, then unacked, then by label."""
	try:
		# prov:<provider>:* silently matches nothing; the /tag:* part is required.
		events = system.alarm.queryStatus(
			source=["prov:%s:/tag:*" % PROVIDER])
	except:
		import traceback
		LOG.warn("queryStatus failed: %s" % traceback.format_exc())
		return []
	out = []
	for e in events:
		out.append({
			"label": _field(e, lambda x: unicode(x.get("displayPath") or u""),
			                u""),
			"name": _field(e, lambda x: unicode(x.getName()), u"Alarm"),
			"priority": _field(e, lambda x: unicode(x.getPriority()), u""),
			"state": _field(e, lambda x: unicode(x.getState()), u""),
			"active": _field(e, lambda x: unicode(x.getState()).lower()
			                 .startswith("active"), False),
			"acked": _field(e, lambda x: bool(x.isAcked()), True),
			"source": _field(e, lambda x: unicode(x.getSource()), u""),
			"time": _field(e, lambda x: system.date.format(
				x.get("eventTime"), "HH:mm:ss"), u""),
		})
	out.sort(key=lambda a: (not a["active"], a["acked"], a["label"]))
	return out


def _field(event, fn, default):
	"""fn(event), or default if it raises."""
	# Guarded per field, not per row: an accessor missing on some builds
	# (isActive) would otherwise drop the whole alarm.
	try:
		return fn(event)
	except:
		return default


def alarmCounts():
	"""Return {"active": n, "unacked": n} for this demo's alarms; unacked counts active ones only."""
	active = 0
	unacked = 0
	for a in liveAlarms():
		if a["active"]:
			active += 1
			if not a["acked"]:
				unacked += 1
	return {"active": active, "unacked": unacked}
