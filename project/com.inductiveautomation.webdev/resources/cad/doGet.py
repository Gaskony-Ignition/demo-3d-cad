def doGet(request, session):
	"""Serve CAD part files (?model=&f=), part lists (f=list) and part alarms (f=alarms)."""
	# `def doGet` must be the first byte of this file, or the route returns an empty 200.
	import os

	params = request.get('params', {}) or {}
	want = params.get('f', '')
	model = params.get('model', '') or ''

	def send(path, contentType):
		# Bytes returned as 'response' are re-encoded as text and arrive corrupt;
		# write them to the servlet stream and return None.
		data = system.file.readFileAsBytes(path)
		resp = request['servletResponse']
		resp.setContentType(contentType)
		resp.setContentLength(len(data))
		out = resp.getOutputStream()
		out.write(data)
		out.flush()
		return None

	if want == 'alarms':
		return {'json': {'ok': True, 'key': MachineDemo.tagdata.CAD_PART,
		                 'alarms': MachineDemo.cad.alarms()}}

	if model:
		try:
			kind, names = MachineDemo.cad.files(model)
		except ValueError as e:
			return {'json': {'ok': False, 'error': str(e)}}
		if want == 'list':
			return {'json': {'ok': True, 'model': model, 'kind': kind,
			                 'parts': names}}
		path = MachineDemo.cad.filePath(model, want) if want in names else None
		if path is None:
			return {'json': {'ok': False, 'error': 'unknown part',
			                 'available': names + ['list']}}
		return send(path, 'application/octet-stream')

	d = MachineDemo.cad.builtinDir()
	if d is None:
		return {'json': {'ok': False, 'error': 'cad folder not found'}}

	# Every STL in this resource folder is a part of the built-in model.
	names = sorted([f[:-4] for f in os.listdir(d) if f.lower().endswith('.stl')])

	if want == 'list':
		return {'json': {'ok': True, 'kind': 'stl', 'parts': names,
		                 'project': system.util.getProjectName()}}

	if want in names:
		return send(os.path.join(d, '%s.stl' % want), 'application/octet-stream')

	return {'json': {'ok': False, 'error': 'unknown part',
	                 'available': names + ['list', 'alarms']}}
