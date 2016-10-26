#Data point name
oat_point_name = "OutsideAirTemperature"
mat_point_name = "MixedAirTemperature" #"DischargeAirTemperature"
dat_point_name = "DischargeAirTemperature"
rat_point_name = "ReturnAirTemperature"
oat_virtual_point_name = "ReturnAirCO2Stpt"
damper_point_name = "DamperSignal"
cool_call1_point_name = "CoolCall1"
cool_call2_point_name = "CoolCall2"
cool_cmd1_point_name = "CoolCommand1"
cool_cmd2_point_name = "CoolCommand2"
fan_status_point_name = "FanStatus"
heat_command1_point_name="HeatCommand1"
heat_command2_point_name="HeatCommand2"
minimum_damper_name="ESMDamperMinPosition"

max_minimum_damper = 12.5
cfm=5000
temp_range=1.0

#Settings for AFDD
check_4_new_data_time = 5
mark_stale_data_time = check_4_new_data_time/2 #Number of seconds after receiving the new data
wait_4_new_data_time = 1
sync_trial_time = 30 #Number of seconds AFDD will wait for confirmation after commanding an equipment
seconds_to_steady_state = 300 #300
sleeptime = 5 #60
minutes_to_average = 1
afdd_threshold=4

#Settings for publisher agent
on_rtu1 = "rtu1" #rtu on which this AFDD applies
rtu_path = "RTU/PNNL/Sigma4/rtu1"
source_file = "Agents/AFDDAgent/afdd/data.csv"


#Settings for AFDD0
afdd0_threshold=5.0

#Settings for AFDD1
min_oa_temperature = 40
max_oa_temperature = 100
afdd1_threshold1 = 4
afdd1_threshold2 = 2  
oalow_limit = 0
oahigh_limit= 120 
ralow_limit = 50
rahigh_limit = 100 
malow_limit= 40
mahigh_limit = 100


#Settings for AFDD2

afdd2_temp_threshold = 4

#Settings for AFDD3
economizertype = 0 # 0 - for differential dry bulb ; 1 - for high limit on outside air temperature
afdd3_threshold = 0.30

#Settings for AFDD4


#settings for AFDD5
afdd5_threshold = 0.25
min_oa = 0.05
minimum_damper_command = 20

#settings for AFDD5
afdd6_threshold = 0