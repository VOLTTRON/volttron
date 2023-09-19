# Ace IoT Solutions
"""
    Platform Driver interface implementation for rainforest eagle 200 gateway
"""

import logging
import requests

from platform_driver.interfaces import (
    BaseInterface,
    BaseRegister,
    BasicRevert,
    DriverInterfaceError,
)

_log = logging.getLogger("rainforest_eagle")


auth = None
macid = None
address = None

ZIGBEE_REGISTER_LIST = [
    "zigbee:CurrentSummationDelivered",
    "zigbee:CurrentSummationReceived",
    "zigbee:InstantaneousDemand",
]


class Register(BaseRegister):
    def __init__(self, name, units, description):
        super(Register, self).__init__(
            register_type="byte",
            read_only=True,
            pointName=name,
            units=units,
            description=description,
        )


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.power_meter = {}

    def configure(self, config_dict, register_config):
        global auth, macid, address
        _log.info(f"configuring rainforest gateway: {config_dict=} {register_config=}")

        username = config_dict["username"]
        password = config_dict["password"]
        auth = (username, password)
        macid = config_dict["macid"]
        address = config_dict["address"]

        self.power_meter = self.get_power_meter()

        if not self.power_meter:
            _log.error("Could not find connected power meter")
            return
        # query for variable values to build units and description for registers
        variable_list = self.get_variables_list(self.power_meter, ZIGBEE_REGISTER_LIST)
        for d in variable_list:
            # remove zigbee: prefix
            name = d["Name"][7:].lower()
            units = d["Units"]
            description = d["Description"]
            self.insert_register(Register(name, units, description))

        _log.info(f"Interface configuration complete. Found {variable_list=}")

    def get_power_meter(self) -> dict:
        self.device_list = self.get_device_list()
        for devices in self.device_list.values():
            for device in devices:
                if (
                    isinstance(device, dict)
                    and device["ModelId"] == "electric_meter"
                    and device["ConnectionStatus"] == "Connected"
                ):
                    _log.info(f"found active power meter {device}")
                    return device

    def get_point(self, point_name):
        return self.get_variable(self.power_meter, point_name)

    def get_variable(self, device, variable):
        _log.info(f"getting {variable} from {device}")
        command = f"""<Command>
                        <Name>device_query</Name>
                        <Format>JSON</Format>
                        <DeviceDetails>
                            <HardwareAddress>{device['HardwareAddress']}</HardwareAddress>
                        </DeviceDetails>
                        <Components>
                            <Component>
                                <Name>Main</Name>
                                <Variables>
                                    <Variable>
                                        <Name>{variable}</Name>
                                    </Variable>
                                </Variables>
                            </Component>
                        </Components>
                    </Command>
                    """

        result = requests.post(address, auth=auth, data=command)
        if result.status_code != requests.codes.ok:
            return str(result.status_code)
        _log.info(f"Queried device {device['Name']} for variable {variable}: {result=}")
        device_result = result.json()
        requested_values = device_result["Device"]["Components"]["Component"][
            "Variables"
        ]
        return requested_values["Variable"]

    def get_variables_list(self, device, var_list):
        returned_vars = []
        for var in var_list:
            returned_vars.append(self.get_variable(device, var))
        return returned_vars

    def get_device_list(self):
        # consider using dicttoxml to set up command as dictionary?
        command = """<Command>
                     <Name>device_list</Name>
                     <Format>JSON</Format>
                   </Command>"""
        result = requests.post(address, auth=auth, data=command)

        if result.status_code != requests.codes.ok:
            return str(result.status_code)

        device_list = result.json()["DeviceList"]
        return device_list

    def scrape_power_meter(self):
        values = {}
        for d in self.get_variables_list(self.power_meter, ZIGBEE_REGISTER_LIST):
            # remove zigbee: prefix
            name = d["Name"][7:].lower()
            if not d["Value"]:
                _log.warning(f"Variable {d['Name']} has no value. skipping")
                continue
            values[name] = d["Value"]

        _log.info(f"Scraped power meter: {values=}")
        return values

    def _set_point(self, point_name, value):
        pass

    def scrape_all(self):
        return self._scrape_all()

    def _scrape_all(self) -> dict:
        # scrape points
        result = self.scrape_power_meter()
        return result
