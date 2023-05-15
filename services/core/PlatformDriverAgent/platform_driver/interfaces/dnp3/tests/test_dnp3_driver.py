import pytest
import gevent
import logging
import time
import csv
import json
from pathlib import Path
import random

from services.core.PlatformDriverAgent.platform_driver.interfaces. \
    dnp3 import UserDevelopRegisterDnp3
from pydnp3 import opendnp3
from services.core.PlatformDriverAgent.platform_driver.interfaces. \
    dnp3.dnp3 import Interface as DNP3Interface

from dnp3_python.dnp3station.master_new import MyMasterNew
from dnp3_python.dnp3station.outstation_new import MyOutStationNew

import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


class TestDummy:
    """
    Dummy test to check pytest setup
    """

    def test_dummy(self):
        print("I am a silly dummy test.")


@pytest.fixture(
    scope="module"
)
def outstation_app(request):
    """
    outstation using default configuration (including default database)
    Note: since outstation cannot shut down gracefully,
    outstation_app fixture need to in "module" scope to prevent interrupting pytest during outstation shut-down
    """
    # Note: allow parsing argument to fixture change port number using `request.param`
    try:
        port = request.param
    except AttributeError:
        port = 20000
    outstation_appl = MyOutStationNew(port=port)  # Note: using default port 20000
    outstation_appl.start()
    # time.sleep(3)
    yield outstation_appl
    # clean-up
    outstation_appl.shutdown()


@pytest.fixture(
    # scope="module"
)
def master_app(request):
    """
    master station using default configuration
    Note: outstation needs to exist first to make connection.
    """

    # Note: allow parsing argument to fixture change port number using `request.param`
    try:
        port = request.param
    except AttributeError:
        port = 20000
    # Note: using default port 20000,
    # Note: using small "stale_if_longer_than" to force update
    master_appl = MyMasterNew(port=port, stale_if_longer_than=0.1)
    master_appl.start()
    # Note: add delay to prevent conflict
    # (there is a delay when master shutdown. And all master shares the same config)
    time.sleep(1)
    yield master_appl
    # clean-up
    master_appl.shutdown()
    time.sleep(1)


class TestStation:
    """
    Testing the underlying pydnp3 package station-related fuctions.
    """

    def test_station_init(self, master_app, outstation_app):
        # master_app = MyMasterNew()
        # master_app.start()
        driver_wrapper_init_arg = {'driver_config': {}, 'point_name': "", 'data_type': "", 'units': "", 'read_only': ""}
        UserDevelopRegisterDnp3(master_application=master_app, reg_def={},
                                **driver_wrapper_init_arg)

    def test_station_get_val_analog_input_float(self, master_app, outstation_app):

        # outstation update with values
        analog_input_val = [1.2454, 33453.23, 45.21]
        for i, val_update in enumerate(analog_input_val):
            outstation_app.apply_update(opendnp3.Analog(value=val_update,
                                                        flags=opendnp3.Flags(24),
                                                        time=opendnp3.DNPTime(3094)),
                                        index=i)
        # Note: group=30, variation=6 is AnalogInputFloat
        for i, val_update in enumerate(analog_input_val):
            val_get = master_app.get_val_by_group_variation_index(group=30, variation=6, index=i)
            # print(f"===val_update {val_update}, val_get {val_get}")
            assert val_get == val_update

        time.sleep(1)  # add delay buffer to pass the "stale_if_longer_than" checking statge

        # outstation update with random values
        analog_input_val_random = [random.random() for i in range(3)]
        for i, val_update in enumerate(analog_input_val_random):
            outstation_app.apply_update(opendnp3.Analog(value=val_update),
                                        index=i)
        # Note: group=30, variation=6 is AnalogInputFloat
        for i, val_update in enumerate(analog_input_val_random):
            val_get = master_app.get_val_by_group_variation_index(group=30, variation=6, index=i)
            # print(f"===val_update {val_update}, val_get {val_get}")
            assert val_get == val_update

    def test_station_set_val_analog_input_float(self, master_app, outstation_app):

        # outstation update with values
        analog_output_val = [1.2454, 33453.23, 45.21]
        for i, val_to_set in enumerate(analog_output_val):
            master_app.send_direct_point_command(group=40, variation=4, index=i,
                                                 val_to_set=val_to_set)
        # Note: group=40, variation=4 is AnalogOutFloat
        for i, val_to_set in enumerate(analog_output_val):
            val_get = master_app.get_val_by_group_variation_index(group=40, variation=4, index=i)
            # print(f"===val_update {val_update}, val_get {val_get}")
            assert val_get == val_to_set

        time.sleep(1)  # add delay buffer to pass the "stale_if_longer_than" checking statge

        # outstation update with random values
        analog_output_val_random = [random.random() for i in range(3)]
        for i, val_to_set in enumerate(analog_output_val_random):
            master_app.send_direct_point_command(group=40, variation=4, index=i,
                                                 val_to_set=val_to_set)
        # Note: group=40, variation=4 is AnalogOutFloat
        for i, val_to_set in enumerate(analog_output_val_random):
            val_get = master_app.get_val_by_group_variation_index(group=40, variation=4, index=i)
            # print(f"===val_update {val_update}, val_get {val_get}")
            assert val_get == val_to_set


@pytest.fixture
def dnp3_inherit_init_args(csv_config, driver_config_in_json_config):
    """
    args required for parent class init (i.e., class WrapperRegister)
    """
    args = {'driver_config': driver_config_in_json_config,
            'point_name': "",
            'data_type': "",
            'units': "",
            'read_only': ""}
    return args


@pytest.fixture
def driver_config_in_json_config():
    """
    associated with `driver_config` in driver-config.config (json-like file)
                    user inputs are put here, e.g., IP address, url, etc.
    """
    json_path = Path("./testing_data/udd-Dnp3.config")
    json_path = Path(TEST_DIR, json_path)
    with open(json_path) as json_f:
        driver_config = json.load(json_f)
    k = "driver_config"
    return {k: driver_config.get(k)}


@pytest.fixture
def csv_config():
    """
    associated with the whole driver-config.csv file
    """
    csv_path = Path("./testing_data/udd-Dnp3.csv")
    csv_path = Path(TEST_DIR, csv_path)
    with open(csv_path) as f:
        reader = csv.DictReader(f, delimiter=',')
        csv_config = [row for row in reader]

    return csv_config


@pytest.fixture
def reg_def_dummy():
    """
    register definition, row of csv config file
    """
    # reg_def = {'Point Name': 'AnalogInput_index0', 'Volttron Point Name': 'AnalogInput_index0',
    #            'Group': '30', 'Variation': '6', 'Index': '0', 'Scaling': '1', 'Units': 'NA',
    #            'Writable': 'FALSE', 'Notes': 'Double Analogue input without status'}
    reg_def = {'Point Name': 'pn', 'Volttron Point Name': 'pn',
               'Group': 'int', 'Variation': 'int', 'Index': 'int', 'Scaling': '1', 'Units': 'NA',
               'Writable': 'NA', 'Notes': ''}
    return reg_def


class TestDNPRegister:
    """
    Tests for UserDevelopRegisterDnp3 class

    init

    get_register_value
        analog input float
        analog input int
        binary input
    """

    def test_init(self, master_app, csv_config, dnp3_inherit_init_args):
        for reg_def in csv_config:
            UserDevelopRegisterDnp3(master_application=master_app,
                                    reg_def=reg_def,
                                    **dnp3_inherit_init_args
                                    )

    def test_get_register_value_analog_float(self, outstation_app, master_app, csv_config,
                                             dnp3_inherit_init_args, reg_def_dummy):

        # dummy test variable
        analog_input_val = [445.33, 1123.56, 98.456] + [random.random() for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 30, variation = 6 is AnalogInputFloat
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(analog_input_val)):
            reg_def["Group"] = "30"
            reg_def["Variation"] = "6"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # outstation update values
        for i, val_update in enumerate(analog_input_val):
            outstation_app.apply_update(opendnp3.Analog(value=val_update), index=i)

        # verify: driver read value
        for i, (val_update, csv_row) in enumerate(zip(analog_input_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            val_get = dnp3_register.get_register_value()
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_update

    def test_get_register_value_analog_int(self, outstation_app, master_app, csv_config,
                                           dnp3_inherit_init_args, reg_def_dummy):

        # dummy test variable
        analog_input_val = [345, 1123, 98] + [random.randint(1, 100) for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 30, variation = 1 is AnalogInputInt32
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(analog_input_val)):
            reg_def["Group"] = "30"
            reg_def["Variation"] = "1"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # outstation update values
        for i, val_update in enumerate(analog_input_val):
            outstation_app.apply_update(opendnp3.Analog(value=val_update), index=i)

        # verify: driver read value
        for i, (val_update, csv_row) in enumerate(zip(analog_input_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            val_get = dnp3_register.get_register_value()
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_update

    def test_get_register_value_binary(self, outstation_app, master_app, csv_config,
                                       dnp3_inherit_init_args, reg_def_dummy):

        # dummy test variable
        binary_input_val = [True, False, True] + [random.choice([True, False]) for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 1, variation = 2 is BinaryInput
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(binary_input_val)):
            reg_def["Group"] = "1"
            reg_def["Variation"] = "2"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # outstation update values
        for i, val_update in enumerate(binary_input_val):
            outstation_app.apply_update(opendnp3.Binary(value=val_update), index=i)

        # verify: driver read value
        for i, (val_update, csv_row) in enumerate(zip(binary_input_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            val_get = dnp3_register.get_register_value()
            # print(f"=========== i {i}, val_get {val_get}, val_update {val_update}")
            assert val_get == val_update


class TestDNP3RegisterControlWorkflow:

    def test_set_register_value_analog_float(self, outstation_app, master_app, csv_config,
                                             dnp3_inherit_init_args, reg_def_dummy):

        # dummy test variable
        # Note: group=40, variation=4 is AnalogOutputDoubleFloat
        output_val = [343.23, 23.1109, 58.2] + [random.random() for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 1, variation = 2 is BinaryInput
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(output_val)):
            reg_def["Group"] = "40"
            reg_def["Variation"] = "4"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # master set values
        for i, (val_set, csv_row) in enumerate(zip(output_val, reg_defs)):
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            dnp3_register.set_register_value(value=val_set)

        # verify: driver read value
        for i, (val_set, csv_row) in enumerate(zip(output_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            val_get = dnp3_register.get_register_value()
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_set

    def test_set_register_value_analog_int(self, outstation_app, master_app, csv_config,
                                           dnp3_inherit_init_args, reg_def_dummy):

        # dummy test variable
        # Note: group=40, variation=4 is AnalogOutputDoubleFloat
        output_val = [45343, 344, 221] + [random.randint(1, 1000) for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 1, variation = 2 is BinaryInput
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(output_val)):
            reg_def["Group"] = "40"
            reg_def["Variation"] = "1"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # master set values
        for i, (val_set, csv_row) in enumerate(zip(output_val, reg_defs)):
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            dnp3_register.set_register_value(value=val_set)

        # verify: driver read value
        for i, (val_set, csv_row) in enumerate(zip(output_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            val_get = dnp3_register.get_register_value()
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_set

    def test_set_register_value_binary(self, outstation_app, master_app, csv_config,
                                       dnp3_inherit_init_args, reg_def_dummy):

        # dummy test variable
        # Note: group=40, variation=4 is AnalogOutputDoubleFloat
        output_val = [True, False, True] + [random.choice([True, False]) for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 1, variation = 2 is BinaryInput
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(output_val)):
            reg_def["Group"] = "10"
            reg_def["Variation"] = "2"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # master set values
        for i, (val_set, csv_row) in enumerate(zip(output_val, reg_defs)):
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            dnp3_register.set_register_value(value=val_set)

        # verify: driver read value
        for i, (val_set, csv_row) in enumerate(zip(output_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            val_get = dnp3_register.get_register_value()
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_set


class TestDNP3InterfaceNaive:

    def test_init(self):
        pass
        dnp3_interface = DNP3Interface()

    def test_get_reg_point(self, outstation_app, master_app, csv_config,
                           dnp3_inherit_init_args, reg_def_dummy):
        # dummy test variable
        analog_input_val = [445.33, 1123.56, 98.456] + [random.random() for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 30, variation = 6 is AnalogInputFloat
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(analog_input_val)):
            reg_def["Group"] = "30"
            reg_def["Variation"] = "6"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        # outstation update values
        for i, val_update in enumerate(analog_input_val):
            outstation_app.apply_update(opendnp3.Analog(value=val_update), index=i)

        # verify: driver read value
        dnp3_interface = DNP3Interface()
        for i, (val_update, csv_row) in enumerate(zip(analog_input_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )

            val_get = dnp3_interface.get_reg_point(register=dnp3_register)
            # print("======== dnp3_register.value", dnp3_register.value)
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_update

    def test_set_reg_point(self, outstation_app, master_app, csv_config,
                           dnp3_inherit_init_args, reg_def_dummy):
        # dummy test variable
        analog_output_val = [445.33, 1123.56, 98.456] + [random.random() for i in range(3)]

        # dummy reg_def (csv config row)
        # Note: group = 30, variation = 6 is AnalogInputFloat
        reg_def = reg_def_dummy
        reg_defs = []
        for i in range(len(analog_output_val)):
            reg_def["Group"] = "40"
            reg_def["Variation"] = "4"
            reg_def["Index"] = str(i)
            reg_defs.append(reg_def.copy())  # Note: Python gotcha, mutable don't evaluate til the end of the loop.

        dnp3_interface = DNP3Interface()

        # dnp3_interface update values
        for i, (val_update, csv_row) in enumerate(zip(analog_output_val, reg_defs)):
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )
            dnp3_interface.set_reg_point(register=dnp3_register, value_to_set=val_update)

        # verify: driver read value

        for i, (val_update, csv_row) in enumerate(zip(analog_output_val, reg_defs)):
            # print(f"====== reg_defs {reg_defs}, analog_input_val {analog_input_val}")
            dnp3_register = UserDevelopRegisterDnp3(master_application=master_app,
                                                    reg_def=csv_row,
                                                    **dnp3_inherit_init_args
                                                    )

            val_get = dnp3_interface.get_reg_point(register=dnp3_register)
            # print("======== dnp3_register.value", dnp3_register.value)
            # print("===========val_get, val_update", val_get, val_update)
            assert val_get == val_update
