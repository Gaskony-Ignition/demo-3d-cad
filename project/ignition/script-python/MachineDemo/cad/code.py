"""
CAD models for the CAD page: the built-in one in the `cad` WebDev resource and
uploads under <data dir>/machine-demo-cad/<model>/ (layout: docs/CAD-VIEWER.md).
Writes come from the Perspective session; the `cad` route writes only STEP part names.
"""

import os
import re
import shutil
from java.lang import Throwable as JThrowable

LOG = system.util.getLogger("MachineDemo.cad")

FOLDER = "machine-demo-cad"
# safeName strips a leading _, so no upload can take this name
BUILTIN = "_builtin"
BUILTIN_LABEL = "UR5 sample (built-in)"

MAX_UPLOAD = 50 * 1024 * 1024
# Limit on unzipped size: a few KB of zip can inflate to gigabytes.
MAX_UNZIPPED = 200 * 1024 * 1024
MAX_PARTS = 500
NAME_MAX = 48

STEP_FILE = "model.step"
META = "meta.json"
PARTS_FILE = "parts.json"


def root():
	"""<data dir>/machine-demo-cad, created on first use."""
	try:
		from com.inductiveautomation.ignition.gateway import IgnitionGateway
		data = IgnitionGateway.get().getSystemManager().getDataDir().getAbsolutePath()
	except (JThrowable, Exception):
		from java.lang import System
		data = os.path.join(System.getProperty("user.dir"), "data")
	d = os.path.join(unicode(data), FOLDER)
	if not os.path.isdir(d):
		os.makedirs(d)
	return d


def safeName(text):
	"""text as one path segment of letters, digits, - and _ (no extension, no leading dot)."""
	base = unicode(text or u"")
	base = re.split(r"[\\/]", base)[-1]
	stem, ext = os.path.splitext(base)
	if ext.lower() in (".stl", ".zip", ".step", ".stp"):
		base = stem
	base = re.sub(r"[^A-Za-z0-9_-]+", "_", base)
	base = re.sub(r"_+", "_", base).strip("_-")
	return base[:NAME_MAX]


def _modelDir(name, mustExist=True):
	if not name or safeName(name) != name:
		raise ValueError("not a valid model name: %r" % name)
	r = root()
	d = os.path.join(r, name)
	# belt and braces: safeName already allows one segment only
	if os.path.dirname(os.path.realpath(d)) != os.path.realpath(r):
		raise ValueError("model path escapes the CAD folder")
	if mustExist and not os.path.isdir(d):
		raise ValueError("no such model: %s" % name)
	return d


def _readMeta(d):
	try:
		return system.util.jsonDecode(system.file.readFileAsString(
			os.path.join(d, META), "UTF-8")) or {}
	except:
		return {}


def models():
	"""Every uploaded model, newest first."""
	out = []
	r = root()
	for name in os.listdir(r):
		d = os.path.join(r, name)
		if not os.path.isdir(d) or safeName(name) != name:
			continue
		files = os.listdir(d)
		meta = _readMeta(d)
		if STEP_FILE in files:
			kind = "step"
			parts = meta.get("parts")
		else:
			kind = "stl"
			parts = len([f for f in files if f.lower().endswith(".stl")])
		out.append({"name": name, "kind": kind, "parts": parts,
		            "source": meta.get("source", u""),
		            "uploaded": meta.get("uploaded", u""),
		            "mtime": os.path.getmtime(d)})
	out.sort(key=lambda m: -m["mtime"])
	return out


def options(rev=None):
	"""Dropdown options for the CAD page. `rev` only forces a re-evaluation."""
	opts = [{"value": BUILTIN, "label": BUILTIN_LABEL}]
	for m in models():
		opts.append({"value": m["name"],
		             "label": u"%s  (%s)" % (m["name"], m["kind"].upper())})
	return opts


def uploadedOptions(rev=None):
	"""Dropdown options for uploaded models only, without the built-in one."""
	return [o for o in options(rev) if o["value"] != BUILTIN]


def builtinDir():
	"""The project's own `cad` WebDev resource folder, or None."""
	from java.lang import System
	rel = os.path.join("data", "projects", system.util.getProjectName(),
	                   "com.inductiveautomation.webdev", "resources", "cad")
	roots = []
	for prop in ("user.dir", "ignition.installdir", "catalina.base"):
		v = System.getProperty(prop)
		if v:
			roots.append(v)
			roots.append(os.path.join(v, ".."))
	roots.append("/usr/local/bin/ignition")
	for r in roots:
		p = os.path.normpath(os.path.join(r, rel))
		if os.path.isdir(p):
			return p
	return None


def parts(name):
	"""Part names of a model; for STEP, what the page last reported (empty until first shown)."""
	if not name or name == BUILTIN:
		d = builtinDir()
		return sorted([f[:-4] for f in os.listdir(d) if f.lower().endswith(".stl")]) if d else []
	kind, stems = files(name)
	if kind == "stl":
		return stems
	try:
		return list(system.util.jsonDecode(system.file.readFileAsString(
			os.path.join(_modelDir(name), PARTS_FILE), "UTF-8")) or [])
	except:
		return []


def partOptions(name, rev=None):
	"""Dropdown options for the parts of one model."""
	return [{"value": p, "label": p} for p in parts(name)]


def saveParts(name, names):
	"""Store the part names the page parsed from a STEP model; return how many were kept."""
	kind, _stems = files(name)
	if kind != "step":
		raise ValueError("part names are only recorded for STEP models")
	if not isinstance(names, (list, tuple)) or len(names) > MAX_PARTS * 4:
		raise ValueError("expected a list of at most %d names" % (MAX_PARTS * 4))
	clean, seen = [], set()
	for n in names:
		n = re.sub(u"[\x00-\x1f\x7f]", u"", unicode(n or u"")).strip()[:128]
		if n and n.lower() not in seen:
			seen.add(n.lower())
			clean.append(n)
	path = os.path.join(_modelDir(name), PARTS_FILE)
	text = system.util.jsonEncode(clean)
	if os.path.isfile(path) and system.file.readFileAsString(path, "UTF-8") == text:
		return len(clean)
	system.file.writeFile(path, text)
	return len(clean)


def files(name):
	"""(kind, [file stems]) of one uploaded model, for the cad route."""
	d = _modelDir(name)
	fs = os.listdir(d)
	if STEP_FILE in fs:
		return "step", [STEP_FILE[:-5]]
	return "stl", sorted([f[:-4] for f in fs if f.lower().endswith(".stl")])


def filePath(name, stem):
	"""Path of one file of an uploaded model, or None. Never leaves the folder."""
	d = _modelDir(name)
	for f in os.listdir(d):
		low = f.lower()
		if (low.endswith(".stl") or low == STEP_FILE) and \
				os.path.splitext(f)[0] == stem:
			return os.path.join(d, f)
	return None


def _isBinarySTL(data):
	"""84-byte header + 50 bytes a triangle, exactly. Everything else is not."""
	n = len(data)
	if n < 84:
		return False
	from java.nio import ByteBuffer, ByteOrder
	count = ByteBuffer.wrap(data, 80, 4).order(ByteOrder.LITTLE_ENDIAN).getInt() & 0xFFFFFFFF
	return 84 + count * 50 == n


def _isStep(data):
	from java.lang import String as JString
	head = unicode(JString(data, 0, min(len(data), 200), "ISO-8859-1")).lstrip()
	return head.startswith(u"ISO-10303-21")


def _write(path, data):
	from java.io import FileOutputStream
	out = FileOutputStream(path)
	try:
		out.write(data)
	finally:
		out.close()


def _unzipSTLs(data):
	"""[(part name, bytes)] from a zip of STLs, named by safeName(basename) so no entry path is used."""
	from java.io import ByteArrayInputStream, ByteArrayOutputStream
	from java.util.zip import ZipInputStream
	from jarray import zeros
	zin = ZipInputStream(ByteArrayInputStream(data))
	parts, seen, total = [], set(), 0
	buf = zeros(65536, "b")
	try:
		while True:
			e = zin.getNextEntry()
			if e is None:
				break
			ename = unicode(e.getName())
			base = re.split(r"[\\/]", ename)[-1]
			if e.isDirectory() or not base.lower().endswith(".stl") \
					or ename.startswith("__MACOSX") or base.startswith("."):
				continue
			bout = ByteArrayOutputStream()
			while True:
				n = zin.read(buf)
				if n < 0:
					break
				total += n
				if total > MAX_UNZIPPED:
					raise ValueError("the zip unpacks to more than %d MB"
					                 % (MAX_UNZIPPED // (1024 * 1024)))
				bout.write(buf, 0, n)
			body = bout.toByteArray()
			if not _isBinarySTL(body):
				raise ValueError("%s is not a binary STL (ASCII STL is not read)"
				                 % base)
			name = safeName(base) or "part"
			stem, i = name, 2
			while name.lower() in seen:
				name = "%s_%d" % (stem, i)
				i += 1
			seen.add(name.lower())
			parts.append((name, body))
			if len(parts) > MAX_PARTS:
				raise ValueError("more than %d STL files in the zip" % MAX_PARTS)
	finally:
		zin.close()
	if not parts:
		raise ValueError("no .stl files in the zip")
	return parts


def save(filename, data, name=None):
	"""Store an upload as a model, replacing any of the same name; return name, kind, parts, replaced."""
	# Written to a temporary folder and swapped in, so a failed upload leaves nothing.
	size = len(data)
	if size == 0:
		raise ValueError("the file is empty")
	if size > MAX_UPLOAD:
		raise ValueError("the file is %.1f MB; the limit is %d MB"
		                 % (size / 1048576.0, MAX_UPLOAD // 1048576))
	ext = os.path.splitext(unicode(filename or u""))[1].lower()
	model = safeName(name) or safeName(filename)
	if not model:
		raise ValueError("give the model a name")

	if ext == ".stl":
		if not _isBinarySTL(data):
			raise ValueError("not a binary STL (ASCII STL is not read)")
		kind, items = "stl", [(model, data)]
	elif ext == ".zip":
		kind, items = "stl", _unzipSTLs(data)
	elif ext in (".step", ".stp"):
		if not _isStep(data):
			raise ValueError("not a STEP file (no ISO-10303-21 header)")
		kind, items = "step", [(STEP_FILE[:-5], data)]
	else:
		raise ValueError("only .stl, .zip of .stl, .step and .stp are accepted")

	r = root()
	final = _modelDir(model, mustExist=False)
	tmp = os.path.join(r, ".upload-%s" % model)
	if os.path.isdir(tmp):
		shutil.rmtree(tmp)
	os.makedirs(tmp)
	try:
		for stem, body in items:
			_write(os.path.join(tmp, stem + (".step" if kind == "step" else ".stl")),
			       body)
		meta = {"kind": kind, "source": unicode(filename),
		        "bytes": size,
		        "parts": len(items) if kind == "stl" else None,
		        "uploaded": system.date.format(system.date.now(),
		                                       "yyyy-MM-dd HH:mm:ss")}
		system.file.writeFile(os.path.join(tmp, META),
		                      system.util.jsonEncode(meta))
		replaced = os.path.isdir(final)
		if replaced:
			shutil.rmtree(final)
		os.rename(tmp, final)
	except:
		if os.path.isdir(tmp):
			shutil.rmtree(tmp)
		raise
	LOG.info("CAD model %s %s from %s (%s, %d part file(s))"
	         % (model, "replaced" if replaced else "stored", filename, kind,
	            len(items)))
	return {"name": model, "kind": kind, "parts": len(items),
	        "replaced": replaced}


def delete(name):
	"""Remove one uploaded model. The built-in model is not deletable here."""
	if name == BUILTIN:
		raise ValueError("the built-in model is part of the project")
	d = _modelDir(name)
	shutil.rmtree(d)
	LOG.info("CAD model %s deleted" % name)
	return True


def alarms():
	"""Standing alarms on this demo's provider that name a CAD part; active, then unacked, then newest first."""
	key = MachineDemo.tagdata.CAD_PART
	try:
		events = system.alarm.queryStatus(
			source=["prov:%s:/tag:*" % MachineDemo.plant.PROVIDER])
	except (JThrowable, Exception):
		import traceback
		LOG.warn("queryStatus failed: %s" % traceback.format_exc())
		return []
	out = []
	for e in events:
		try:
			part = e.get(key)
		except:
			part = None
		if not part:
			continue
		f = MachineDemo.plant._field
		state = f(e, lambda x: unicode(x.getState()), u"")
		out.append({
			"part": unicode(part),
			"name": f(e, lambda x: unicode(x.getName()), u"Alarm"),
			"label": f(e, lambda x: unicode(x.get("displayPath") or u""), u""),
			"priority": f(e, lambda x: unicode(x.getPriority()), u""),
			"state": state,
			"active": state.lower().startswith("active"),
			"acked": f(e, lambda x: bool(x.isAcked()), True),
			"time": f(e, lambda x: system.date.format(
				x.get("eventTime"), "HH:mm:ss"), u""),
			"ts": f(e, lambda x: x.get("eventTime").getTime(), 0),
		})
	out.sort(key=lambda a: (not a["active"], a["acked"], -a["ts"]))
	return out


def _slot(i, leaf):
	return "CadSim/Sim%d/%s" % (i, leaf)


def _slotRange():
	return range(1, MachineDemo.tagdata.CAD_SIM_SLOTS + 1)


def simSlots(rev=None):
	"""Each slot: what it is set to and where its alarm stands."""
	P = MachineDemo.plant
	vals = P.read([_slot(i, leaf) for i in _slotRange()
	               for leaf in ("Part", "Priority", "Active")])
	acked = {}
	try:
		for e in system.alarm.queryStatus(
				source=["prov:%s:/tag:CadSim/*" % P.PROVIDER],
				state=["ActiveUnacked", "ActiveAcked"]):
			m = re.search(r"CadSim/Sim(\d+)/", unicode(e.getSource()))
			if m:
				acked[int(m.group(1))] = bool(e.isAcked())
	except (JThrowable, Exception):
		pass
	names = MachineDemo.tagdata.PRIORITIES
	out = []
	for k, i in enumerate(_slotRange()):
		part, pri, active = vals[k * 3], vals[k * 3 + 1], bool(vals[k * 3 + 2])
		pri = names[pri] if isinstance(pri, int) and 0 <= pri < len(names) else u""
		if active:
			text = u"Slot %d  -  %s  -  %s  -  %s" % (
				i, part, pri, u"acknowledged" if acked.get(i) else u"unacknowledged")
		else:
			text = u"Slot %d  -  free" % i
		out.append({"slot": i, "part": part or u"", "priority": pri,
		            "active": active, "acked": bool(acked.get(i)), "text": text})
	return out


def simRaise(part, priority="High"):
	"""Raise a simulated alarm on a part, reusing its slot if it has one; return the slot."""
	from java.lang import Thread as JThread
	P = MachineDemo.plant
	part = unicode(part or u"").strip()[:128]
	if not part:
		raise ValueError("choose a part")
	names = MachineDemo.tagdata.PRIORITIES
	if priority not in names:
		raise ValueError("priority must be one of %s" % ", ".join(names))
	slots = simSlots()
	slot = None
	for s in slots:
		if s["active"] and s["part"].lower() == part.lower():
			slot = s["slot"]
	if slot is None:
		free = [s["slot"] for s in slots if not s["active"]]
		if not free:
			raise ValueError("all %d simulation slots are in use - clear one first"
			                 % len(slots))
		slot = free[0]
	P.write({_slot(slot, "Active"): False})
	# Part and Priority have to be in place before Active goes true: the alarm
	# reads its bound properties once, at activation.
	P.write({_slot(slot, "Part"): part, _slot(slot, "Priority"): names.index(priority)})
	JThread.sleep(300)
	P.write({_slot(slot, "Active"): True})
	LOG.info("simulated %s alarm on part %s (slot %d)" % (priority, part, slot))
	return slot


def simClear(slot=None):
	"""Clear one slot's alarm, or every slot's."""
	MachineDemo.plant.write(dict((_slot(i, "Active"), False) for i in _slotRange()
	                             if slot is None or i == int(slot)))


def simAck(slot=None, user="CAD screen"):
	"""Acknowledge one slot's standing alarm, or every slot's."""
	P = MachineDemo.plant
	src = "prov:%s:/tag:CadSim/%s*" % (P.PROVIDER, "Sim%d/" % int(slot) if slot else "")
	ids = [str(e.getId()) for e in system.alarm.queryStatus(
		source=[src], state=["ActiveUnacked", "ClearUnacked"])]
	if ids:
		system.alarm.acknowledge(ids, "acknowledged on the CAD screen", user)
	return len(ids)
