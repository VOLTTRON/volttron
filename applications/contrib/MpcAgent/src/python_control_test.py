# import python_control
#
# c = python_control.Control(2)
# period = c.get_control_period()
# print period
# for x in range(0,1):
# 	c.set_upper_limit(x,30)
# 	c.set_lower_limit(x,20)
# c.set_zone_temp(0,15)
# c.set_zone_temp(1,35)
# c.set_outside_temp(25)
# c.set_max_units(2)
# for x in range(10):
# 	c.run_control()
# 	mode1 = c.get_hvac_command(0)
# 	mode2 = c.get_hvac_command(1)
# 	print mode1, mode2
