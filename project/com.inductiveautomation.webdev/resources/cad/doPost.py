def doPost(request, session):
	"""Accept only ?f=parts: store the part names the CAD page parsed from a STEP model."""
	# `def doPost` must be the first byte of this file, or the route returns an empty 200.
	params = request.get('params', {}) or {}
	if params.get('f', '') != 'parts' or not params.get('model'):
		return {'json': {'ok': False, 'error': 'only ?f=parts&model=<name> is accepted'}}
	try:
		n = MachineDemo.cad.saveParts(params.get('model'), request.get('postData'))
	except ValueError as e:
		return {'json': {'ok': False, 'error': str(e)}}
	return {'json': {'ok': True, 'parts': n}}
