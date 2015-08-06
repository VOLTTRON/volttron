import ctypes

class Control:
	def cleanup(self):
		self.clib.free_control.argtypes = []
		self.clib.free_control.restype = None
		self.clib.free_control()
	def __init__(self,numZones):
		self.clib = ctypes.CDLL("mpc_lib.so")
		self.clib.init_control.argtypes = [ctypes.c_int]
		self.clib.init_control.restype = None
		numZones_arg = ctypes.c_int(numZones)
		self.clib.init_control(numZones_arg)
	def set_upper_limit(self,zone,degsC):
		self.clib.set_upper_limit.argtypes = [ctypes.c_int,ctypes.c_double]
		self.clib.set_lower_limit.restype = None
		zone_arg = ctypes.c_int(zone)
		temp_arg = ctypes.c_double(degsC)
		self.clib.set_upper_limit(zone_arg,temp_arg)
	def set_lower_limit(self,zone,degsC):
		self.clib.set_lower_limit.argtypes = [ctypes.c_int,ctypes.c_double]
		self.clib.set_lower_limit.restype = None
		zone_arg = ctypes.c_int(zone)
		temp_arg = ctypes.c_double(degsC)
		self.clib.set_lower_limit(zone_arg,temp_arg)
	def set_zone_temp(self,zone,degsC):
		self.clib.set_zone_temp.argtypes = [ctypes.c_int,ctypes.c_double]
		self.clib.set_zone_temp.restype = None
		zone_arg = ctypes.c_int(zone)
		temp_arg = ctypes.c_double(degsC)
		self.clib.set_zone_temp(zone_arg,temp_arg)
	def set_outside_temp(self,degsC):
		self.clib.set_outside_temp.argtypes = [ctypes.c_double]
		self.clib.set_outside_temp.restype = None
		temp_arg = ctypes.c_double(degsC)
		self.clib.set_outside_temp(temp_arg)
	def set_max_units(self,units):
		self.clib.set_max_units.argtypes = [ctypes.c_int]
		self.clib.set_max_units.restype = None
		units_arg = ctypes.c_int(units)
		self.clib.set_max_units(units_arg)
	def run_control(self):
		self.clib.run_control.argtypes = []
		self.clib.run_control.restype = None
		self.clib.run_control()
	def get_hvac_command(self,zone):
		self.clib.get_hvac_command.argtypes = [ctypes.c_int]
		self.clib.get_hvac_command.restype = ctypes.c_int
		zone_arg = ctypes.c_int(zone)
		result = self.clib.get_hvac_command(zone_arg)
		return result
	def get_control_period(self):
		self.clib.get_control_period.argtypes = []
		self.clib.get_control_period.restype = ctypes.c_double
		result = self.clib.get_control_period()
		return result

