import json
import logging
import math
import re
import struct
from enum import Enum

_log = logging.getLogger("cta_resources")

regEx = re.compile(r"080100|080200")
camel_to_snake_re = re.compile(r"(?<!^)(?=[A-Z])")
camel_to_snake = lambda x: camel_to_snake_re.sub("_", x).lower()

class EventStates(str, Enum):
    """
    Enumeration class for DER event states
    While this is a string enumeration, we're using it
    as an integer enum as well, so ordering must be preserved, new states
    must be defined at the end of the list.
    """

    NOT_STARTED = "NOT_STARTED"
    PRE_EVENT = "PRE_EVENT"
    CURTAILED = "CURTAILED"
    POST_EVENT = "POST_EVENT"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"
    OPTED_OUT = "OPTED_OUT"
    IDLE = "IDLE"

CTA_DEVICE_TYPES = {
    0x0000: "Unspecified Type",
    0x0001: "Water Heater - Gas",
    0x0002: "Water Heater - Electric",
    0x0003: "Water Heater – Heat Pump",
    0x0004: "Central AC – Heat Pump",
    0x0005: "Central AC – Fossil Fuel Heat",
    0x0006: "Central AC – Resistance Heat",
    0x0007: "Central AC (only)",
    0x0008: "Evaporative Cooler",
    0x0009: "Baseboard Electric Heat",
    0x000A: "Window AC",
    0x000B: "Portable Electric Heater",
    0x000C: "Clothes Washer",
    0x000D: "Clothes Dryer - Gas",
    0x000E: "Clothes Dryer - Electric",
    0x000F: "Refrigerator/Freezer",
    0x0010: "Freezer",
    0x0011: "Dishwasher",
    0x0012: "Microwave Oven",
    0x0013: "Oven – Electric",
    0x0014: "Oven – Gas",
    0x0015: "Cook Top – Electric",
    0x0016: "Cook Top - Gas",
    0x0017: "Stove – Electric",
    0x0018: "Stove - Gas",
    0x0019: "Dehumidifier",
    0x001A: "Central AC – Heat Pump Variable Capacity",
    0x001B: "Water Heater – Heat Pump Variable Capacity/Speed",
    0x001C: "Water Heater - Phase Change Material",
    0x0020: "Fan",
    0x0030: "Pool Pump – Single Speed",
    0x0031: "Pool Pump – Variable Speed",
    0x0032: "Electric Hot Tub",
    0x0040: "Irrigation Pump",
    0x0041: "Clothes Dryer – Heat Pump",
    0x1000: "Electric Vehicle",
    0x1001: "Hybrid Vehicle",
    0x1100: "Electric Vehicle Supply Equipment – general (SAE J1772)",
    0x1101: "Electric Vehicle Supply Equipment – Level 1 (SAE J1772)",
    0x1102: "Electric Vehicle Supply Equipment – Level 2 (SAE J1772)",
    0x1103: "Electric Vehicle Supply Equipment – Level 3 (SAE J1772)",
    0x2000: "In Premises Display",
    0x5000: "Energy Manager",
    0x6000: "Gateway Device",
    0x7000: "Distributed Energy Resources",
    0x7001: "Solar Inverter",
    0x7002: "Battery Storage",
}
CTA_DEVICE_CLASSES = {
    0x0001: "wh",
    0x0002: "wh",
    0x0003: "wh",
    0x0004: "hvac",
    0x0005: "hvac",
    0x0006: "hvac",
    0x0007: "hvac",
    0x000A: "ptac",
    0x001A: "hvac",
    0x001B: "wh",
    0x001C: "wh",
    0x0030: "poolpump",
    0x0031: "poolpump",
    0x1000: "ev",
    0x1001: "ev",
    0x1100: "evse",
    0x1101: "evse",
    0x1102: "evse",
    0x1103: "evse",
}

# TODO: Change message types to bytestrings
CTA_MESSAGE_TYPES = {
    "0181": "GetInformationReply",
    "0382": "GetTemperatureOffsetsReply",
    "0383": "GetTemperatureSetpointsReply",
    "0384": "GetPresentTemperatureReply",
    "0680": "GetCommodityReadReply",
    "0781": "GetThermostatModeReply",
    "0782": "GetThermostatFanModeReply",
    "0783": "GetThermostatHoldReply",
}
CTA_RESPONSE_CODES = dict(
    enumerate(
        [
            "Success",
            "Command not implemented",
            "Bad Value – one or more values in the message are invalid",
            "Command Length  Error – command is too long",
            "Response Length Error – response is too long",
            "Busy",
            "Other Error",
            "Customer Override is in effect",
            "Command not enabled",
        ]
    )
)
CTA_COMMODITY_CODES = dict(
    enumerate(
        [
            "Electricity Consumed",
            "Electricity Produced",
            "Natural gas",
            "Water",
            "Natural gas",
            "Water",
            "Total Energy Storage/Take Capacity",
            "Present Energy Storage/Take Capacity",
            "Rated Max Consumption Level Electricity",
            "Rated Max Production Level Electricity",
        ]
    )
)
CTA_CAPABILITY_BITMAP = dict(
    enumerate(
        [
            "Cycling supported",
            "Tier mode supported",
            "Price mode supported",
            "Temperature Offset supported",
            "Continuously variable power",
            "Discreetly variable power",
            "Advanced Load Up supported",
            "Price Stream supported",
            "SGD Efficiency Level supported",
        ]
    )
)
CTA_THERMOSTAT_SYSTEM_MODES = dict(
    enumerate(
        [
            "Off",
            "Auto",
            "Reserved",
            "Cool",
            "Heat",
            "Aux/Emer Heat",
            "Reserved",
            "Reserved",
        ]
    )
)
CTA_THERMOSTAT_HOLD_MODES = dict(
    enumerate(["No Hold", "Temporary Hold", "Permanent Hold", "Time Hold"])
)
tstatFanModes = {0: "Auto", 1: "On", 2: "Circulate"}

BASIC_OP_STATES = dict(
    enumerate(
        [
            "Idle Normal",
            "Running Normal",
            "Running Curtailed",
            "Running Heightened",
            "Idle Curtailed",
            "SGD Error Condition",
            "Idle Heightened",
            "Cycling On",
            "Cycling Off",
            "Variable Following",
            "Variable Not Following",
            "Idle, Opted Out",
            "Running, Opted Out",
        ]
    )
)

BASIC_DR_APP_OP_CODES = {
    "BasicDrMessage": "0801",
    "IntermediateDrMessage": "0802",
    "Shed": "01",
    "EndShed": "02",
    "BasicApplicationACK": "03",
    "BasicApplicationNAK": "04",
    "PowerLevelRequest": "06",
    "RelativePriceIndicator": "07",
    "NextPeriodRelativePrice": "08",
    "TimeRemainingPresentPricePeriod": "09",
    "CriticalPeakEvent": "0A",
    "GridEmergency": "0B",
    "GridGuidance": "0C",
    "OutsideCommConnectionStatus": "0E",
    "CustomerOverride": "11",
    "OperationStateQuery": "12",
    "StateQueryResponse": "13",
    "Sleep": "14",
    "WakeRefreshRequest": "15",
    "SimpleTimeSync": "16",
    "LoadUp": "17",
    "PendingEventTime": "18",
    "PendingEventType": "19",
    "Reboot": "1A",
}

WH_EVENT_STATE_MAP = {
    EventStates.PRE_EVENT: "LoadUp",
    EventStates.CURTAILED: "Shed",
    EventStates.ENDED: "EndShed",
    EventStates.CANCELLED: "EndShed",
    EventStates.OPTED_OUT: "EndShed",
    EventStates.IDLE: "EndShed",
    EventStates.POST_EVENT: "Shed",
}

class Basic(object):
    stateDict = BASIC_OP_STATES
    idleStateCodes = [
        idx
        for idx, val in BASIC_OP_STATES.items()
        if any((val in val.lower() for val in ("idle", "off", "not following")))
    ]

    @classmethod
    def process_payload(self, payload):
        data = {}
        if len(payload) == 4:
            opcode1 = payload[:2]  # .zfill(2)
            opcode2 = payload[2:]
            if opcode1 == "13":  # Processing Operational State Response
                data.update({"msg_name": "StateQueryResponse"})
                code = int(opcode2, base=16)
                desc = self.stateDict.get(code)

                if (
                    code in self.idleStateCodes
                ):  # Based on Table 10-3 – Operating State Codes we have two state
                    state = 0
                elif code == 5:
                    state = 3
                else:
                    state = 1

                if "Normal" in desc:
                    mode = 0
                elif "Curtailed" in desc:
                    mode = 1
                elif "Heightened" in desc:
                    mode = 2
                else:
                    mode = 3

                data.update(
                    {
                        "code": code,
                        "state": state,
                        "mode": mode,
                        "desc": desc,
                        "opted_out": code in (11, 12),
                    }
                )
            elif opcode1 == "11":  # Processing Customer Overrride Notification
                data.update({"msg_name": "CustomerOverrideNotice"})
                data.update({"opted_out": opcode2 == "01"})
            else:  # Setting ERROR for unprocessed message
                data.update({"error": "basic message not processed"})

            if "error" not in data:
                data.update({"error": None})
        else:
            data.update({"error": "invalid basic message"})
        return data


class Intermediate(object):
    deviceTypes = CTA_DEVICE_TYPES
    deviceClasses = CTA_DEVICE_CLASSES
    commodityCodes = CTA_COMMODITY_CODES
    capabilityBitmap = CTA_CAPABILITY_BITMAP

    tstatSystemModes = CTA_THERMOSTAT_SYSTEM_MODES
    tstatHoldModes = dict(
        enumerate(["No Hold", "Temporary Hold", "Permanent Hold", "Time Hold"])
    )
    tstatFanModes = {0: "Auto", 1: "On", 2: "Circulate"}
    cmdTypes: dict

    @classmethod
    def process_payload(self, payload):
        data = {}
        if len(payload) > 4:
            resp_code = int(payload[4:6], base=16)
            data["resp_code"] = resp_code
            if resp_code == 0:
                msg_type = CTA_MESSAGE_TYPES.get(payload[:4])
                if msg_type:
                    data.update(
                        getattr(self, "process_" + camel_to_snake(msg_type))(
                            payload[6:]
                        )
                    )
                    if "error" not in data:
                        data["error"] = None
                else:
                    data["error"] = "intermediate message not processed"
            else:
                data["error"] = CTA_RESPONSE_CODES.get(resp_code)
        else:
            data["error"] = "invalid intermediate message"
        return data

    @classmethod
    def process_get_information_reply(self, body):
        data = {"msg_name": "GetInformationReply"}
        bbody = bytes.fromhex(body)
        if len(bbody) < 13:
            data.update({"error": "missing required/mandatory field"})
        else:
            ctaver, vendor, devcode, rev, capcode = struct.unpack(
                ">2sHH2sI", bbody[:12]
            )
            data["version"] = ctaver
            data["vendor"] = hex(vendor)
            data["type"] = self.deviceClasses.get(devcode)
            data["devtype"] = self.deviceTypes.get(devcode)
            data["revision"] = rev
            data["capabilities"] = ", ".join(self.get_capabitities(capcode))

            if len(bbody) > 14:
                try:
                    model, serial = struct.unpack(">16s16s", bbody[13:45])
                    data["model"] = model.decode("utf-8")
                    data["serial"] = serial.decode("utf-8")
                    year_code, month_code, day_code, major, minor = struct.unpack(
                        ">5B", bbody[45:]
                    )
                    if year_code != 255:
                        data["year"] = 2000 + year_code
                    if month_code != 255:
                        data["month"] = 1 + month_code
                    if day_code != 255:
                        data["day"] = day_code
                    data["major"] = major
                    data["minor"] = minor
                except Exception as e:
                    print(e)
                    pass
        return data

    @classmethod
    def process_get_commodity_read_reply(self, body):
        data = {"msg_name": "GetCommodityReadReply"}
        length = len(body)
        if length < 26:
            data.update({"error": "missing required/mandatory field"})
        else:
            pos = 0
            commodities = dict()
            while pos < length and pos % 26 == 0:
                code = int(body[pos : 2 + pos], base=16)
                name = self.commodityCodes.get(code)
                rate = int(body[2 + pos : 14 + pos], base=16)
                amount = int(body[14 + pos : 26 + pos], base=16)
                commodities[code] = {
                    "code": code,
                    "name": name,
                    "instantaneous_rate": rate,
                    "cumulative_amount": amount,
                }
                pos += 26
            data["commodities"] = commodities
        return data

    @classmethod
    def process_get_temperature_offsets_reply(self, body):
        data = {"msg_name": "GetTemperatureOffsetReply"}
        if len(body) < 4:
            data.update({"error": "missing required/mandatory field"})
        else:
            data["offset"] = int(body[:2], base=16)
            data["units"] = "F" if body[2:] == "00" else "C"
        return data

    @classmethod
    def process_get_temperature_setpoints_reply(self, body):
        data = {"msg_name": "GetSetPointReply"}
        if len(body) < 10:
            data.update({"error": "missing required/mandatory field"})
        else:
            data["device_type"] = self.deviceTypes.get(int(body[:4], base=16))
            data["units"] = "F" if body[4:6] == "00" else "C"
            data["heat_setpoint"] = int(body[6:10], base=16)
            try:
                data["cool_setpoint"] = int(body[10:], base=16)
            except:
                pass
        return data

    @classmethod
    def process_get_present_temperature_reply(self, body):
        data = {"msg_name": "GetPresentTemperatureReply"}
        if len(body) < 10:
            data.update({"error": "missing required/mandatory field"})
        else:
            data["device_type"] = self.deviceTypes.get(int(body[:4], base=16))
            data["units"] = "F" if body[4:6] == "00" else "C"
            data["cur_temp"] = int(body[6:], base=16)
        return data

    @classmethod
    def process_get_thermostat_hold_response(self, body):
        data = {"msg_name": "GetHoldResponse"}
        if len(body) < 2:
            data.update({"error": "missing required/mandatory field"})
        else:
            data["hold_mode"] = self.tstatHoldModes.get(int(body[:2], base=16))
            try:
                data["hold_setpoint"] = int(body[2:4], base=16)
                data["hold_time_remaining"] = int(body[4:], base=16)
            except:
                pass
        return data

    @classmethod
    def process_get_thermostat_fan_mode_response(self, body):
        data = {"msg_name": "GetFanModeResponse"}
        if len(body) < 2:
            data.update({"error": "missing required/mandatory field"})
        else:
            data["fan_mode"] = self.tstatFanModes.get(int(body, base=16))
        return data

    @classmethod
    def process_get_thermostat_mode_response(self, body):
        data = {"msg_name": "GetThermostatModeResponse"}
        if len(body) < 10:
            data.update({"error": "missing required/mandatory field"})
        else:
            data["system_mode"] = self.tstatSystemModes.get(int(body, base=16))
        return data

    @classmethod
    def get_capabitities(self, capability_bitmap):
        capabilities = [
            self.capabilityBitmap.get(bit)
            for bit in range(0, 32)
            if (((1 << bit) & capability_bitmap) and self.capabilityBitmap.get(bit))
        ]
        print(capabilities)
        return capabilities

    @classmethod
    def get_ascii(self, value):
        ordinals = bytes.fromhex(value)
        return ordinals.decode("ascii")


class CTA2045Parser:
    basic = Basic()
    intermediate = Intermediate()

    @classmethod
    def get_data(self, data_packet: str):
        data = {}
        try:
            payload = data_packet[8:]
            if data_packet.startswith("0801"):
                data.update(self.basic.process_payload(payload))
            elif data_packet.startswith("0802"):
                data.update(self.intermediate.process_payload(payload))

            if "error" not in data:
                data["error"] = None
        except IndexError as Ex:
            data.update({"error": Ex})
        return data

    @classmethod
    def process_received_packet(self, incoming_packet: str):
        try:
            data = {}
            message = json.loads(incoming_packet.decode("utf-8"))
            _log.debug(f"{message=}")
            try:
                incoming_packet = message['SGD']['d']
            except KeyError:
                incoming_packet = message['d']
            location = max(incoming_packet.rfind('080100'), incoming_packet.rfind('080200'))
            assert location != -1
            data_packet = incoming_packet[location:]
            while data_packet:
                packet_len = 8 + 2 * int(data_packet[4:8], 16)
                packet = data_packet[:packet_len]
                message = self.get_data(packet)
                try:
                    data.update({message['msg_name']: message})
                except Exception as exc:
                    _log.error(f"could not update data with message: {exc=}")
                    return
                data_packet = data_packet[packet_len:]
        except AssertionError:
            _log.debug("invalid message received")
            return
        return data

    @classmethod
    def build_event_duration_message(cls, wh_mode: str, duration: int):
        """
        Return command to send to device over MQTT
        """
        duration_op_code = int(math.sqrt((duration / 2)))
        if duration_op_code > 0xFE:
            duration_op_code = 0xFF
        mode = BASIC_DR_APP_OP_CODES[WH_EVENT_STATE_MAP[wh_mode]]
        reserved = "00"
        payload_length = 0x02
        message = f"{BASIC_DR_APP_OP_CODES['BasicDrMessage']}{reserved}{payload_length:02X}{mode}{duration_op_code:02X}"
        return (message)
