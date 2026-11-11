"""
The 3D cell's scene document: the Machine/Scene view's custom props, edited in
the Designer and read here off the view.json on disk for the 3D page.
"""

import os
from java.lang import System

VIEW = "Machine/Scene"

# Top-level rather than nested so a binding reads custom.parts[3].size[0], the
# same path a Perspective component's props would use.
KEYS = ["units", "consts", "data", "materials", "parts"]


def _candidates():
	"""Possible paths to the view.json, from the install-dir system properties and the Docker default."""
	project = system.util.getProjectName()
	rel = os.path.join("data", "projects", project,
	                   "com.inductiveautomation.perspective", "views",
	                   os.path.join(*VIEW.split("/")), "view.json")
	roots = []
	for prop in ("user.dir", "ignition.installdir", "catalina.base"):
		v = System.getProperty(prop)
		if v:
			roots.append(v)
			roots.append(os.path.join(v, ".."))
	roots.append("/usr/local/bin/ignition")
	out = []
	for r in roots:
		p = os.path.normpath(os.path.join(r, rel))
		if p not in out:
			out.append(p)
	return out


# Cached: revision() is polled four times a second.
_resolved = [None]


def revision():
	"""Return "mtime-size" of the Scene view.json, or "" if it is not found; never raises."""
	paths = [_resolved[0]] if _resolved[0] else _candidates()
	for path in paths:
		try:
			st = os.stat(path)
		except Exception:
			continue
		_resolved[0] = path
		return "%d-%d" % (st.st_mtime, st.st_size)
	_resolved[0] = None
	return ""


def document():
	"""Return {"ok": True, "scene": {...}} from the Scene view, or {"ok": False, "error"} saying why; never raises."""
	tried = []
	for path in _candidates():
		tried.append(path)
		if not os.path.exists(path):
			continue
		try:
			f = open(path, "r")
			try:
				view = system.util.jsonDecode(f.read())
			finally:
				f.close()
		except Exception as exc:
			return {"ok": False, "error": "could not read %s: %s" % (path, exc),
			        "tried": tried}
		custom = view.get("custom") or {}
		missing = [k for k in KEYS if k not in custom]
		if missing:
			return {"ok": False,
			        "error": "%s has no custom.%s" % (VIEW, ", custom.".join(missing)),
			        "path": path}
		doc = {}
		for k in KEYS:
			doc[k] = custom[k]
		return {"ok": True, "view": VIEW, "path": path, "scene": doc,
		        "parts": len(doc["parts"]), "materials": len(doc["materials"])}
	return {"ok": False,
	        "error": "%s/view.json was not found on this gateway" % VIEW,
	        "tried": tried}
