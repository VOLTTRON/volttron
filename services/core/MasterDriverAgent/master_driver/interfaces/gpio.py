# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

from services.core.MasterDriverAgent.master_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from gpiozero import OutputDevice, DigitalOutputDevice, DigitalInputDevice
from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero.pins.mock import MockFactory
from gpiozero.pins.native import NativeFactory
from ipaddress import ip_address as ip
import logging

_log = logging.getLogger(__name__)


class Interface(BasicRevert, BaseInterface):
    """
    Interface implementation for wrapping around the gpiozero library.
    """
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        # Use default pin factory.
        self.pin_factory = None
        self.config_dict = None
        self.driver_path = None
        # GPIO registers are of non-standard datatypes, so override existing register type dictionary
        self.registers = {
            ('output', False): [],
            ('digital_output', False): [],
            ('digital_input', True): []
        }

    def configure(self, config_dict, registry_config_str):
        """
        Parse driver configuration to establish the pin factory and remote address of the GPIO pins if provided.
        :param config_dict: Dictionary containing configuration information.
        :param registry_config_str: List of dictionaries containing point information used to establish registers.
        """
        self.config_dict = config_dict
        # Set Device Path for callbacks
        self.driver_path = config_dict.get("driver_path")

        # If a remote address is specified set the pin factory to PiGPIO using the address.
        if config_dict.get("remote_address"):
            try:
                ip(config_dict["remote_address"])
            except Exception as e:
                raise ValueError("Invalid value provided for 'remote_address,' a valid ip address is required.")
            # Try to set pin_factory and connect to the remote PiGPIO daemon.
            try:
                self.pin_factory = PiGPIOFactory(host=self.config_dict["remote_address"])
            except Exception as e:
                logging.warning("Failed to connect to PiGPIO daemon on remote device. Trying again...")
                # Try a second time to connect to the remote PiGPIO daemon.
                try:
                    self.pin_factory = PiGPIOFactory(host=self.config_dict["remote_address"])
                except:
                    raise IOError("Failed to connect to PiGPIO daemon on remote device.")
            if config_dict.get("pin_factory"):
                raise ValueError("If a remote address is specified, the PiGPIO factory must be used.")
        # Check if a valid pin factory is specified
        elif config_dict.get("pin_factory"):
            if config_dict["pin_factory"].lower() == "mock":
                self.pin_factory = MockFactory()
            elif config_dict["pin_factory"].lower() == "rpi.gpio":
                # This is the default pin factory.
                import RPi.GPIO
            elif config_dict["pin_factory"].lower() == "pigpio":
                self.pin_factory = PiGPIOFactory()
            elif config_dict["pin_factory"].lower() == "native":
                self.pin_factory = NativeFactory()
        # Parse registry config and create specified registers.
        self.parse_config(registry_config_str)

    def parse_config(self, registry_config_str):
        """
        The registry configuration csv is parsed and the specified registers are inserted.
        :param registry_config_str: List of dictionaries used to construct registers.
        """
        if not self.config_dict:
            return
        # Loop through register information and construct registers.
        for index, reg in enumerate(registry_config_str):
            # Check the values required for all device types.

            # Point name is required.
            if not reg.get("Point Name"):
                raise ValueError(
                    "Registry config entry {} did not provide a 'Point Name.'".format(index)
                )
                continue

            # Pin value is required,
            if not reg.get("Pin"):
                raise ValueError("Registry config entry {} did not provide a value for 'Pin.'")
                continue

            # Pin value must be a valid BroadCom gpio pin value.
            try:
                reg["Pin"] = int(reg["Pin"])
            except:
                raise ValueError(
                    "Registry config entry {} provided an invalid pin. A valid Broadcom pin number is required.".format(
                        index)
                )
                continue
            if int(reg["Pin"]) < 2 or int(reg["Pin"]) > 27:
                raise ValueError(
                    "Registry config entry {} provided an invalid pin. A valid Broadcom pin number is required.".format(
                        index)
                )
                continue

            # Check for optional arguments.

            # Notes and units are not required.
            description = reg.get('Notes', '')
            units = reg.get('Units', None)

            # Set empty optional configs to None
            if reg.get("Active High") == "":
                reg["Active High"] = None
            if reg.get("Initial Value") == "":
                reg["Initial Value"] = None
            if reg.get("Pull Up") == "":
                reg["Pull Up"] = None
            if reg.get("Bounce Time") == "":
                reg["Bounce Time"] = None
            if reg.get("Device Type") == "":
                reg["Device Type"] = None

            # Default setting for device type is GPIO, which is the broadest category supported.
            if not reg.get("Device Type"):
                reg["Device Type"] = "output"
                logging.warning("Registry config entry {} provided no 'Device Type,' default type 'output' used.")

            # Insert digital input GPIO registers.
            if reg["Device Type"] == "digital_input":
                # Validate bounce time config.
                if reg.get("Bounce Time") is None:
                    logging.warning(("Registry config entry {} provided no value for 'Bounce Time,' no bounce " + \
                                     "compensation will be performed.").format(index))
                else:
                    try:
                        reg["Bounce Time"] = float(reg["Bounce Time"])
                    except Exception as e:
                        raise ValueError(("Registry config entry {} provided invalid value for 'Bounce Time,' " + \
                                          "float is required").format(index))

                # Validate pull up and active high config.
                if not (reg.get("Pull Up") is None):
                    if str(reg["Pull Up"]).lower() != "true" and str(reg["Pull Up"]).lower() != "false":
                        raise ValueError(("Registry config entry {} provided invalid value for 'Pull Up,' " +
                                          "true or false is required").format(index))
                    else:
                        reg["Pull Up"] = (str(reg["Pull Up"]) == "true")
                if not (reg.get("Active High") is None):
                    if str(reg["Active High"]).lower() != "true" and str(reg["Active High"]).lower() != "false":
                        raise ValueError(("Registry config entry {} provided invalid value for 'Active High,' " +
                                          "true or false is required, value provided was {}").format(index, reg["Active High"]))
                    else:
                        reg["Active High"] = (str(reg["Active High"]) == "true")

                # Active high should only be specified if pull up is not.
                if not isinstance(reg.get("Pull Up"), bool) and not isinstance(reg.get("Active High"), bool):
                    logging.warning("Registry config entry {} provided no value for 'Pull Up,' the default is false"
                                    .format(index))
                if isinstance(reg.get("Active High"), bool) and isinstance(reg.get("Pull Up"), bool):
                    logging.warning(("Registry config entry {} specified both 'Active High' and 'Pull Up,' when " \
                                     "'Pull Up' is specified 'Active High' is ignored").format(index))
                    reg["Active High"] = None

                # Insert register.
                self.insert_register(DigitalInputRegister(self, reg["Point Name"], reg["Pin"], reg.get("Pull Up"),
                                                          reg.get("Active High"), reg.get("Bounce Time"),
                                                          pin_factory=self.pin_factory, units=units,
                                                          description=description))

            # Insert digital and generic output GPIO registers.
            elif reg["Device Type"] == "output" or reg["Device Type"] == "digital_output":
                # Validate configuration values.
                if reg.get("Active High") is None:
                    raise ValueError("Registry config entry {} provided no value for 'Active High.'".format(index))
                elif str(reg["Active High"]).lower() != "true" and str(reg["Active High"]).lower() != "false":
                    raise ValueError(("Registry config entry {} provided invalid value for 'Active High,' " + \
                                      "true or false is required").format(index))
                else:
                    reg["Active High"] = (str(reg["Active High"]).lower() == "true")

                if reg.get("Initial Value") is None:
                    logging.warning(("Registry config entry {} provided no value for 'Initial Value,' the default is" + \
                                     "false.").format(index))
                elif str(reg["Initial Value"]).lower() != "true" and str(reg["Initial Value"]).lower() != "false":
                    raise ValueError(("Registry config entry {} provided invalid value for 'Initial Value,' " + \
                                      "true or false is required").format(index))
                else:
                    reg["Initial Value"] = (str(reg["Initial Value"]) == "true")
                # Insert register.
                if reg["Device Type"] == "output":
                    self.insert_register(OutputRegister(reg["Point Name"], reg["Pin"], reg["Active High"],
                                                        reg["Initial Value"], pin_factory=self.pin_factory, units=units,
                                                        description=description))
                if reg["Device Type"] == "digital_output":
                    self.insert_register(DigitalOutputRegister(reg["Point Name"], reg["Pin"], reg["Active High"],
                                                               reg["Initial Value"], pin_factory=self.pin_factory,
                                                               units=units, description=description))

    def get_point(self, point_name):
        """
        Return the state of the specified GPIO point.
        :param point_name: The point name references the point to communicate with.
        """
        register = self.get_register_by_name(point_name)
        return register.get_state()

    def _set_point(self, point_name, value):
        """
        Set the state of the specified GPIO point, or perform action on GPIO point.
        :param point_name: The point name references the point to communicate with.
        :param value: Either a value to set the point to, or an action dictionary
        for performing more complex actions.
        """
        register = self.get_register_by_name(point_name)
        if not register:
            raise ValueError("Valid point name not provided.")
        # Invoke the action method of the register if 'value' is a dictionary.
        if isinstance(value, dict):
            return register.action(value)
        # If value is not a dictionary, the register needs to not be writable.
        elif not register.read_only:
            register._set_state(value)
        else:
            raise IOError("Cannot write to a point configured as read only.")

    def _scrape_all(self):
        """
        Return the most recent point values for all configured points.
        :return: Dictionary containing the most recent point values for all configured points.
        """
        result = {}
        # Get list of read only registers.
        read_registers = self.get_registers_by_type("digital_input", True)
        # Get list of writable registers.
        write_registers = self.get_registers_by_type("output", False) + self.get_registers_by_type("digital_output", False)
        # Combine register lists into a dictionary.
        for register in read_registers + write_registers:
            result[register.point_name] = register.get_state()
        return result


class GPIOregister(BaseRegister):
    """
    Parent GPIO register class containing common functions.
    :param reg_type: Type of register.
    :param read_only: Boolean describing if device is read only.
    :param pointName: Name of the point.
    :param units: Units of the point value.
    :param description: Description of the point.
    """
    def __init__(self, reg_type, read_only, pointName, units, description=''):
        self.point_name = pointName
        super(GPIOregister, self).__init__(reg_type, read_only, pointName, units, description=description)

    def get_state(self):
        """
        Return value of device.
        :return: Value of device.
        """
        return self.device.value

    def _set_state(self, value):
        """
        Set device value if not read only.
        :param value: Value to set device to.
        :return: None
        """
        if self.read_only:
            raise RuntimeError("Attempted write of read-only register {}".format(self.point_name))
        self.device.value = value

    def close(self):
        """
        Release pin, and remove the device.
        :return: None
        """
        self.device.close()


class DigitalInputRegister(GPIOregister):
    """
    Register to manage a digital input device.
    :param driver: Driver instance for publishing.
    :param pointName: Name of the point.
    :param pin: Broadcom pin the device is connected to.
    :param active_state: Whether the device is active when state is high or low.
    :param bounce_time: Number of seconds of bounce compensation to provide.
    :param pin_factory: Pin library to use for managing pins.
    :param units: Units of the point value.
    :param description: Description of the point.
    :return: None
    """
    def __init__(self, driver, pointName, pin, pull_up, active_state, bounce_time, pin_factory, units, description=''):
        # Set attributes
        self.driver = driver
        self.pin_factory = pin_factory
        self.pin = pin
        # Construct GPIO device.
        self.device = DigitalInputDevice(pin, pull_up, active_state, bounce_time, pin_factory=pin_factory)
        super(DigitalInputRegister, self).__init__("digital_input", True, pointName, units, description=description)

    def push_cov_to_master(self):
        """
        Helper function for performing a callback that publishes to the message bus.
        :return: None
        """
        self.driver.vip.pubsub.publish(peer="pubsub", topic="devices/"+self.driver.driver_path+"/"+self.point_name,
                                       message="Active.")

    def action(self, action_dictionary):
        """
        Parse action dictionary and perform specified action.
        :param action_dictionary: Dictionary containing action name and necessary parameters.
        :return: None
        """
        # Check action dictionary for key "action."
        if action_dictionary.get("action"):
            action = action_dictionary["action"]
            # Check if a valid action was provided.
            if action == "wait_for_active":
                # Check for valid "timeout" value
                if action_dictionary.get("timeout"):
                    if isinstance(action_dictionary["timeout"], float):
                        self.device.wait_for_active(action_dictionary["timeout"])
                    else:
                        raise ValueError("No valid value provided for key 'timeout,' float is required.")
                else:
                    logging.warning("No value provided for 'timeout,' process will wait indefinitely.")
                    self.device.wait_for_active(action_dictionary["timeout"])
            elif action == "wait_for_inactive":
                # Check for valid "timeout" value
                if action_dictionary.get("timeout"):
                    if isinstance(action_dictionary["timeout"], float):
                        self.device.wait_for_inactive(action_dictionary["timeout"])
                    else:
                        raise ValueError("No valid value provided for key 'timeout,' float is required.")
                else:
                    logging.warning("No value provided for 'timeout,' process will wait indefinitely.")
                    self.device.wait_for_active(action_dictionary["timeout"])
            elif action == "active_time":
                return self.device.active_time
            elif action == "inactive_time":
                return self.device.inactive_time
            elif action == "when_activated":
                # When activated publish value to topic
                self.device.when_activated = self.push_cov_to_master
            elif action == "when_deactivated":
                # When activated publish value to topic
                self.device.when_deactivated = self.push_cov_to_master
            elif action == "drive_high":
                self.pin_factory.pin(self.pin).drive_high()
            elif action == "drive_low":
                self.pin_factory.pin(self.pin).drive_low()
            else:
                raise ValueError("The action dictionary does not contain a valid action.")
        else:
            raise ValueError("The action dictionary does not contain a valid action.")


class OutputRegister(GPIOregister):
    """
    Register to manage an output device.
    :param pointName: Name of the point.
    :param pin: Broadcom pin the device is connected to.
    :param active_high: Whether the device is active when state is high or low.
    :param initial_value: Whether the device will keep its initial state.
    :param pin_factory: Pin library to use for managing pins.
    :param units: Units of the point value.
    :param description: Description of the point.
    :return: None
    """
    def __init__(self, pointName, pin, active_high, initial_value, pin_factory, units, description=''):
        # Construct GPIO device.
        self.device = OutputDevice(pin, active_high, initial_value, pin_factory=pin_factory)
        super(OutputRegister, self).__init__("output", False, pointName, units, description=description)

    def action(self, action_dictionary):
        """
        Parse action dictionary and perform specified action.
        :param action_dictionary: Dictionary containing action name and necessary parameters.
        :return: Boolean or None
        """
        # Check action dictionary for key "action."
        if action_dictionary.get("action"):
            action = action_dictionary["action"]
            # Check if a valid action was provided.
            if action == "off":
                self.device.off()
                return
            elif action == "on":
                self.device.on()
                return
            elif action == "toggle":
                self.device.toggle()
                return
            elif action == "get_active_high":
                return self.device.active_high
            elif action == "set_active_high":
                # Check if a valid value for "active_high" was provided, "active_high" must be a bool.
                if action_dictionary.get("active_high") is not None:
                    if action_dictionary["active_high"].lower() == "true" or action_dictionary["active_high"].lower() == "false":
                        self.device.active_high = action_dictionary["active_high"] == "true"
                    else:
                        raise ValueError("Invalid value assigned to key 'active_high' in the action dictionary, true " +
                                         "or false is required.")
                else:
                    raise ValueError("No value assigned to key 'active_high' in the action dictionary, true or false " +
                                     "is required.")
            else:
                raise ValueError("The action dictionary does not contain a valid action.")
        else:
            raise ValueError("The action dictionary does not contain a valid action.")


class DigitalOutputRegister(GPIOregister):
    """
    Register to manage a digital output device.
    :param pointName: Name of the point.
    :param pin: Broadcom pin the device is connected to.
    :param active_high: Whether the device is active when state is high or low.
    :param initial_value: Whether the device will keep its initial state.
    :param pin_factory: Pin library to use for managing pins.
    :param units: Units of the point value.
    :param description: Description of the point.
    :return: None
    """
    def __init__(self, pointName, pin, active_high, initial_value, pin_factory, units, default_value=None, description=''):
        # Construct GPIO device.
        self.device = DigitalOutputDevice(pin, active_high, initial_value, pin_factory=pin_factory)
        super(DigitalOutputRegister, self).__init__("digital_output", False, pointName, units, description=description)

    def action(self, action_dictionary):
        """
        Parse action dictionary and perform specified action.
        :param action_dictionary: Dictionary containing action name and necessary parameters.
        :return: Boolean or None
        """
        # Check action dictionary for key "action."
        if action_dictionary.get("action"):
            action = action_dictionary["action"]
            # Check if a valid action was provided.
            if action == "off":
                self.device.off()
            elif action == "on":
                self.device.on()
            elif action == "toggle":
                self.device.toggle()
            elif action == "blink":
                # Check for valid value for "on_time," the number of seconds on.
                if action_dictionary.get("on_time"):
                    if not isinstance(action_dictionary["on_time"], float):
                        raise ValueError("Invalid value provided for key 'on_time' in the action dictionary, float " +
                                         "is required.")
                    # Check for valid value for "off_time," the number of seconds off.
                    if action_dictionary.get("off_time"):
                        if not isinstance(action_dictionary["off_time"], float):
                            raise ValueError( "Invalid value provided for key 'off_time' in the action dictionary, " +
                                              "float is required.")
                        # Check for valid value for "number_of_blinks," the number of times to blink.
                        if action_dictionary.get("number_of_blinks"):
                            if not isinstance(action_dictionary["number_of_blinks"], int):
                                raise ValueError("Invalid value provided for key 'number_of_blinks' in the action " +
                                                 "dictionary, int is required.")
                            # Check for valid value for "background," whether blinking is performed in the background or
                            # foreground.
                            if action_dictionary.get("background"):
                                if not isinstance(action_dictionary["background"], bool):
                                    raise ValueError("Invalid value provided for key 'background,' true or false is " +
                                                     "required.")
                            else:
                                logging.warning("No value provided for key 'background,' the default is true.")
                        else:
                            logging.warning("No value provided for key 'number_of_blinks' in the action dictionary, " +
                                            "default is forever.")
                    else:
                        logging.warning("No value provided for key 'off_time' in the action dictionary, default " +
                                        "value is 1 second.")
                else:
                    logging.warning("No value provided for key 'on_time' in the action dictionary, default value is " +
                                    "is 1 second.")
                self.device.blink(action_dictionary.get("on_time"), action_dictionary.get("off_time"),
                                  action_dictionary.get("number_of_blinks"), action_dictionary.get("background"))
            elif action == "get_active_high":
                return self.device.active_high
            elif action == "set_active_high":
                # Check if a valid value for "active_high" was provided, "active_high" must be a bool.
                if action_dictionary.get("active_high") is not None:
                    if action_dictionary["active_high"].lower() == "true" or action_dictionary["active_high"].lower() == "false":
                        self.device.active_high = action_dictionary["active_high"] == "true"
                    else:
                        raise ValueError("Invalid value assigned to key 'active_high' in the action dictionary, true " +
                                         "or false is required.")
                else:
                    raise ValueError("No value assigned to key 'active_high' in the action dictionary, true or false " +
                                     "is required.")
            else:
                raise ValueError("The action dictionary does not contain a valid action.")
        else:
            raise ValueError("The action dictionary does not contain a valid action.")
