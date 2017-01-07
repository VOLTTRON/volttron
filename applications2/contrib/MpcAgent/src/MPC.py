import python_building
import python_control
import time

# Scale the clock
def scale_time(seconds):
	# 1 second real time = 1 hours simulated time
	# return 30.0*seconds/3600.0
	# Run in real time
	return seconds

# This is a cludge. It should return the same value
# as the control period from the control object.
PERIOD = scale_time(30*60)

class MPC:
	def __init__(self):
		# Setup the actuator and control modules
		self.bldg = python_building.Building()
		self.cntrl = python_control.Control(self.bldg.get_num_zones())
		self.cntrl.set_max_units(self.bldg.get_num_zones()/2)

	def set_outdoor_temp(self,degF):
		self.bldg.set_outdoor_temp(degF)
	
	def get_outdoor_temp(self):
		return self.bldg.get_outdoor_temp()

	def run_control(self,simHrs):
		self.bldg.advance(simHrs)
		for zone in range(0,self.bldg.get_num_zones()):
			self.cntrl.set_upper_limit(zone,self.bldg.get_high_temp_limit(zone))
			self.cntrl.set_lower_limit(zone,self.bldg.get_low_temp_limit(zone))
			self.cntrl.set_zone_temp(zone,self.bldg.get_indoor_temp(zone))
		self.cntrl.set_outside_temp(self.bldg.get_outdoor_temp())
		self.cntrl.run_control()
		for zone in range(0,self.bldg.get_num_zones()):
			self.bldg.set_hvac_mode(zone,self.cntrl.get_hvac_command(zone))

	def cleanup(self):
		self.bldg.cleanup()
		self.cntrl.cleanup()

