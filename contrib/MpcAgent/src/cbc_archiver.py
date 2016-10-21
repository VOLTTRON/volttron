# This python script scrapes data from the scanA.csv and
# scanB.csv files created by the python_cbc_building module
# and stores this scraped data in the SMAP archiver.
# 
import os
from string import *
import time
from pytz import timezone
from smap import driver, util

# SMAP heading
smapHeading = "ORNL/cbc"

# Data will be scraped from whichever of these files has the
# most recent write
fileA = "scanA.csv"
fileB = "scanB.csv"
fileHandle = None

# Structure to hold most recent data scraped for a thermostat
class Thermostat:
	timestamp = None
	temp = None
	upper_temp_limit = None
	lower_temp_limit = None
	addr = None
	mode = None

# Map from zone address to Thermostat object for that address
zoneInfo = dict()

# Get the most recently updated file, or return None
# if neither file exists
def select_most_recent_file():
	mA = None
	mB = None
	try:
		mA = os.path.getmtime(fileA)
	except OSError:
		pass
	try:
		mB = os.path.getmtime(fileB)
	except OSError:
		pass
	if mA == None and mB == None:
		return None
	if mA == None and mB != None:
		return fileB
	if mA != None and mB == None:
	 	return fileA
	if mA > mB:
		return fileA
	return fileB

def scrape():
	global fileHandle
	count = 0
	which = select_most_recent_file()
	if which == None:
		return
	if fileHandle == None or fileHandle.name != which:
		fileHandle = open(which,"rb",0)
	# Reset the end of file indicator
	fileHandle.seek(fileHandle.tell())
	# Go through the file line by line updating the thermostat
	# data as we go
	for line in fileHandle:
		words = split(line,",")
		count = count + 1
		if len(words) > 12:
			newData = Thermostat()
			newData.timestamp = words[0]
			newData.addr = words[2]
			newData.temp = words[4]
			newData.mode = words[6]
			if newData.mode == 'idle':
				newData.mode = 0
			elif newData.mode == 'heat1':
				newData.mode = 1
			elif newData.mode == 'heat2':
				newData.mode = 2
			elif newData.mode == 'cool1':
				newData.mode = -1
			elif newData.mode == 'cool2':
				newData.mode = -2
			else:
				newData.mode = 999
			newData.lower_temp_limit = words[10]
			newData.upper_temp_limit = words[12]
			zoneInfo[newData.addr] = newData
	print "Processed ",count," new lines in file ",fileHandle.name,fileHandle.tell()

class cbc_archiver(driver.SmapDriver):
	def setup(self, opts):
		# Scrape data until we have seen all four zones
		while len(zoneInfo) < 4:
			scrape()
		# Register a timeseries for each zone
		print "Adding subjects..."
		self.add_timeseries(smapHeading+"/peak_power_reduction",'%',data_type='double',timezone='US/Eastern')
		for data in zoneInfo.itervalues():
			name = smapHeading+"/zone/"+data.addr
			self.add_timeseries(name+'/temp', 'F', data_type='double', timezone='US/Eastern')
			self.add_timeseries(name+'/mode', '', data_type='long', timezone='US/Eastern')
			self.add_timeseries(name+'/lower_temp_limit', 'F', data_type='double', timezone='US/Eastern')
			self.add_timeseries(name+'/upper_temp_limit', 'F', data_type='double', timezone='US/Eastern')
		print "done!"
	def start(self):
		util.periodicSequentialCall(self.read).start(60)
	def read(self):
		# Look for new data
		scrape()
		# Record the new data
		timestamp = 0
		operating = 0.0
		would_operate = 0.0
		max_operate = 0.0
		peak_power_reduction = 0.0
		for data in zoneInfo.itervalues():
			max_operate = max_operate + 1.0
			if data.mode != 0:
				operating = operating+1.0
			if float(data.temp) < float(data.lower_temp_limit) or float(data.temp) > float(data.upper_temp_limit):
				would_operate = would_operate+1.0
			name = smapHeading+"/zone/"+data.addr
			timestamp = time.mktime(time.strptime(data.timestamp,"%Y-%m-%d %H:%M:%S"))
			self.add(name+'/temp',timestamp,float(data.temp))
			self.add(name+'/mode',timestamp,long(data.mode))
			self.add(name+'/lower_temp_limit',timestamp,float(data.lower_temp_limit))
			self.add(name+'/upper_temp_limit',timestamp,float(data.upper_temp_limit))
		if would_operate > 0.0:
			peak_power_reduction = 1.0-operating/would_operate
		self.add(smapHeading+"/peak_power_reduction",timestamp,peak_power_reduction)
