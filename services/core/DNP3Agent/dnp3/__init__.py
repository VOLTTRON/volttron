from pydnp3 import opendnp3

DEFAULT_POINT_TOPIC = 'dnp3/point'
DEFAULT_OUTSTATION_STATUS_TOPIC = 'mesa/outstation_status'
DEFAULT_LOCAL_IP = "0.0.0.0"
DEFAULT_PORT = 20000

# StepDefinition.fcode values:
DIRECT_OPERATE = 'direct_operate'       # This is actually DIRECT OPERATE / RESPONSE
SELECT = 'select'                       # This is actually SELECT / RESPONSE
OPERATE = 'operate'                     # This is actually OPERATE / RESPONSE
READ = 'read'
RESPONSE = 'response'

# PointDefinition.action values:
PUBLISH = 'publish'
PUBLISH_AND_RESPOND = 'publish_and_respond'

# Some PointDefinition.type values
POINT_TYPE_ARRAY = 'array'
POINT_TYPE_SELECTOR_BLOCK = 'selector_block'
POINT_TYPE_ENUMERATED = 'enumerated'
POINT_TYPES = [POINT_TYPE_ARRAY, POINT_TYPE_SELECTOR_BLOCK, POINT_TYPE_ENUMERATED]

# Some PointDefinition.point_type values:
DATA_TYPE_ANALOG_INPUT = 'AI'
DATA_TYPE_ANALOG_OUTPUT = 'AO'
DATA_TYPE_BINARY_INPUT = 'BI'
DATA_TYPE_BINARY_OUTPUT = 'BO'

# PointDefinition.group
DEFAULT_GROUP_BY_DATA_TYPE = {
    DATA_TYPE_BINARY_INPUT:  1,
    DATA_TYPE_BINARY_OUTPUT: 10,
    DATA_TYPE_ANALOG_INPUT:  30,
    DATA_TYPE_ANALOG_OUTPUT: 40
}

# variation = 1: 32 bit, variation = 2: 16 bit
DEFAULT_VARIATION = {
    DATA_TYPE_BINARY_INPUT:  {'evariation': opendnp3.EventBinaryVariation.Group2Var1,
                              'svariation': opendnp3.StaticBinaryVariation.Group1Var2},
    DATA_TYPE_BINARY_OUTPUT: {'evariation': opendnp3.EventBinaryOutputStatusVariation.Group11Var1,
                              'svariation': opendnp3.StaticBinaryOutputStatusVariation.Group10Var2},
    DATA_TYPE_ANALOG_INPUT:  {'evariation': opendnp3.EventAnalogVariation.Group32Var1,
                              'svariation': opendnp3.StaticAnalogVariation.Group30Var1},
    DATA_TYPE_ANALOG_OUTPUT: {'evariation': opendnp3.EventAnalogOutputStatusVariation.Group42Var1,
                              'svariation': opendnp3.StaticAnalogOutputStatusVariation.Group40Var1}
}

# PointDefinition.event_class
DEFAULT_EVENT_CLASS = 2

EVENT_CLASSES = {
    0: opendnp3.PointClass.Class0,
    1: opendnp3.PointClass.Class1,
    2: opendnp3.PointClass.Class2,
    3: opendnp3.PointClass.Class3
}

DATA_TYPES_BY_GROUP = {
    # Single-Bit Binary: See DNP3 spec, Section A.2-A.5 and Table 11-17
    1: DATA_TYPE_BINARY_INPUT,    # Binary Input (static): Reporting the present value of a single-bit binary object
    2: DATA_TYPE_BINARY_INPUT,    # Binary Input Event: Reporting single-bit binary input events and flag bit changes
    # Binary Output: See DNP3 spec, Section A.6-A.9 and Table 11-12
    10: DATA_TYPE_BINARY_OUTPUT,  # Binary Output (static): Reporting the present output status
    11: DATA_TYPE_BINARY_OUTPUT,  # Binary Output Event: Reporting changes to the output status or flag bits
    # Analog Input: See DNP3 spec, Section A.14-A.18 and Table 11-9
    30: DATA_TYPE_ANALOG_INPUT,   # Analog Input (static): Reporting the present value
    32: DATA_TYPE_ANALOG_INPUT,   # Analog Input Event: Reporting analog input events or changes to the flag bits
    # Analog Output: See DNP3 spec, Section A.19-A.22 and Table 11-10
    40: DATA_TYPE_ANALOG_OUTPUT,  # Analog Output Status (static): Reporting present value of analog outputs
    42: DATA_TYPE_ANALOG_OUTPUT   # Analog Output Event: Reporting changes to the analog output or flag bits
}
