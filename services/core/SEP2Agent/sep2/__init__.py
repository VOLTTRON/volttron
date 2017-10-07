from collections import namedtuple

STOR_UNKNOWN = -1
STOR_DISCONNECTED = 1
STOR_CONNECTED = 5

CONTROL_MODE_LOCAL = 0
CONTROL_MODE_REMOTE = 1

INVERTER_STATUS_UNKNOWN = -1
INVERTER_NORMAL = 0
INVERTER_OFF = 1
INVERTER_STARTING = 3
INVERTER_FORCED_POWER_REDUCTION = 5
INVERTER_FAULT = 7
INVERTER_CELL_BALANCING = 10

MRID_SUFFIX_FUNCTION_SET_ASSIGNMENT = 3
MRID_SUFFIX_DER_PROGRAM = 4
MRID_SUFFIX_DER_CONTROL = 5

EVENT_STATUS_SCHEDULE = 0
EVENT_STATUS_ACTIVE = 1
EVENT_STATUS_CANCELLED = 2
EVENT_STATUS_CANCELLED_RANDOM = 3
EVENT_STATUS_SUPERCEDED = 4

QUALITY_NTP = 3

STATUS_CODES = {
    200: '200 OK',
    201: '201 Created',
    204: '204 No Content',
    500: '500 Internal Error',
}
XML_HEADERS = [("Content-Type", "application/sep+xml")]
CREATED_HEADERS = [("Content-Length", "0")]

Endpoint = namedtuple('Endpoint', ['url', 'callback'])
SEP2_ENDPOINTS = {
    "dcap": Endpoint(url="/dcap", callback='dcap'),
    "tm": Endpoint(url="/dcap/tm", callback='tm'),
    "sdev": Endpoint(url="/dcap/sdev", callback='sdev'),
    "edev-list": Endpoint(url="/dcap/edev", callback='edev_list'),

    "sdev-di": Endpoint(url="/dcap/sdev/di", callback='sdev_di'),
    "sdev-log": Endpoint(url="/dcap/sdev/log", callback='sdev_log'),

    "mup-list": Endpoint(url="/dcap/mup", callback='mup_list'),
}
SEP2_MUP_ENDPOINTS = {
    "mup": Endpoint(url="/dcap/mup/{}", callback='mup'),
}
SEP2_EDEV_ENDPOINTS = {
    "edev": Endpoint(url="/dcap/edev/{}", callback='edev'),
    "reg": Endpoint(url="/dcap/edev/{}/reg", callback='edev_reg'),
    "di": Endpoint(url="/dcap/edev/{}/di", callback='edev_di'),
    "dstat": Endpoint(url="/dcap/edev/{}/dstat", callback='edev_dstat'),
    "ps": Endpoint(url="/dcap/edev/{}/ps", callback='edev_ps'),
    "der-list": Endpoint(url="/dcap/edev/{}/der", callback='edev_der_list'),

    "derp-list": Endpoint(url="/dcap/edev/{}/derp", callback='edev_derp_list'),
    "derp": Endpoint(url="/dcap/edev/{}/derp/1", callback='edev_derp'),

    "der": Endpoint(url="/dcap/edev/{}/der/1", callback='edev_der'),
    "dera": Endpoint(url="/dcap/edev/{}/der/1/dera", callback='edev_dera'),
    "dercap": Endpoint(url="/dcap/edev/{}/der/1/dercap", callback='edev_dercap'),
    "derg": Endpoint(url="/dcap/edev/{}/der/1/derg", callback='edev_derg'),
    "ders": Endpoint(url="/dcap/edev/{}/der/1/ders", callback='edev_ders'),

    "derc-list": Endpoint(url="/dcap/edev/{}/derc", callback='edev_derc_list'),
    "derc": Endpoint(url="/dcap/edev/{}/derc/1", callback='edev_derc'),

    "fsa-list": Endpoint(url="/dcap/edev/{}/fsa", callback='edev_fsa_list'),
    "fsa": Endpoint(url="/dcap/edev/{}/fsa/0", callback='edev_fsa'),
}

RESOURCE_MAPPING = {
    "DeviceInformation": "device_information",
    "MirrorMeterReading": "mup",
    "DERStatus": "der_status",
    "DERControl": "der_control",
    "DERCapability": "der_capability",
    "DERSettings": "der_settings",
    "DERAvailability": "der_availability",
    "PowerStatus": "power_status",
}