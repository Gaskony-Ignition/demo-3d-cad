def handleTimerEvent():
	"""Run one cell simulation step (500 ms, shared thread, fixed delay)."""
	MachineDemo.sim.tick()
