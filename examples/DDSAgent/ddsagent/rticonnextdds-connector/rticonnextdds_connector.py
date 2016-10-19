##############################################################################
#    (c) 2005-2015 Copyright, Real-Time Innovations, All rights reserved.    #
#                                                                            #
# RTI grants Licensee a license to use, modify, compile, and create          #
# derivative works of the Software.  Licensee has the right to distribute    #
# object form only for use with RTI products. The Software is provided       #
# "as is", with no warranty of any type, including any warranty for fitness  #
# for any purpose. RTI is under no obligation to maintain or support the     #
# Software.  RTI shall not be liable for any incidental or consequential     #
# damages arising out of the use or inability to use the software.           #
#                                                                            #
##############################################################################

import ctypes
import os
import sys
import weakref
import platform
import json

(bits, linkage)  = platform.architecture();
osname = platform.system();
isArm = platform.uname()[4].startswith("arm");

def fromcstring(s):
	return s

def tocstring(s):
	return s

def tocstring3(s):
	try:
		return s.encode('utf8')
	except AttributeError as e:
		raise

def fromcstring3(s):
	try:
		return s.decode('utf8')
	except AttributeError as e:
		raise

if sys.version_info[0] == 3 :
	tocstring = tocstring3
	fromcstring = fromcstring3


if "64" in bits:
	if "Linux" in osname:
		arch = "x64Linux2.6gcc4.4.5"
		libname = "librti_dds_connector"
		post = "so"
	elif "Darwin" in osname:
		arch = "x64Darwin12clang4.1"
		libname = "librti_dds_connector"
		post = "dylib"
	else:
		print("platfrom not yet supported")
else:
	if isArm:
		arch = "armv6vfphLinux3.xgcc4.7.2"
		libname = "librti_dds_connector"
		post = "so"
	elif "Linux" in osname:
		arch = "i86Linux3.xgcc4.6.3"
		libname = "librti_dds_connector"
		post = "so"
	elif "Windows" in osname:
		arch = "i86Win32VS2010"
		libname = "rti_dds_connector"
		post = "dll"
	else:
		print("platfrom not yet supported")

path = os.path.dirname(os.path.realpath(__file__))
path = path + os.sep + "lib" + os.sep + arch + os.sep;
libname = libname + "." + post
rti = ctypes.CDLL(os.path.join(path, libname), ctypes.RTLD_GLOBAL)

rtin_RTIDDSConnector_new = rti.RTIDDSConnector_new
rtin_RTIDDSConnector_new.restype = ctypes.c_void_p
rtin_RTIDDSConnector_new.argtypes = [ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p]

rtin_RTIDDSConnector_getWriter= rti.RTIDDSConnector_getWriter
rtin_RTIDDSConnector_getWriter.restype= ctypes.c_void_p 
rtin_RTIDDSConnector_getWriter.argtypes=[ ctypes.c_void_p,ctypes.c_char_p ]

rtin_RTIDDSConnector_getReader= rti.RTIDDSConnector_getReader
rtin_RTIDDSConnector_getReader.restype= ctypes.c_void_p 
rtin_RTIDDSConnector_getReader.argtypes=[ ctypes.c_void_p,ctypes.c_char_p ]

rtin_RTIDDSConnector_setNumberIntoSamples = rti.RTIDDSConnector_setNumberIntoSamples
rtin_RTIDDSConnector_setNumberIntoSamples.argtypes = [ctypes.c_void_p, ctypes.c_char_p,ctypes.c_char_p,ctypes.c_double]
rtin_RTIDDSConnector_setBooleanIntoSamples = rti.RTIDDSConnector_setBooleanIntoSamples
rtin_RTIDDSConnector_setBooleanIntoSamples.argtypes = [ctypes.c_void_p, ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
rtin_RTIDDSConnector_setStringIntoSamples = rti.RTIDDSConnector_setStringIntoSamples
rtin_RTIDDSConnector_setStringIntoSamples.argtypes = [ctypes.c_void_p, ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p]

rtin_RTIDDSConnector_write = rti.RTIDDSConnector_write
rtin_RTIDDSConnector_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

rtin_RTIDDSConnector_read = rti.RTIDDSConnector_read
rtin_RTIDDSConnector_read.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
rtin_RTIDDSConnector_take = rti.RTIDDSConnector_take
rtin_RTIDDSConnector_take.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

rtin_RTIDDSConnector_wait = rti.RTIDDSConnector_wait
rtin_RTIDDSConnector_wait.restype = ctypes.c_int
rtin_RTIDDSConnector_wait.argtypes = [ctypes.c_void_p, ctypes.c_int]

rtin_RTIDDSConnector_getInfosLength = rti.RTIDDSConnector_getInfosLength
rtin_RTIDDSConnector_getInfosLength.restype = ctypes.c_double
rtin_RTIDDSConnector_getInfosLength.argtypes = [ctypes.c_void_p,ctypes.c_char_p]

rtin_RTIDDSConnector_getBooleanFromInfos = rti.RTIDDSConnector_getBooleanFromInfos
rtin_RTIDDSConnector_getBooleanFromInfos.restype  = ctypes.c_int
rtin_RTIDDSConnector_getBooleanFromInfos.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]

rtin_RTIDDSConnector_getSamplesLength = rti.RTIDDSConnector_getInfosLength
rtin_RTIDDSConnector_getSamplesLength.restype = ctypes.c_double
rtin_RTIDDSConnector_getSamplesLength.argtypes = [ctypes.c_void_p,ctypes.c_char_p]

rtin_RTIDDSConnector_getNumberFromSamples = rti.RTIDDSConnector_getNumberFromSamples
rtin_RTIDDSConnector_getNumberFromSamples.restype = ctypes.c_double
rtin_RTIDDSConnector_getNumberFromSamples.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]

rtin_RTIDDSConnector_getBooleanFromSamples = rti.RTIDDSConnector_getBooleanFromSamples
rtin_RTIDDSConnector_getBooleanFromSamples.restype = ctypes.c_int
rtin_RTIDDSConnector_getBooleanFromSamples.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]

rtin_RTIDDSConnector_getStringFromSamples = rti.RTIDDSConnector_getStringFromSamples
rtin_RTIDDSConnector_getStringFromSamples.restype = ctypes.c_char_p
rtin_RTIDDSConnector_getStringFromSamples.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]

rtin_RTIDDSConnector_getJSONSample = rti.RTIDDSConnector_getJSONSample
rtin_RTIDDSConnector_getJSONSample.restype = ctypes.c_char_p
rtin_RTIDDSConnector_getJSONSample.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

rtin_RTIDDSConnector_setJSONInstance = rti.RTIDDSConnector_setJSONInstance
rtin_RTIDDSConnector_setJSONInstance.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]


#Python Class Definition

class Samples:
	def __init__(self,input):
		self.input = input;

	def getLength(self):
		return int(rtin_RTIDDSConnector_getSamplesLength(self.input.connector.native,tocstring(self.input.name)));

	def getNumber(self, index, fieldName):
		return rtin_RTIDDSConnector_getNumberFromSamples(self.input.connector.native,tocstring(self.input.name),index,tocstring(fieldName));

	def getBoolean(self, index, fieldName):
		return rtin_RTIDDSConnector_getBooleanFromSamples(self.input.connector.native,tocstring(self.input.name),index,tocstring(fieldName));

	def getString(self, index, fieldName):
		return fromcstring(rtin_RTIDDSConnector_getStringFromSamples(self.input.connector.native,tocstring(self.input.name),index,tocstring(fieldName)));

	def getDictionary(self,index):
		jsonStr = rtin_RTIDDSConnector_getJSONSample(self.input.connector.native,tocstring(self.input.name),index);
		return json.loads(fromcstring(jsonStr))

class Infos:
	def __init__(self,input):
		self.input = input;

	def getLength(self):
		return int(rtin_RTIDDSConnector_getInfosLength(self.input.connector.native,tocstring(self.input.name)));

	def isValid(self, index):
		return rtin_RTIDDSConnector_getBooleanFromInfos(self.input.connector.native,tocstring(self.input.name),index,tocstring('valid_data'));

class Input:
	def __init__(self, connector, name):
		self.connector = connector;
		self.name = name;
		self.native= rtin_RTIDDSConnector_getReader(self.connector.native,tocstring(self.name))
		if self.native == None:
			raise ValueError("Invalid Subscription::DataReader name")
		self.samples = Samples(self);
		self.infos = Infos(self);

	def read(self):
		rtin_RTIDDSConnector_read(self.connector.native,tocstring(self.name));

	def take(self):
		rtin_RTIDDSConnector_take(self.connector.native,tocstring(self.name));

	def wait(self,timeout):
		return rtin_RTIDDSConnector_wait(self.connector.native,timeout);

class Instance:
	def __init__(self, output):
		self.output = output;

	def setNumber(self, fieldName, value):
		try:
			rtin_RTIDDSConnector_setNumberIntoSamples(self.output.connector.native,tocstring(self.output.name),tocstring(fieldName),value);
		except ctypes.ArgumentError as e:
			raise TypeError("field:{0} should be of type Numeric"\
				.format(fieldName))

	def setBoolean(self,fieldName, value):
		try:
			rtin_RTIDDSConnector_setBooleanIntoSamples(self.output.connector.native,tocstring(self.output.name),tocstring(fieldName),value);
		except ctypes.ArgumentError as e:
			raise TypeError("field:{0} should be of type Boolean"\
				.format(fieldName))

	def setString(self, fieldName, value):
		try:
			rtin_RTIDDSConnector_setStringIntoSamples(self.output.connector.native,tocstring(self.output.name),tocstring(fieldName),tocstring(value));
		except AttributeError | ctypes.ArgumentError as e:
			raise TypeError("field:{0} should be of type String"\
				.format(fieldName))

	def setDictionary(self,dictionary):
		jsonStr = json.dumps(dictionary)
		rtin_RTIDDSConnector_setJSONInstance(self.output.connector.native,tocstring(self.output.name),tocstring(jsonStr));


class Output:
	def __init__(self, connector, name):
		self.connector = connector;
		self.name = name;
		self.native= rtin_RTIDDSConnector_getWriter(self.connector.native,tocstring(self.name))
		if self.native ==None:
			raise ValueError("Invalid Publication::DataWriter name")
		self.instance = Instance(self);

	def write(self):
		return rtin_RTIDDSConnector_write(self.connector.native,tocstring(self.name));

class Connector:
	def __init__(self, configName, fileName):
		self.native = rtin_RTIDDSConnector_new(tocstring(configName), tocstring(fileName),None);
		if self.native == None:
			raise ValueError("Invalid participant profile, xml path or xml profile")

	def getOutput(self, outputName):
		return Output(self,outputName);

	def getInput(self, inputName):
		return Input(self, inputName);
