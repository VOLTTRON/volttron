import MPC
import signal

app = None

def signal_handler(signal, frame):
	print "Shutting down..."
	app.set_stop()

signal.signal(signal.SIGINT,signal_handler)
signal.signal(signal.SIGTERM,signal_handler)
app = MPC.MPC()
app.run()

