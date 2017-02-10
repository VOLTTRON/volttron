import ctypes

class Building:
	def cleanup(self):
		self.clib.free_building.argtypes = []
		self.clib.free_building.restype = None
		self.clib.free_building()
	def __init__(self):
		self.clib = ctypes.CDLL("bldg_lib.so")
		self.clib.init_building.argtypes = []
		self.clib.init_building.restype = None
		self.clib.init_building()
		self.outdoor_temp = None
	def get_num_zones(self):
		self.clib.get_num_zones.argtypes = []
		self.clib.get_num_zones.restype = ctypes.c_int
		result = self.clib.get_num_zones()
		return result
	def get_indoor_temp(self,zone):
		self.clib.get_indoor_temp.argtypes = [ctypes.c_int]
		self.clib.get_indoor_temp.restype = ctypes.c_double
		zone_arg = ctypes.c_int(zone)
		result = self.clib.get_indoor_temp(zone_arg)
		return result
	def get_high_temp_limit(self,zone):
		self.clib.get_high_temp_limit.argtypes = [ctypes.c_int]
		self.clib.get_high_temp_limit.restype = ctypes.c_double
		zone_arg = ctypes.c_int(zone)
		result = self.clib.get_high_temp_limit(zone_arg)
		return result
	def get_low_temp_limit(self,zone):
		self.clib.get_low_temp_limit.argtypes = [ctypes.c_int]
		self.clib.get_low_temp_limit.restype = ctypes.c_double
		zone_arg = ctypes.c_int(zone)
		result = self.clib.get_low_temp_limit(zone_arg)
		return result
	def set_deadbands(self,zone,cool,heat):
		self.clib.set_deadbands.argtypes = [ctypes.c_int,ctypes.c_double,ctypes.c_double]
		self.clib.set_deadbands.restype = None
		zone_arg = ctypes.c_int(zone)
		cool_arg = ctypes.c_double(cool)
		heat_arg = ctypes.c_double(heat)
		self.clib.set_deadbands(zone_arg,cool_arg,heat_arg)
	def set_fan_mode(self,zone,mode):
		self.clib.set_fan_mode.argtypes = [ctypes.c_int,ctypes.c_int]
		self.clib.set_fan_mode.restype = None
		zone_arg = ctypes.c_int(zone)
		mode_arg = ctypes.c_int(mode)
		self.clib.set_fan_mode(zone_arg,mode_arg)
	def get_outdoor_temp(self):
		result = self.outdoor_temp
		if result == None:
			self.clib.get_outdoor_temp.argtypes = []
			self.clib.get_outdoor_temp.restype = ctypes.c_double
			result = self.clib.get_outdoor_temp()
		return result
	def set_outdoor_temp(self,degf):
		self.outdoor_temp = degf
	def set_hvac_mode(self,zone,mode):
		self.clib.set_hvac_mode.argtypes = [ctypes.c_int,ctypes.c_int]
		self.clib.set_hvac_mode.restype = None
		zone_arg = ctypes.c_int(zone)
		mode_arg = ctypes.c_int(mode)
		self.clib.set_hvac_mode(zone_arg,mode_arg)
	def advance(self,dtHrs):
		self.clib.advance.argtypes = [ctypes.c_double]
		self.clib.advance.restype = None
		dtHrs_arg = ctypes.c_double(dtHrs)
		self.clib.advance(dtHrs)

