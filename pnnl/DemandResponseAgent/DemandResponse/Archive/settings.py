#settings for DR agent
#Schedule settings
pre_cpp_hour = 0
during_cpp_hour =0
after_cpp_hour = 0

#Cooling Set Point SSettings
csp_norm = 74  #For testing will read from controller

csp_pre = 67

csp_cpp = 80

max_precool_hours = 5
fan_reduction = 0.1 #fractional reduction 10% = 0.1

pre_time = 65 #number of seconds between stepping down cooling set point in pre-cooling procedure

after_time =65 #number of seconds between stepping down cooling set point in after-cooling procedure

damper_cpp = 0 #minimum damper command during CPP event

signal = True

default_command_timeout = 20

default_data_timeout = 200
