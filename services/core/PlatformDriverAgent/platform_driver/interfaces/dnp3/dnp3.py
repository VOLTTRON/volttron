from .driver_wrapper import WrapperInterface, WrapperRegister
from .driver_wrapper import ImplementedRegister, RegisterValue
from typing import List, Optional, Dict

from dnp3_python.dnp3station.master_new import MyMasterNew

# TODO-developer: Your code here
# Add dependency as needed, and update in requirements
import json

import logging
import random
import sys

from datetime import datetime

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'))

_log = logging.getLogger(__name__)
_log.addHandler(stdout_stream)
_log.setLevel(logging.DEBUG)
_log.setLevel(logging.WARNING)
_log.setLevel(logging.ERROR)


# TODO-developer: Your code here
# Change the classname "UserDevelopRegister" as needed
class UserDevelopRegisterDnp3(WrapperRegister):
    # TODO-developer: Your code here
    def __init__(self, master_application, reg_def, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.master_application = kwargs['master_application']
        # self.reg_def = kwargs['reg_def']
        self.master_application = master_application
        self.reg_def = reg_def

    def get_register_value(self) -> RegisterValue:
        # TODO-developer: Your code here
        # Implement get-register-value logic here
        # Note: Keep the method name as it is including the signatures.
        # Use a helper method if needed.

        # EXAMPLE:
        # def get_register_value(self) -> RegisterValue:
        #    return _get_register_value_helper(url=self.driver_config.get("url"))
        # def _get_register_value_helper(self, url: str):
        #    ...

        #         print("silly implementation")
        # the url will be in the config file

        try:
            reg_def = self.reg_def
            group = int(reg_def.get("Group"))
            variation = int(reg_def.get("Variation"))
            index = int(reg_def.get("Index"))
            val = self._get_outstation_pt(self.master_application, group, variation, index)
            # val = str(val)

            if val is not None:
                return val
            else:
                _log.warning("dnp3 driver (master) couldn't collect data from the outstation.")
                raise ValueError(f"Returned invalid dnp3 data point {val}")  # do not publish invalid values
        except Exception as e:
            # print(f"!!!!!!!!!!!!!!!!!!!!{e}")
            _log.error(e)

            raise Exception(e)

    @staticmethod
    def _get_outstation_pt(master_application, group, variation, index) -> RegisterValue:
        """
        Core logic to retrieve register value by polling a dnp3 outstation
        Note: using def get_db_by_group_variation_index
        Returns
        -------

        """
        return_point_value = master_application.get_val_by_group_variation_index(group=group,
                                                                                 variation=variation,
                                                                                 index=index)
        return return_point_value

    def set_register_value(self, value, **kwargs) -> Optional[RegisterValue]:
        """
        TODO: docstring
        """
        try:
            reg_def = self.reg_def
            group = int(reg_def.get("Group"))
            variation = int(reg_def.get("Variation"))
            index = int(reg_def.get("Index"))

            val: Optional[RegisterValue]
            self._set_outstation_pt(self.master_application, group, variation, index, set_value=value)
            val = None

            return val
        except Exception as e:
            _log.error(e)
            _log.warning("dnp3 driver (master) couldn't set value for the outstation.")

    @staticmethod
    def _set_outstation_pt(master_application, group, variation, index, set_value) -> None:
        """
        Core logic to send point operate command to outstation
        Note: using def send_direct_point_command
        Returns None
        -------

        """
        master_application.send_direct_point_command(group=group, variation=variation, index=index,
                                                     val_to_set=set_value)


class Interface(WrapperInterface):
    # TODO-developer: Your code here
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.master_application = None

    # TODO-developer: Your code here
    # Register type configuration
    @staticmethod
    def pass_register_types(csv_config: dict, driver_config_in_json_config: List[dict],
                            register_type_list: List[ImplementedRegister] = None):
        """
        Note: based on the config.csv file.
        By default, assuming register points are dnp3-register type + (optional) heartbeat register
        """
        return [UserDevelopRegisterDnp3] * len(csv_config)

    @staticmethod
    def _create_master_station(driver_config: dict):
        """
        init a master station and later pass to registers

        Note: rely on XX.config json file convention, e.g.,
        "driver_config":
            {"master_ip": "0.0.0.0",
            "outstation_ip": "127.0.0.1",
            "master_id": 2,
            "outstation_id": 1,
            "port":  20000},

        Returns
        -------

        """

        master_application = MyMasterNew(
            masterstation_ip_str=driver_config.get("master_ip"),
            outstation_ip_str=driver_config.get("outstation_ip"),
            port=driver_config.get("port"),
            masterstation_id_int=driver_config.get("master_id"),
            outstation_id_int=driver_config.get("outstation_id"),
        )
        # master_application.start()
        return master_application

    def create_register(self, driver_config,
                        point_name,
                        data_type,
                        units,
                        read_only,
                        default_value,
                        description,
                        csv_config,
                        reg_def,
                        register_type, *args, **kwargs):
        def get_master_station():
            # Note: this a closure, since parameter driver_config is required.
            # (at current state) only create_register workflow should use it.
            if self.master_application:
                return self.master_application
            else:
                self.master_application = self._create_master_station(driver_config)
                return self.master_application

        master = get_master_station()
        master.start()

        register = UserDevelopRegisterDnp3(
            driver_config=driver_config,
            point_name=point_name,
            data_type=data_type,  # TODO: make it more clear in documentation
            units=units,
            read_only=read_only,
            default_value=default_value,
            description=description,
            csv_config=csv_config,
            reg_def=reg_def,
            master_application=master
        )
        return register

    @staticmethod
    def get_reg_point(register: ImplementedRegister):
        """
        Core logic for get_point
        Note: Can be used for vip-agent-mock testing
        """
        return register.get_register_value()

    @staticmethod
    def set_reg_point(register: ImplementedRegister, value_to_set: RegisterValue):
        """
        Core logic for set_point, i.e., _set_point without verification
        Note: Can be used for vip-agent-mock testing
        """
        set_pt_response = register.set_register_value(value=value_to_set)
        return set_pt_response
