"""
Event handlers and script transforms for the Machine views, called from one-line view scripts.
"""

from java.lang import Throwable


def _isDict(v):
	"""True if v has keys()."""
	try:
		v.keys()
		return True
	except Throwable:
		return False
	except:
		return False


def _isList(v):
	"""True if v is a sized iterable that is neither a dict nor a string."""
	if _isDict(v) or isinstance(v, basestring):
		return False
	try:
		len(v)
		iter(v)
		return True
	except:
		return False


def _led(ok):
	"""Lamp state for an ok value: na, ok or bad."""
	if ok is None:
		return "na"
	if ok:
		return "ok"
	return "bad"


def _pick(it, keys):
	"""The first of keys that holds a non-empty value in it, or None."""
	for k in keys:
		v = it.get(k)
		if v is not None and str(v) != "":
			return v
	return None


def _one(it):
	"""One console row from a result item."""
	if _isDict(it):
		nm = _pick(it, ("title", "name", "item", "step", "label", "key"))
		ok = _pick(it, ("ok", "present", "done", "installed", "healthy"))
		st = _pick(it, ("detail", "state", "status", "message", "value"))
		if st is None:
			if ok is None:
				st = ""
			elif ok:
				st = "OK"
			else:
				st = "MISSING"
		if nm is None:
			nm = ""
		return {"name": str(nm), "state": str(st), "led": _led(ok)}
	return {"name": str(it), "state": "", "led": "na"}


def _findList(d, depth):
	"""The first list in d, searched to four levels."""
	if depth > 4:
		return None
	if _isList(d):
		return d
	if not _isDict(d):
		return None
	for k in ("items", "checks", "rows", "results", "steps"):
		if _isList(d.get(k)):
			return d.get(k)
	for k in d.keys():
		r = _findList(d.get(k), depth + 1)
		if r is not None:
			return r
	return None


def _flatten(d):
	"""One console row per leaf of a nested dict, keys sorted."""
	rows = []
	if not _isDict(d):
		return rows
	keys = [str(k) for k in d.keys()]
	keys.sort()
	for k in keys:
		v = d.get(k)
		if _isDict(v):
			rows.extend(_flatten(v))
		elif _isList(v):
			rows.append({"name": k, "state": "%d entries" % len(v), "led": "na"})
		else:
			txt = str(v)
			ok = None
			if v is True or txt.lower() in ("ok", "true", "yes", "ready", "installed"):
				ok = True
			elif v is False or txt.lower() in ("false", "no", "missing", "error", "failed"):
				ok = False
			rows.append({"name": k, "state": txt, "led": _led(ok)})
	return rows


def _rowify(d):
	"""Console rows from a result: its first list if it has one, else its leaves."""
	lst = _findList(d, 0)
	if lst:
		return [_one(it) for it in lst]
	return _flatten(d)


def consoleResult(key, call, rows=6, noteOverflow=False):
	"""Run a Setup console command in-process; return the {msg, raw, rows} its panel shows, padded to rows."""
	out = {"msg": "", "raw": "", "rows": []}
	try:
		# The JSON round trip hands _rowify() the same object the HTTP route returns.
		data = system.util.jsonDecode(system.util.jsonEncode({"ok": True, key: call()}))
		out["msg"] = "%s -> OK" % key
		if data is None:
			out["raw"] = ""
		else:
			try:
				out["raw"] = system.util.jsonEncode(data, 1)[:1400]
			except:
				out["raw"] = str(data)[:1400]
			out["rows"] = _rowify(data)
	except Throwable as e:
		out["msg"] = "%s -> FAILED" % key
		out["raw"] = str(e)[:1400]
	except Exception as e:
		out["msg"] = "%s -> FAILED" % key
		out["raw"] = str(e)[:1400]
	# The view has a fixed number of rows; one bound past the list shows a "null" error box.
	lst = out["rows"]
	extra = len(lst) - rows
	while len(lst) < rows:
		lst.append({"name": "", "state": "", "led": "blank"})
	if noteOverflow and extra > 0:
		out["msg"] = "%s (+%d not shown)" % (out["msg"], extra)
	out["rows"] = lst[:rows]
	return out


def setSimSpeed(speed):
	"""Write Line/SimSpeed as given; errors are ignored."""
	# api.setSpeed clamps to 10, so the direct write is what lets 20x and 60x through.
	try:
		MachineDemo.api.setSpeed(speed)
	except Throwable:
		pass
	except:
		pass
	try:
		system.tag.writeBlocking(["[MachineDemo]Line/SimSpeed"], [float(speed)])
	except Throwable:
		pass


def trySetFault(name, on):
	"""Inject or clear one fault; errors are ignored."""
	try:
		MachineDemo.api.setFault(name, on)
	except Throwable:
		pass
	except:
		pass


def clearAllFaults():
	"""Clear every injected fault and the robot's fault bit and text; errors are ignored."""
	for name in ("WrapperFilmFeed", "ConveyorJam", "VacuumLow", "GuardOpen", "RobotAxisFault"):
		trySetFault(name, False)
	try:
		system.tag.writeBlocking(["[MachineDemo]Robot/Fault", "[MachineDemo]Robot/FaultText"], [False, ""])
	except Throwable:
		pass


def _holdTarget(view):
	"""Set the Manual view's lift target to the lift's current position."""
	try:
		cur = float(system.tag.readBlocking(["[MachineDemo]Robot/Lift_mm"])[0].value)
		view.custom.liftTarget = cur
	except Throwable:
		pass


def _releaseJog():
	"""Clear both jog bits."""
	try:
		system.tag.writeBlocking(["[MachineDemo]Robot/JogUp", "[MachineDemo]Robot/JogDown"], [False, False])
	except Throwable:
		pass


def manualStartup(view):
	"""Start the Manual view with the lift target at the current position and no motion."""
	_holdTarget(view)
	view.custom.jog = 0
	view.custom.seek = False


def stopMotion(view):
	"""Stop jog and seek, hold the lift where it is and clear both jog bits."""
	view.custom.jog = 0
	view.custom.seek = False
	_holdTarget(view)
	_releaseJog()


def jogStart(view, direction):
	"""Start a hold-to-run jog: direction 1 is up, -1 is down."""
	view.custom.seek = False
	view.custom.jog = direction
	try:
		system.tag.writeBlocking(["[MachineDemo]Robot/Jog%s" % ("Up" if direction > 0 else "Down")], [True])
	except Throwable:
		pass


def jogStop(view):
	"""End a hold-to-run jog and clear both jog bits."""
	view.custom.jog = 0
	_releaseJog()


def homeLift(view):
	"""Seek the lift to 0 mm and set Robot/Homed."""
	view.custom.seek = True
	view.custom.jog = 0
	view.custom.liftTarget = 0.0
	try:
		system.tag.writeBlocking(["[MachineDemo]Robot/Homed"], [True])
	except Throwable:
		pass


def liftStep(view):
	"""Move the lift one tick of the Manual view's jog or seek (16 or 26 mm, within 0..1200); return ""."""
	try:
		j = int(view.custom.jog)
	except Throwable:
		j = 0
	try:
		cur = float(system.tag.readBlocking(["[MachineDemo]Robot/Lift_mm"])[0].value)
	except Throwable:
		return ""
	try:
		tgt = float(view.custom.liftTarget)
	except Throwable:
		tgt = cur
	nxt = cur
	if j != 0:
		nxt = cur + (j * 16.0)
		if nxt < 0.0:
			nxt = 0.0
		if nxt > 1200.0:
			nxt = 1200.0
		view.custom.liftTarget = nxt
	elif view.custom.seek:
		d = tgt - cur
		if abs(d) <= 26.0:
			nxt = tgt
			view.custom.seek = False
		elif d > 0:
			nxt = cur + 26.0
		else:
			nxt = cur - 26.0
	else:
		return ""
	try:
		system.tag.writeBlocking(["[MachineDemo]Robot/Lift_mm"], [nxt])
	except Throwable:
		pass
	return ""


def alarmMessages():
	"""The Manual view's 20 message rows: standing alarms, else one "Cell healthy" row, padded with blanks."""
	rows = []
	try:
		evts = MachineDemo.plant.liveAlarms()
	except Throwable:
		evts = []
	for a in evts:
		txt = str(a.get("label") or a.get("name") or "Alarm")
		if txt.startswith("Palletiser / "):
			txt = txt[13:]
		if not a.get("acked"):
			txt = txt + "  (unacked)"
		elif not a.get("active"):
			txt = txt + "  (cleared)"
		rows.append({"time": str(a.get("time") or ""), "level": str(a.get("priority") or "").upper(), "text": txt})
	rows = rows[:20]
	if not rows:
		rows.append({"time": system.date.format(system.date.now(), "HH:mm:ss"), "level": "INFO", "text": "Cell healthy - no alarms standing"})
	while len(rows) < 20:
		rows.append({"time": "", "level": "", "text": ""})
	return rows


def alarmTotals():
	"""Standing alarms counted by priority, plus total, active and unacked."""
	out = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Diagnostic": 0, "total": 0, "active": 0, "unacked": 0}
	try:
		rows = MachineDemo.plant.liveAlarms()
	except Throwable:
		return out
	for a in rows:
		pri = str(a.get("priority") or "Low")
		if pri not in out:
			pri = "Low"
		out[pri] = out[pri] + 1
		out["total"] = out["total"] + 1
		if a.get("active"):
			out["active"] = out["active"] + 1
		if not a.get("acked"):
			out["unacked"] = out["unacked"] + 1
	return out


def alarmBanner():
	"""The Overview alarm bar: text, counts and colours for the most urgent standing alarm."""
	out = {"text": "No active alarms on this machine", "sub": "0 alarms - 0 unacknowledged", "colour": "var(--md-ink-quiet, #8b98a3)", "bg": "var(--md-panel, #1d232a)", "border": "var(--md-line, #2c343d)", "time": "", "n": 0, "active": 0}
	try:
		rows = MachineDemo.plant.liveAlarms()
	except Throwable:
		return out
	if not rows:
		return out
	order = {"Diagnostic": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}
	best = None
	bestscore = -1
	bestpri = 0
	unacked = 0
	active = 0
	for a in rows:
		if not a.get("acked"):
			unacked = unacked + 1
		pri = order.get(str(a.get("priority") or "Low"), 1)
		if a.get("active"):
			active = active + 1
			score = 100 + pri * 2
		else:
			score = pri * 2
		if not a.get("acked"):
			score = score + 1
		if score > bestscore:
			bestscore = score
			bestpri = pri
			best = a
	if best is None:
		return out
	lbl = str(best.get("label") or "")
	nm = str(best.get("name") or "Alarm")
	if not lbl:
		lbl = nm
	st = str(best.get("state") or "")
	colour = "var(--md-info, #6cc4e8)"
	bg = "var(--md-panel, #1d232a)"
	border = "var(--md-line, #2c343d)"
	if bestpri >= 3:
		colour = "var(--md-fault-ink, #ff8d92)"
		bg = "var(--md-fault-bg-2, #2e1a1d)"
		border = "var(--md-fault-line, #c2444c)"
	elif bestpri == 2:
		colour = "var(--md-warn, #eebf5e)"
		bg = "var(--md-warn-bg-2, #2b2418)"
		border = "var(--md-warn-line, #7d6427)"
	if not best.get("active"):
		# A cleared alarm is amber until acknowledged, then quiet: it wants attention, not action.
		bg = "var(--md-panel, #1d232a)"
		border = "var(--md-line, #2c343d)"
		if best.get("acked"):
			colour = "var(--md-ink-quiet, #8b98a3)"
		else:
			colour = "var(--md-warn, #eebf5e)"
	out["text"] = lbl + "  -  " + st
	out["sub"] = "%d alarms - %d active - %d unacknowledged" % (len(rows), active, unacked)
	out["colour"] = colour
	out["bg"] = bg
	out["border"] = border
	out["time"] = str(best.get("time") or "")
	out["n"] = len(rows)
	out["active"] = active
	return out


def simCommand(custom, call, *args):
	"""Run a CAD sim-alarm command and report the outcome in the CadSim view's custom props."""
	try:
		call(*args)
	except (Throwable, Exception) as e:
		custom.status = u"Failed: %s" % e
		custom.ok = False
		return
	custom.status = u""
	custom.ok = True
	custom.rev = (custom.rev or 0) + 1


def simRaise(custom):
	"""Raise a simulated alarm on the CadSim view's chosen part and report the slot used."""
	try:
		slot = MachineDemo.cad.simRaise(custom.part, custom.priority)
	except (Throwable, Exception) as e:
		custom.status = u"Not raised: %s" % e
		custom.ok = False
		return
	custom.status = u"%s alarm raised on %s (slot %d)." % (custom.priority, custom.part, slot)
	custom.ok = True
	custom.rev = (custom.rev or 0) + 1


def uploadModel(custom, upload):
	"""Store an uploaded CAD file under the CadModels view's name; return the cadModelChanged payload, or None."""
	name = custom.name
	try:
		r = MachineDemo.cad.save(upload.name, upload.getBytes(), name)
	except (Throwable, Exception) as e:
		custom.status = u"Not stored: %s" % e
		custom.ok = False
		return None
	custom.status = u"%s %s - %s, %d part file(s). It is showing now." % (
		r["name"], "replaced" if r["replaced"] else "stored", r["kind"].upper(), r["parts"])
	custom.ok = True
	custom.rev = (custom.rev or 0) + 1
	custom.name = ""
	return {"model": r["name"]}


def deleteModel(custom):
	"""Delete the chosen uploaded model on the second press; return the cadModelChanged payload, or None."""
	name = custom.delModel
	if not name:
		custom.status = u"Choose an uploaded model to delete."
		custom.ok = False
		return None
	if custom.armed != name:
		custom.armed = name
		return None
	try:
		MachineDemo.cad.delete(name)
	except (Throwable, Exception) as e:
		custom.status = u"Not deleted: %s" % e
		custom.ok = False
		return None
	custom.armed = ""
	custom.status = u"%s deleted." % name
	custom.ok = True
	custom.rev = (custom.rev or 0) + 1
	custom.delModel = None
	return {"deleted": name}


def applyModelChange(custom, payload):
	"""Follow a cadModelChanged message on the CAD page: show the new model, or the built-in one if ours was deleted."""
	custom.rev = (custom.rev or 0) + 1
	if payload.get('deleted') and custom.model == payload['deleted']:
		custom.model = '_builtin'
	elif payload.get('model'):
		custom.model = payload['model']


