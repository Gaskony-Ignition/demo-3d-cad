def handleTimerEvent():
	"""Run one cell simulation step and publish the alarm summary tags (500 ms, shared thread, fixed delay)."""
	MachineDemo.sim.tick()
	MachineDemo.ui.publishAlarms()
