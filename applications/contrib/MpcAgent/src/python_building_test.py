# import python_building
# import CBC_Gui
# import time
# import signal
# import sys
# import random
#
# b = python_building.Building()
# gui = CBC_Gui.CBC_Gui(b)
#
# def signal_handler(signal, frame):
# 	print 'You pressed Ctrl+C!'
# 	cont=0
# 	gui.exit()
# 	sys.exit(0)
#
# cont=1
# signal.signal(signal.SIGINT,signal_handler)
#
# while cont:
# 	time.sleep(1)
# 	b.advance(1)
# 	for zone in 0,3:
# 		t0 = b.get_indoor_temp(zone);
# 		tout = b.get_outdoor_temp()
# 		high_lim = b.get_high_temp_limit(zone)
# 		low_lim = b.get_low_temp_limit(zone)
# 		b.set_hvac_mode(zone,random.randint(-2,2))
# 		b.set_deadbands(zone,5.0,2.0)
# 		b.set_fan_mode(zone,1)
# 		print zone,t0,tout,high_lim,low_lim
