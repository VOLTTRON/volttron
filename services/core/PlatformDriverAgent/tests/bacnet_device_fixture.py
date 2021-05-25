from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.app import BIPSimpleApplication
from bacpypes.task import RecurringTask
from bacpypes.object import AnalogOutputObject, BinaryOutputObject
from bacpypes.service.device import LocalDeviceObject
from bacpypes.core import run

_debug = 0
_log = ModuleLogger(globals())

# test globals
test_av = None
test_bv = None
test_app = None

BACNET_SUBNET = "172.28.0.0/16"
BACNET_DEVICE_IP_ADDR = "172.28.5.1"
COOLING_VALVE_OUTPUT_COMMAND_OBJECT_ID = 3000107
GENERAL_EXHAUST_FAN_COMMAND_OBJECT_ID = 3000114


@bacpypes_debugging
# TODO: Extend class to have more parent classes so that we can add more integration tests; look in BACpypes repo for more sophisticated applications
class BacnetTestApplication(BIPSimpleApplication):
    pass


@bacpypes_debugging
class TestAnalogOutputValueTask(RecurringTask):
    def __init__(self, interval):
        if _debug:
            TestAnalogOutputValueTask._debug("__init__ %r", interval)
        RecurringTask.__init__(self, interval * 1000)

        self.interval = interval
        self.test_values = [1.1, 1.2, 1.3]

    def process_task(self):
        if _debug:
            TestAnalogOutputValueTask._debug("process_task")
        global test_av

        n = self.test_values.pop(0)
        self.test_values.append(n)
        if _debug:
            TestAnalogOutputValueTask._debug("    - next_value: %r", n)
        test_av.presentValue = n


@bacpypes_debugging
class TestBinaryOutputValueTask(RecurringTask):
    def __init__(self, interval):
        if _debug:
            TestBinaryOutputValueTask._debug("__init__ %r", interval)
        RecurringTask.__init__(self, interval * 1000)

        self.interval = interval
        self.test_values = [False, True]

    def process_task(self):
        if _debug:
            TestBinaryOutputValueTask._debug("process_task")
        global test_bv

        n = self.test_values.pop(0)
        self.test_values.append(n)
        if _debug:
            TestBinaryOutputValueTask._debug("    - next_value: %r", n)
        test_bv.presentValue = n


def main():
    global test_app, test_av, test_bv

    # make a device
    this_device = LocalDeviceObject(objectIdentifier=500, vendorIdentifier=15)
    if _debug:
        _log.debug("    - this_device: %r", this_device)

    # add device to test application
    address = BACNET_DEVICE_IP_ADDR
    testapp = BacnetTestApplication(this_device, address)

    # the objectIdentifier's object instance (i.e. second value in tuple) should match the value in the corresponding Index column of the BACnet Driver's registry config
    test_av = AnalogOutputObject(
        objectIdentifier=("analogOutput", COOLING_VALVE_OUTPUT_COMMAND_OBJECT_ID),
        objectName="Building/FCB.Local Application.CLG-O",
        presentValue=1.0,
        statusFlags=[0, 0, 0, 0],
    )
    _log.debug("    - test_av: %r", test_av)
    testapp.add_object(test_av)

    test_bv = BinaryOutputObject(
        objectIdentifier=("binaryOutput", GENERAL_EXHAUST_FAN_COMMAND_OBJECT_ID),
        objectName="Building/FCB.Local Application.GEF-C",
        presentValue="inactive",
        statusFlags=[0, 0, 0, 0],
    )
    _log.debug("    - test_bv: %r", test_bv)
    testapp.add_object(test_bv)

    # TODO: make a third object that supports COV so that we can test COV of BACnet driver

    # run tasks
    test_av_task = TestAnalogOutputValueTask(5)
    test_av_task.process_task()

    test_bv_task = TestBinaryOutputValueTask(5)
    test_bv_task.process_task()

    run(1.0)


if __name__ == "__main__":
    main()
