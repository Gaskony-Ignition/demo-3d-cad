def doGet(request, session):
	"""Read-only routes (?cmd=state, status, check, faults, alarms, ...); a write cmd gets 405."""
	# Docstring inside the def on purpose: anything above `def doGet` makes the
	# route return an empty 200 with nothing in the log.
	import traceback

	READS = ["state", "status", "version", "check", "faults", "alarms",
	         "alarmcheck", "scene"]
	WRITES = ["setup", "fix", "fault", "clear", "reset", "speed", "mode",
	          "jog", "guards"]

	params = request['params']
	cmd = params.get('cmd', 'status')

	def refuse(code, body):
		try:
			request['servletResponse'].setStatus(code)
		except:
			pass
		return {'json': body}

	try:
		if cmd == 'state':
			# Polled at 4 Hz by the 3D page: keep this branch first and cheap.
			return {'json': MachineDemo.api.state()}

		if cmd == 'status':
			return {'json': {'ok': True, 'status': MachineDemo.api.status()}}

		if cmd == 'version':
			return {'json': {'ok': True,
			                 'version': MachineDemo.plant.VERSION,
			                 'cell': MachineDemo.plant.CELL_NAME,
			                 'provider': MachineDemo.plant.PROVIDER,
			                 'project': system.util.getProjectName()}}

		if cmd == 'scene':
			return {'json': MachineDemo.scene.document()}

		if cmd == 'check':
			return {'json': {'ok': True, 'check': MachineDemo.setup.check()}}

		if cmd == 'faults':
			return {'json': {'ok': True, 'faults': MachineDemo.api.faults()}}

		if cmd == 'alarms':
			return {'json': {'ok': True,
			                 'counts': MachineDemo.plant.alarmCounts(),
			                 'alarms': MachineDemo.plant.liveAlarms()}}

		if cmd == 'alarmcheck':
			# Tells apart: alarm not defined, disabled, not crossed, or queryStatus asked wrongly.
			prov = MachineDemo.plant.PROVIDER
			path = params.get('tag', 'Faults/ConveyorJam')
			full = MachineDemo.plant.tag(path)
			cfg = system.tag.getConfiguration(full, False)
			alarms = []
			for node in cfg:
				for a in (node.get('alarms') or []):
					alarms.append(dict((unicode(k), unicode(v))
					                   for k, v in a.items()))
			qv = system.tag.readBlocking([full])[0]
			everything = list(system.alarm.queryStatus())
			return {'json': {
				'ok': True, 'tag': path, 'value': unicode(qv.value),
				'quality': unicode(qv.quality),
				'alarmsOnTag': alarms,
				'slashTag': len(list(system.alarm.queryStatus(
					source=['prov:%s:/tag:*' % prov]))),
				'star': len(list(system.alarm.queryStatus(
					source=['prov:%s:*' % prov]))),
				'gatewayWideCount': len(everything),
				'gatewayWideSources': [unicode(e.getSource())
				                       for e in everything][:25],
			}}

		if cmd in WRITES:
			return refuse(405, {
				'ok': False,
				'error': 'writes are not accepted on GET',
				'cmd': cmd,
				'use': ('POST to this same URL with an authenticated user, '
				        'or the Setup screen in the Perspective project'),
				'example': ("curl -sS -X POST --netrc-file ~/.ignition-netrc "
				            "'.../admin?cmd=%s'" % cmd),
				'reads': READS,
				'writes': WRITES})

		return refuse(400, {'ok': False, 'error': 'unknown cmd: %s' % cmd,
		                    'reads': READS, 'writes': WRITES})

	except:
		return refuse(500, {'ok': False, 'error': traceback.format_exc()})
