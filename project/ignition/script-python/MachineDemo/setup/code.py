"""Stands the cell up on a gateway from the project, live through system.config:
tag provider, tags and robot UDT, and where the edition allows, the demo's own
SQLite connection and alarm journal. check() reports each item independently,
fix(key) creates one, run() creates whatever is missing.
"""

P = MachineDemo.plant

PROVIDER = P.PROVIDER
LOG = system.util.getLogger("MachineDemo.setup")


# Same JSON as tag-provider/<name>/config.json on disk; keep this the only copy.
TAG_PROVIDER_CONFIG = {
	"profile": {
		"allowBackfill": False,
		"enableTagReferenceStore": True,
		"type": "STANDARD",
	},
	"settings": {
		"defaultDatasourceName": None,
		"editPermissions": {"securityLevels": [], "type": "AllOf"},
		"readOnly": False,
		"readPermissions": {"securityLevels": [], "type": "AllOf"},
		"valuePersistence": "Database",
		"writePermissions": {"securityLevels": [], "type": "AllOf"},
	},
}

DB = "MachineDemoDB"
DB_FILE = "machine-hmi-demo.db"

# WAL so the alarm table can read while the journal writes; busy_timeout covers
# two writers. ${data} is expanded by Ignition to the gateway's data directory.
DB_URL = ("jdbc:sqlite:${data}/%s?journal_mode=WAL&busy_timeout=30000"
          % DB_FILE)

# Ignition's defaults except poolMaxActive 4: one SQLite file has one write lock.
# No password key: SQLite opens a file, it does not log in.
DB_CONFIG = {
	"connectURL": DB_URL,
	"connectionProps": "",
	"connectionResetParams": "",
	"defaultTransactionLevel": "DEFAULT",
	"driver": "SQLite",
	"evictionRate": -1,
	"evictionTests": 3,
	"evictionTime": 1800000,
	"failoverMode": "STANDARD",
	"failoverProfile": "",
	"includeSchemaInTableName": False,
	"poolInitSize": 0,
	"poolMaxActive": 4,
	"poolMaxIdle": 8,
	"poolMaxWait": 5000,
	"poolMinIdle": 0,
	"slowQueryLogThreshold": 60000,
	"testOnBorrow": True,
	"testOnReturn": False,
	"testWhileIdle": False,
	"translator": "SQLITE",
	"username": "",
	"validationQuery": "SELECT 1",
	"validationSleepTime": 10000,
}

JOURNAL = PROVIDER
JOURNAL_NAME_TAG = "Line/JournalName"
JOURNAL_TABLE = "alarm_events"
JOURNAL_DATA_TABLE = "alarm_event_data"

# minPriority Diagnostic so no injected fault is silently left out of history.
JOURNAL_CONFIG = {
	"profile": {"queryOnly": False, "type": "DATASOURCE"},
	"settings": {
		"advanced": {
			"dataTableName": JOURNAL_DATA_TABLE,
			"tableName": JOURNAL_TABLE,
			"useStoreAndForward": True,
		},
		"dataFilters": {"pathFilterName": "", "pathOrSourceFilterName": "",
		                "sourceFilterName": ""},
		"datasource": DB,
		"eventData": {"dynamicAssociatedData": True, "dynamicConfig": True,
		              "staticAssociatedData": True, "staticConfig": False},
		"events": {"minPriority": "Diagnostic",
		           "storeFromEnabledChange": False,
		           "storeShelvedEvents": True},
		"pruning": {"age": 1, "ageUnits": "YEAR", "enabled": False},
	},
}

# JOURNAL_CONFIG without "advanced" and "datasource", for a gateway with no database.
JOURNAL_CONFIG_LOCAL = {
	"profile": {"type": "LOCAL"},
	"settings": {
		"dataFilters": {"pathFilterName": "", "pathOrSourceFilterName": "",
		                "sourceFilterName": ""},
		"eventData": {"dynamicAssociatedData": True, "dynamicConfig": True,
		              "staticAssociatedData": True, "staticConfig": False},
		"events": {"minPriority": "Diagnostic",
		           "storeFromEnabledChange": False,
		           "storeShelvedEvents": True},
		"pruning": {"age": 1, "ageUnits": "YEAR", "enabled": False},
	},
}


# Test-only: True/False forces _hasDatabaseModule's answer. Ship as None.
_FORCE_NO_DB = None


def _hasDatabaseModule():
	"""True if the gateway registers the database-connection type (SQL Bridge; absent on Edge)."""
	if _FORCE_NO_DB is not None:
		return not _FORCE_NO_DB
	from java.lang import Throwable as JThrowable
	try:
		return ("ignition", "database-connection") in system.config.getResourceTypes()
	except (JThrowable, Exception):
		# Undocumented call: if it is missing, assume no database rather than risk a write.
		LOG.warn("could not determine database capability - "
		         "assuming none (see _hasDatabaseModule)")
		return False


def _isEdgeGateway():
	"""True on Ignition Edge, detected by the Edge-only edge-sync-settings resource type."""
	# Not edge-system-properties: a standard gateway registers that too.
	from java.lang import Throwable as JThrowable
	try:
		return ("ignition", "edge-sync-settings") in \
		       system.config.getResourceTypes()
	except (JThrowable, Exception):
		return False


def journalName():
	"""Return the alarm journal name to use: Edge's own journal on Edge, else this demo's JOURNAL."""
	if not _isEdgeGateway():
		return JOURNAL
	have = _names("alarm-journal")
	if JOURNAL in have:
		return JOURNAL
	return have[0] if have else JOURNAL


# A representative tag sample; nothing in the project reads it (_tagsCheck reads every path).
PROBE_TAGS = ["Config/CaseW_mm", "Line/SimEnabled", "Safety/GuardsClosed",
              "Robot/J1_deg", "Robot/LiftTarget_mm", "Robot/JogUp",
              "Pallet/Station2/CasesPlaced", "Conveyor/PE_Clear",
              "Zones/Z8/Name", "Faults/RobotAxisFault"]

# The tags that must be carrying alarm definitions, and how many each.
ALARM_TAGS = (["Safety/EStopOK", "Safety/GuardsClosed",
               "Safety/AirPressureOK", "Safety/InterfacesOK",
               "Safety/AirPressure_kPa", "Robot/Fault"]
              + ["Faults/%s" % n for n in
                 ["WrapperFilmFeed", "ConveyorJam", "VacuumLow", "GuardOpen",
                  "RobotAxisFault"]])


def _resource(typeId, name):
	"""A config resource, or None if it is missing."""
	# getResource raises a java.lang.Throwable when missing; in Jython
	# `except Exception` does not catch it.
	from java.lang import Throwable as JThrowable
	try:
		return system.config.getResource(moduleId="ignition", typeId=typeId,
		                                 name=name)
	except (JThrowable, Exception):
		return None


def _config(res):
	"""A resource's config as plain Python, via a JSON round trip of getConfig()'s wrappers."""
	return system.util.jsonDecode(system.util.jsonEncode(res.getConfig()))


def _names(typeId):
	"""Sorted names of every config resource of typeId on this gateway; [] on error."""
	from java.lang import Throwable as JThrowable
	try:
		return sorted([unicode(r.getName()) for r in
		               system.config.getResources(moduleId="ignition",
		                                          typeId=typeId)])
	except (JThrowable, Exception):
		return []


def _upsert(typeId, name, config, description):
	"""Create or replace a config resource; return "created" or "updated"."""
	# replace() is refused without the resource's current signature.
	existing = _resource(typeId, name)
	if existing is None:
		system.config.create(moduleId="ignition", typeId=typeId, name=name,
		                     config=config, description=description,
		                     actor="MachineDemo.setup")
		return "created"
	system.config.replace(moduleId="ignition", typeId=typeId, name=name,
	                      config=config, signature=existing.getSignature(),
	                      actor="MachineDemo.setup")
	return "updated"


def _providerCheck():
	"""(ok, detail): the provider resource exists and browses."""
	# Edge accepts a second provider resource then refuses to start it; only a browse shows that.
	if _resource("tag-provider", PROVIDER) is None:
		if _isEdgeGateway():
			return False, (u"tag provider '%s' does not exist. Edge keeps "
			               u"exactly ONE realtime provider and will not "
			               u"start a second - name it '%s' under Config -> "
			               u"Ignition Edge -> Tag Provider (this gateway "
			               u"has: %s)"
			               % (PROVIDER, PROVIDER,
			                  u", ".join(_names("tag-provider"))))
		return False, u"tag provider '%s' does not exist" % PROVIDER
	from java.lang import Throwable as JThrowable
	try:
		system.tag.browse("[%s]" % PROVIDER)
	except (JThrowable, Exception):
		return False, (u"tag provider '%s' is configured but not running - "
		               u"on Edge that means a second provider was written "
		               u"and refused at startup; rename Edge's own provider "
		               u"to '%s' instead" % (PROVIDER, PROVIDER))
	return True, u"tag provider '%s' exists and is running" % PROVIDER


def _providerFix():
	if _isEdgeGateway() and _resource("tag-provider", PROVIDER) is None:
		# Edge would accept a second provider and never start it.
		return (u"not created - Edge permits one realtime provider. Set "
		        u"Config -> Ignition Edge -> Tag Provider to '%s' and save; "
		        u"the rename is live, no restart." % PROVIDER)
	what = _upsert("tag-provider", PROVIDER, TAG_PROVIDER_CONFIG,
	               "Palletising cell demo tag provider - the cell's folders "
	               "live at the provider root")
	return u"tag provider '%s' %s" % (PROVIDER, what)


def _tagsCheck():
	"""(ok, detail): every path in MachineDemo.tagdata reads Good from the provider."""
	from java.lang import Throwable as JThrowable
	paths = MachineDemo.tagdata.paths()
	try:
		qvs = system.tag.readBlocking([P.tag(p) for p in paths])
	except (JThrowable, Exception):
		return False, u"the tag provider did not answer"
	bad = []
	for path, q in zip(paths, qvs):
		try:
			good = q.quality.isGood()
		except:
			good = False
		if not good:
			bad.append(path)
	if bad:
		shown = u", ".join(bad[:6])
		if len(bad) > 6:
			shown = u"%s and %d more" % (shown, len(bad) - 6)
		return False, u"%d of %d tags missing or bad quality: %s" % (
			len(bad), len(paths), shown)
	c = MachineDemo.tagdata.counts()
	return True, u"all %d tags in %d top-level nodes readable in [%s]" % (
		len(paths), c["folders"], PROVIDER)


def _bad(qualities):
	"""The non-Good quality codes from a system.tag.configure result, as text."""
	# configure does not raise on a partial write; the qualities are the only sign.
	out = []
	for q in (qualities or []):
		try:
			if q.isGood():
				continue
		except:
			pass
		try:
			text = unicode(q)
		except:
			text = u"?"
		if not text.startswith(u"Good"):
			out.append(text)
	return out


def _writeTypes():
	"""Write the UDT definitions into [<provider>]_types_; return how many, raise if refused."""
	# Must run before the provider root: the Robot instance is refused without its definition.
	defs = MachineDemo.tagdata.types()
	q = system.tag.configure(u"[%s]_types_" % PROVIDER, defs, u"o")
	bad = _bad(q)
	if bad:
		raise Exception(u"UDT definitions refused: %s" % u", ".join(bad))
	return len(defs)


def _tagsFix():
	"""Overwrite the UDT definitions and tag tree in the provider; return a one-line account."""
	from java.lang import Thread as JThread
	last = None
	# A just-created provider may not accept writes yet and fails with a bare throwable.
	for _attempt in range(3):
		try:
			nTypes = _writeTypes()
			replaced = _clearStaleRobot()
			folders = MachineDemo.tagdata.tags()
			q = system.tag.configure(u"[%s]" % PROVIDER, folders, u"o")
			bad = _bad(q)
			if bad:
				raise Exception(u"provider refused: %s" % u", ".join(bad))
			_settle()
			c = MachineDemo.tagdata.counts()
			said = (u"wrote %d UDT definition(s) and %d tags with %d alarm "
			        u"definitions into [%s]"
			        % (nTypes, c["tags"], c["alarms"], PROVIDER))
			if replaced:
				said = u"%s, %s" % (said, replaced)
			return said
		except:
			import traceback
			last = traceback.format_exc().strip().split("\n")[-1]
			JThread.sleep(2000)
	raise Exception(u"could not write tags into [%s]: %s" % (PROVIDER, last))


def _robotCarriesValues():
	"""True if Robot/J1_deg reads Good, i.e. the robot instance's members are live."""
	from java.lang import Throwable as JThrowable
	try:
		q = system.tag.readBlocking([P.tag("Robot/J1_deg")])[0]
		return bool(q.quality.isGood())
	except (JThrowable, Exception):
		return False


def _settle(seconds=6):
	"""Wait up to seconds for the robot's members to read Good after configure returns."""
	from java.lang import Thread as JThread
	for _i in range(int(seconds * 2)):
		if _robotCarriesValues():
			return True
		JThread.sleep(500)
	return False


def _clearStaleRobot():
	"""Delete the Robot node unless it is a live instance; return what was replaced, or None."""
	# An instance written over a folder answers Good but its members never carry
	# a value (docs/CONTRACT.md, "The upgrade trap").
	kind = _nodeType("Robot")
	if kind is None:
		return None
	if kind == u"UdtInstance" and _robotCarriesValues():
		return None
	from java.lang import Thread as JThread
	system.tag.deleteTags([P.tag("Robot")])
	JThread.sleep(500)
	if kind == u"UdtInstance":
		return u"replaced a Robot instance whose members carried no value"
	return u"replaced the old Robot %s with an instance of '%s'" % (
		kind.lower() if kind else u"node", MachineDemo.tagdata.ROBOT_TYPE)


def _nodeType(path):
	"""The tagType at a provider path, or None if there is nothing there."""
	from java.lang import Throwable as JThrowable
	try:
		cfg = system.tag.getConfiguration(P.tag(path), False)
	except (JThrowable, Exception):
		return None
	for node in cfg:
		try:
			return unicode(node.get("tagType"))
		except (JThrowable, Exception):
			return None
	return None


def _udtCheck():
	"""(ok, detail): the robot UDT has every member and Robot is a live instance of it."""
	typeName = MachineDemo.tagdata.ROBOT_TYPE
	typePath = u"_types_/%s" % typeName
	if _nodeType(typePath) != u"UdtType":
		return False, u"no UDT definition at [%s]%s" % (PROVIDER, typePath)
	from java.lang import Throwable as JThrowable
	try:
		members = [unicode(t.get("name")) for t in
		           system.tag.getConfiguration(P.tag(typePath), True)[0]
		           .get("tags")]
	except (JThrowable, Exception):
		members = []
	want = [unicode(m["name"]) for m in MachineDemo.tagdata._robotMembers()]
	missing = [m for m in want if m not in members]
	if missing:
		return False, (u"'%s' is missing member(s): %s"
		               % (typeName, u", ".join(missing)))
	kind = _nodeType("Robot")
	if kind != u"UdtInstance":
		return False, (u"[%s]Robot is a %s, not an instance of '%s'"
		               % (PROVIDER, kind or u"nothing", typeName))
	if not _robotCarriesValues():
		return False, (u"[%s]Robot is an instance of '%s' but its members "
		               u"carry no value - it was written over the old folder "
		               u"instead of replacing it. Fix this row."
		               % (PROVIDER, typeName))
	return True, (u"'%s' defines %d members and [%s]Robot is a live instance "
	              u"of it" % (typeName, len(members), PROVIDER))


def _configPaths():
	return [p for p in MachineDemo.tagdata.paths() if p.startswith("Config/")]


def _configCheck():
	"""(ok, detail): every Config tag reads, with the case and pallet sizes quoted."""
	paths = _configPaths()
	if not paths:
		return False, u"the project carries no Config tags"
	vals = P.read(paths)
	missing = [p for p, v in zip(paths, vals) if v is None]
	if missing:
		return False, u"missing or bad quality: %s" % u", ".join(missing)
	got = dict(zip(paths, vals))
	return True, (u"%d geometry tags in [%s]Config - case %sx%sx%s mm, pallet "
	              u"%sx%s mm, %s cases x %s layers"
	              % (len(paths), PROVIDER,
	                 got.get("Config/CaseW_mm"), got.get("Config/CaseD_mm"),
	                 got.get("Config/CaseH_mm"), got.get("Config/PalletW_mm"),
	                 got.get("Config/PalletD_mm"),
	                 got.get("Config/CasesPerLayer"),
	                 got.get("Config/Layers")))


def _alarmsOn(path):
	from java.lang import Throwable as JThrowable
	try:
		cfg = system.tag.getConfiguration(P.tag(path), False)
	except (JThrowable, Exception):
		return []
	out = []
	for node in cfg:
		for a in (node.get("alarms") or []):
			try:
				out.append(unicode(a.get("name")))
			except:
				out.append(u"?")
	return out


def _alarmsCheck():
	"""(ok, detail): every ALARM_TAGS tag carries alarms and each tagdata.CAD_PARTS alarm has its part."""
	missing = [p for p in ALARM_TAGS if not _alarmsOn(p)]
	if missing:
		return False, u"no alarm definition on: %s" % u", ".join(missing)
	total = sum(len(_alarmsOn(p)) for p in ALARM_TAGS)
	# Without part links the CAD page's alarm panel stays empty with no error.
	want = MachineDemo.tagdata.CAD_PARTS
	linked = _cadLinks()
	unlinked = [n for n in sorted(want) if linked.get(n) != want[n]]
	if unlinked:
		return False, (u"not linked to a CAD part (%s): %s"
		               % (MachineDemo.tagdata.CAD_PART, u", ".join(unlinked)))
	return True, (u"%d alarm definitions on %d tags, %d linked to CAD parts"
	              % (total, len(ALARM_TAGS), len(linked)))


def _cadLinks():
	"""alarm name -> CadPart, for every alarm on ALARM_TAGS that carries one."""
	from java.lang import Throwable as JThrowable
	key = MachineDemo.tagdata.CAD_PART
	out = {}
	for path in ALARM_TAGS:
		try:
			cfg = system.tag.getConfiguration(P.tag(path), False)
		except (JThrowable, Exception):
			continue
		for node in cfg:
			for a in (node.get("alarms") or []):
				try:
					part = a.get(key)
					if part:
						out[unicode(a.get("name"))] = unicode(part)
				except:
					pass
	return out


def _databaseCheck():
	"""(ok, detail): the connection exists and answers SELECT 1; green "not applicable" without SQL Bridge."""
	if not _hasDatabaseModule():
		return True, (u"not applicable on this edition - no SQL Bridge "
		              u"module, so no database connection is possible here. "
		              u"The alarm journal below uses Edge's own local "
		              u"profile instead.")
	if _resource("database-connection", DB) is None:
		have = _names("database-connection")
		return False, (u"connection '%s' does not exist. This gateway has: %s"
		               % (DB, u", ".join(have) if have else u"(none)"))
	from java.lang import Throwable as JThrowable
	try:
		system.db.runScalarQuery("SELECT 1", DB)
	except (JThrowable, Exception):
		return False, (u"connection '%s' exists but did not answer 'SELECT 1'"
		               % DB)
	return True, u"'%s' answering - SQLite at %s" % (DB, DB_URL)


def _databaseFix():
	"""Upsert the SQLite connection and wait for it to answer; a reported no-op without SQL Bridge."""
	if not _hasDatabaseModule():
		return (u"skipped - this edition has no SQL Bridge module, so no "
		        u"database connection is possible; nothing to create")
	if _resource("database-connection", DB) is None:
		have = _names("database-driver")
		if "SQLite" not in have:
			raise Exception(
				u"this gateway has no 'SQLite' JDBC driver (it has: %s). "
				u"SQLite ships with Ignition, so a gateway without it has had "
				u"it removed." % (u", ".join(have) if have else u"none"))
	what = _upsert("database-connection", DB, DB_CONFIG,
	               "Machine HMI Demo's own database - a SQLite file beside "
	               "the gateway, holding this demo's alarm journal and "
	               "nothing else")

	# The pool opens some seconds after the resource is created.
	from java.lang import Thread as JThread
	for _attempt in range(15):
		ok, _detail = _databaseCheck()
		if ok:
			return u"connection '%s' %s at %s" % (DB, what, DB_URL)
		JThread.sleep(1000)
	return (u"connection '%s' %s but is not answering yet - check the row "
	        u"below in a moment" % (DB, what))


def _journalCheck():
	"""(ok, detail): the journal profile is the right type for this edition and the name tag matches."""
	# A profile pointed at the wrong datasource raises nothing; the history is just wrong.
	if _isEdgeGateway():
		if not _names("alarm-journal"):
			return False, u"this Edge gateway has no alarm journal at all"
		ok, why = _journalTagCheck()
		if not ok:
			return False, why
		return True, (u"'%s' is Edge's own journal - Edge keeps exactly one "
		              u"and will not accept a second, so this demo uses it "
		              u"rather than creating its own, and %s carries the name"
		              % (journalName(), JOURNAL_NAME_TAG))

	res = _resource("alarm-journal", JOURNAL)
	if res is None:
		have = _names("alarm-journal")
		return False, (u"alarm journal profile '%s' does not exist. This "
		               u"gateway has: %s"
		               % (JOURNAL, u", ".join(have) if have else u"(none)"))
	from java.lang import Throwable as JThrowable
	try:
		cfg = _config(res)
		flavour = cfg["profile"]["type"]
	except (JThrowable, Exception):
		flavour = None

	if not _hasDatabaseModule():
		if flavour != u"LOCAL":
			return False, (u"profile '%s' is a '%s' journal, not the LOCAL "
			               u"one this edition needs - no database is "
			               u"available to a 'DATASOURCE' profile here"
			               % (JOURNAL, flavour))
		return True, (u"profile '%s' is Edge's own LOCAL journal - no "
		              u"database, alarms still journalled internally"
		              % JOURNAL)

	if flavour != u"DATASOURCE":
		return False, (u"profile '%s' is a '%s' journal, not 'DATASOURCE' - "
		               u"this gateway can have a database and should be "
		               u"using it" % (JOURNAL, flavour))
	try:
		ds = cfg["settings"]["datasource"]
	except (JThrowable, Exception):
		ds = None
	if ds != DB:
		return False, (u"profile '%s' writes to '%s', not this demo's '%s'"
		               % (JOURNAL, ds, DB))
	ok, why = _journalTagCheck()
	if not ok:
		return False, why
	return True, u"profile '%s' writes %s on '%s'" % (JOURNAL, JOURNAL_TABLE,
	                                                  DB)


def _journalTagCheck():
	"""(ok, detail): JOURNAL_NAME_TAG, which the Alarms screen's journal table binds to, equals journalName()."""
	want = journalName()
	qv = system.tag.readBlocking(["[%s]%s" % (PROVIDER, JOURNAL_NAME_TAG)])[0]
	have = unicode(qv.value) if qv.quality.isGood() else None
	if have != want:
		return False, (u"%s reads '%s', not '%s' - the Alarms screen binds "
		               u"its journal table to it" % (JOURNAL_NAME_TAG,
		                                             have, want))
	return True, u""


def _journalFix():
	"""Write the journal-name tag and upsert the journal profile (DATASOURCE or LOCAL); none on Edge."""
	_journalTagFix()
	if _isEdgeGateway():
		# Edge refuses to create an alarm journal (UnsupportedOperationException).
		return u"alarm journal '%s' is Edge's own and already exists - " \
		       u"nothing created, %s written" % (journalName(),
		                                         JOURNAL_NAME_TAG)
	if not _hasDatabaseModule():
		what = _upsert("alarm-journal", JOURNAL, JOURNAL_CONFIG_LOCAL,
		               "Machine HMI Demo's own alarm journal - this edition "
		               "has no database, so this is Edge's own LOCAL "
		               "profile: alarms are still journalled, internally, "
		               "with no datasource anywhere")
		return u"alarm journal profile '%s' %s as a LOCAL (no-database) " \
		       u"journal" % (JOURNAL, what)
	what = _upsert("alarm-journal", JOURNAL, JOURNAL_CONFIG,
	               "Machine HMI Demo's own alarm journal - writes the standard "
	               "alarm_events / alarm_event_data tables into this demo's "
	               "own connection, sharing them with nothing")
	return u"alarm journal profile '%s' %s, pointed at '%s'" % (JOURNAL, what,
	                                                            DB)


def _journalTagFix():
	system.tag.writeBlocking(["[%s]%s" % (PROVIDER, JOURNAL_NAME_TAG)],
	                         [journalName()])


def _simCheck():
	"""(ok, detail): the sim is enabled and the robot and air-pressure tags change over 1.4 s."""
	# A tick counter in MachineDemo.sim is not visible unless both share a script manager.
	from java.lang import Thread as JThread
	v = P.readDict({"enabled": "Line/SimEnabled", "speed": "Line/SimSpeed",
	                "state": "Robot/State"})
	if v.get("enabled") is None:
		return False, u"the simulation tags are not readable - write the tags first"
	if not v.get("enabled"):
		return False, u"the simulation is switched off (Line/SimEnabled)"

	probe = ["Robot/J1_deg", "Robot/J2_deg", "Robot/Lift_mm",
	         "Robot/Vacuum_kPa", "Safety/AirPressure_kPa"]
	before = P.read(probe)
	JThread.sleep(1400)
	after = P.read(probe)
	if before == after:
		return False, (u"the simulation is enabled but nothing moved in 1.4 s "
		               u"- check the CellSim gateway timer script is enabled, "
		               u"and that the robot is not held or faulted")
	return True, u"running at %sx, robot %s" % (
		v.get("speed"), v.get("state") or u"?")


def _simFix():
	mapping = {"Line/SimEnabled": True, "Line/SimSpeed": 1.0,
	           "Line/Mode": "Auto", "Safety/GuardsClosed": True,
	           "Robot/JogUp": False, "Robot/JogDown": False}
	for n in P.FAULTS:
		mapping["Faults/%s" % n] = False
	P.write(mapping)
	MachineDemo.sim.clearInternals()
	return u"simulation enabled at 1x with every fault cleared"


def _items():
	"""Setup items in install order: (key, title, check, fix, why)."""
	c = MachineDemo.tagdata.counts()
	return [
		("tagProvider", "Tag provider", _providerCheck, _providerFix,
		 "A standard provider named %s, created live through system.config - "
		 "no file to place and no config scan to remember." % PROVIDER),
		("tags", "Cell tags", _tagsCheck, _tagsFix,
		 "%d tags across the machine's geometry, the line, the safety "
		 "circuit, the robot, both pallet stations, the conveyors, eight line "
		 "zones and five injectable faults - written into the provider from "
		 "the copy the project carries, %d UDT definition(s) first."
		 % (c["tags"], c["udts"])),
		("udt", "Robot UDT", _udtCheck, _tagsFix,
		 "The robot is an instance of the '%s' type under [%s]_types_, not a "
		 "folder of %d loose tags - so a second arm is a second instance and "
		 "the alarm on Robot/Fault is defined once. Every member path is "
		 "unchanged: a gateway set up before this row existed is converted in "
		 "place, without a restart."
		 % (MachineDemo.tagdata.ROBOT_TYPE, PROVIDER,
		    len(MachineDemo.tagdata._robotMembers()))),
		("config", "Machine geometry", _configCheck, _tagsFix,
		 "%d tags under [%s]Config holding the case, the pallet, the conveyor "
		 "and where the two build stations sit. The 3D page and the screens "
		 "read them, so the next machine is a handful of tag values rather "
		 "than a source edit." % (len(_configPaths()), PROVIDER)),
		("alarms", "Alarm definitions", _alarmsCheck, _tagsFix,
		 "%d alarms on the fault tags, the safety booleans and the robot. "
		 "They travel with the tags; this row is separate because a tree that "
		 "wrote its values and dropped its alarms looks perfect and raises "
		 "nothing. The robot's is defined on the UDT and inherited by the "
		 "instance, which is why it still reads at Robot/Fault."
		 % c["alarms"]),
		("database", "Database connection", _databaseCheck, _databaseFix,
		 "This demo's own connection, named %s - SQLite, so it is a file "
		 "beside the gateway with no server to reach, no credential and no "
		 "config scan. It exists so the alarm journal below has somewhere of "
		 "its own to write. On an edition with no SQL Bridge module (Edge "
		 "Panel - the reason this demo exists) this row is not applicable: "
		 "no connection is attempted, and it still reports green." % DB),
		("journal", "Alarm journal", _journalCheck, _journalFix,
		 "A journal profile named %s, sharing its history with nothing. On "
		 "this gateway it writes %s into %s; filtering a shared journal by "
		 "source only looks like isolation - the rows still interleave with "
		 "every other project's, and the retention belongs to someone else. "
		 "On an edition with no database (Edge Panel) this is instead a "
		 "LOCAL profile - Edge's own internal journal, alarms still kept, "
		 "no datasource anywhere."
		 % (JOURNAL, JOURNAL_TABLE, DB)),
		("simulation", "Cell simulation", _simCheck, _simFix,
		 "The palletiser actually running a pattern - pick, traverse, place, "
		 "retract - at real machine speed. It is what makes every screen and "
		 "the 3D cell live."),
	]


def items():
	"""Setup items in install order as (key, title, checkFn, fixFn, why) tuples."""
	return _items()


FIXABLE = ["tagProvider", "tags", "udt", "config", "alarms", "database",
           "journal", "simulation"]


def check():
	"""Report every setup item's state, each checked independently; changes nothing.

	Returns: {items: [{key, title, ok, detail, fixable, why}], ok, version, provider, cell, counts}.
	"""
	rows = []
	for key, title, checkFn, fixFn, why in _items():
		try:
			ok, detail = checkFn()
		except:
			import traceback
			ok = False
			detail = traceback.format_exc().strip().split("\n")[-1]
			LOG.warn("check %s failed: %s" % (key, traceback.format_exc()))
		rows.append({"key": key, "title": title, "ok": bool(ok),
		             "detail": detail, "fixable": fixFn is not None,
		             "why": why})
	c = MachineDemo.tagdata.counts()
	return {"items": rows,
	        "ok": all(r["ok"] for r in rows),
	        "version": P.VERSION,
	        "provider": PROVIDER,
	        "cell": u"%s - %s" % (P.CELL_OWNER, P.CELL_NAME),
	        "counts": c}


def fix(key):
	"""Run one item's fix; return a one-line account, or raise."""
	for k, _title, _checkFn, fixFn, _why in _items():
		if k != key:
			continue
		if fixFn is None:
			raise ValueError("%s cannot be created from the project" % key)
		return fixFn()
	raise ValueError("no such setup item: %s (try one of %s)"
	                 % (key, ", ".join(FIXABLE)))


def run():
	"""Fix every failing item in install order, carrying on past failures; return check() plus changed/errors."""
	done, failed = [], []
	for key, _title, checkFn, fixFn, _why in _items():
		if fixFn is None:
			continue
		try:
			ok, _detail = checkFn()
		except:
			ok = False
		if ok:
			continue
		try:
			said = fix(key)
			if said not in done:
				done.append(said)
		except:
			import traceback
			failed.append("%s: %s"
			              % (key,
			                 traceback.format_exc().strip().split("\n")[-1]))
			LOG.warn("setup step %s failed: %s"
			         % (key, traceback.format_exc()))

	state = check()
	state["changed"] = done
	if failed:
		state["errors"] = failed
	LOG.info("setup run: %d changed, %d failed, ok=%s"
	         % (len(done), len(failed), state["ok"]))
	return state
