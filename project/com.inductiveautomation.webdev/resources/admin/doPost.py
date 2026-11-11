def doPost(request, session):
	"""Refuse every POST with 405: writes go through the Setup screen or the Script Console."""
	# Docstring inside the def: anything above `def doPost` makes the route return an empty 200.
	import traceback

	def refuse(code, body):
		try:
			request['servletResponse'].setStatus(code)
		except:
			pass
		return {'json': body}

	try:
		cmd = (request['params'] or {}).get('cmd', '')
		return refuse(405, {
			'ok': False,
			'error': ('writes are not accepted over HTTP; use the Setup '
			          'screen or the Designer Script Console'),
			'cmd': cmd,
			'use': ('MachineDemo.api.* / MachineDemo.setup.* from the '
			        'Designer Script Console, or the Setup screen in the '
			        'Perspective project'),
		})

	except:
		return refuse(500, {'ok': False, 'error': traceback.format_exc()})
