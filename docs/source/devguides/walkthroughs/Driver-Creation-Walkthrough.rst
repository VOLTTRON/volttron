.. _DriverCreationWalkthrough:

Volttron Drivers Overview
=========================

In order for Volttron agents to gather data from a device or to set device values, agents send requests to the Master
Driver Agent to read or set points. The Master Driver Agent then sends these requests on to the appropriate driver for
interfacing with that device based on the topic specified in the request and the configuration of the Master Driver.
Drivers provide an interface between the device and the master driver by implementing portions of the devices' protocols
needed to serve the functions of setting and reading points.

As a demonstration of developing a driver, a driver can be made to read and set points in a CSV file. This driver will
only differ from a real device driver in terms of the specifics of the protocol.

Create a Driver and Register class
==================================

When a new driver configuration is added to the Master Driver, the Master Driver will look for a file in its interfaces
directory (services/core/MasterDriverAgent/master_driver/interfaces) that shares the name of the value specified by
"driver_type" in the configuration file. For the CSV Driver, create a file named csvdriver.py in that directory.

::

    ├── master_driver
    │   ├── agent.py
    │   ├── driver.py
    │   ├── __init__.py
    │   ├── interfaces
    │   │   ├── __init__.py
    │   │   ├── bacnet.py
    |   |   ├── csvdriver.py
    │   │   └── modbus.py
    │   └── socket_lock.py
    ├── master-driver.agent
    └── setup.py

Interface Basics
----------------
A complete interface consists of two parts: the interface class and one or more register classes.


Interface Class Skeleton
~~~~~~~~~~~~~~~~~~~~~~~~
When the Master Driver processes a driver configuration file, it creates an instance of the interface class found in the
interface file (such as the one we've just created). The interface class is responsible for managing the communication
between the Volttron Platform, and the device. Each device has many registers which hold the values Volttron agents are
interested in, so generally the interface manages reading and writing to and from a device's registers. At a minimum,
the interface class should be configurable, be able to read and write registers, as well as read all registers with a
single request. First create the csv interface class boilerplate.

.. code-block:: python

    class Interface(BasicRevert, BaseInterface):
        def __init__(self, **kwargs):
            super(Interface, self).__init__(**kwargs)

        def configure(self, config_dict, registry_config_str):
            pass

        def get_point(self, point_name):
            pass

        def _set_point(self, point_name, value):
            pass

        def _scrape_all(self):
            pass

This class should inherit from the BaseInterface, and at a minimum implement the configure, get_point, set_point, and
scrape_all methods.

.. Note:: In some sense, drivers are sub-agents running under the same process as the Master Driver. They should be instantiated following the agent pattern, so a function to handle configuration and create the Driver object has been included.

Register Class Skeleton
~~~~~~~~~~~~~~~~~~~~~~~
The interface needs some information specifying the communication for each register on the device. For each different
type of register, a register class should be defined, which will help identify individual registers, and determine how
to communicate with them. Our CSV driver will be fairly basic, with one kind of "register", which will be a column in
a CSV file, however other drivers may require many kinds of registers; For instance, the Modbus protocol driver has
registers which store data in byte sized chunks, and registers which store individual bits, therefore the Modbus driver
has bit and byte registers.

For the CSV driver, create the register class boilerplate:

.. code-block:: python

    class CsvRegister(BaseRegister):
        def __init__(self, csv_path, read_only, pointName, units, reg_type,
                     default_value=None, description=''):
            super(CsvRegister, self).__init__("byte", read_only, pointName, units, description=description)

This class should inherit from the BaseRegister. The class should keep register metadata, and depending upon the
requirements of the protocol/device, may perform the communication.

The BACNet and Modbus drivers may be used as examples of more specific implementations. For the purpose of this
demonstration, writing and reading points will be done in the register, however, this may not always be the case (as in
the case of the BACNet driver).

Filling out the Interface class
-------------------------------
The CSV interface will be writing to and reading from a CSV file, so the device configuration should include a path
specifying a CSV file to use as the "device". The CSV "device: path value is set at the beginning of the agent loop
which runs the configure method when the Master Driver starts. Since this Driver is for demonstration, we'll create the
CSV with some default values if the configured path doesn't exist. The CSV device will consist of 2 columns, "Point
Name" specifying the name of the register, and "Point Value", the current value of the register.

.. code-block:: python


    _log = logging.getLogger(__name__)

    CSV_FIELDNAMES = ["Point Name", "Point Value"]
    CSV_DEFAULT = [
        {
            "Point Name": "test1",
            "Point Value": 0
        },
        {
            "Point Name": "test2",
            "Point Value": 1
        },
        {
            "Point Name": "test3",
            "Point Value": "testpoint"
        }
    ]
    type_mapping = {"string": str,
                    "int": int,
                    "integer": int,
                    "float": float,
                    "bool": bool,
                    "boolean": bool}

    class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.csv_path = None

    def configure(self, config_dict, registry_config_str):
        self.csv_path = config_dict.get("csv_path", "csv_device.csv")
        if not os.path.isfile(self.csv_path):
            _log.info("Creating csv 'device'")
            with open(self.csv_path, "w+") as csv_device:
                writer = DictWriter(csv_device, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                writer.writerows(CSV_DEFAULT)
        self.parse_config(registry_config_str)

At the end of the configuration method, the Driver parses the registry configuration. The registry configuration is
a csv which is used to tell the Driver which register the user wishes to communicate with, and includes a few meta-data
values about each register, such as whether the register can be written to, if the register value uses a specific
measurement unit, etc. After each register entry is parsed from the registry config, a register is added to the driver's
list of active registers.

.. code-block:: python

    def parse_config(self, config_dict):
        if config_dict is None:
            return

        for index, regDef in enumerate(config_dict):
            # Skip lines that have no point name yet
            if not regDef.get('Point Name'):
                continue

            read_only = regDef.get('Writable', "").lower() != 'true'
            point_name = regDef.get('Volttron Point Name')
            if not point_name:
                point_name = regDef.get("Point Name")
            if not point_name:
                raise ValueError("Registry config entry {} did not have a point name or volttron point name".format(
                    index))
            description = regDef.get('Notes', '')
            units = regDef.get('Units', None)
            default_value = regDef.get("Default Value", "").strip()
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            reg_type = type_mapping.get(type_name, str)

            register = CsvRegister(
                self.csv_path,
                read_only,
                point_name,
                units,
                reg_type,
                default_value=default_value,
                description=description)

            if default_value is not None:
                self.set_default(point_name, register.value)

            self.insert_register(register)

Since the driver's registers will be doing the work of parsing the registers, the interface only needs to select the
correct register to read from or write to, and instruct the register to perform the corresponding unit of work.

.. code-block:: python

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.get_state()

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError("Trying to write to a point configured read only: " + point_name)
        register.set_state(value)
        return register.get_state()

    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            result[register.point_name] = register.get_state()
        return result

Writing the Register class
--------------------------
The CSV driver's register class is responsible for parsing the CSV, reading the corresponding rows to return the
register's current value and writing updated values into the CSV for the register. On a device which communicates via
a protocol such as Modbus, the same units of work would be done, but using pymodbus to perform the reads and writes.
Here, Python's CSV library will be used as our "protocol implementation".

The Register class determines which file to read based on values passed from the Interface class.

.. code-block:: python

    class CsvRegister(BaseRegister):
        def __init__(self, csv_path, read_only, pointName, units, reg_type,
                     default_value=None, description=''):
            super(CsvRegister, self).__init__("byte", read_only, pointName, units,
                                              description=description)
            self.csv_path = csv_path

To find its value, the register will read the CSV file, iterate over each row until a row with the point name the same
as the register name, at which point it extracts the point value, and returns it. The register should be written to
handle problems which may occur, such as no correspondingly named row being present in the CSV file.

.. code-block:: python

    def get_state(self):
        if os.path.isfile(self.csv_path):
            with open(self.csv_path, "r") as csv_device:
                reader = DictReader(csv_device)
                for point in reader:
                    if point.get("Point Name") == self.point_name:
                        point_value = point.get("Point Value")
                        if not point_value:
                            raise RuntimeError("Point {} not set on CSV Device".format(self.point_name))
                        else:
                            return point_value
            raise RuntimeError("Point {} not found on CSV Device".format(self.point_name))
        else:
            raise RuntimeError("CSV device at {} does not exist".format(self.csv_path))

Likewise to overwrite an existing value, the register will iterate over each row until the point name matches the
register name, saving the output as it goes. When it finds the correct row, it instead saves the output updated with the
new value, then continues on. Finally it writes the output back to the csv.

.. code-block:: python

    def set_state(self, value):
        _log.info("Setting state for {} on CSV Device".format(self.point_name))
        field_names = []
        points = []
        found = False
        with open(self.csv_path, "r") as csv_device:
            reader = DictReader(csv_device)
            field_names = reader.fieldnames
            for point in reader:
                if point["Point Name"] == self.point_name:
                    found = True
                    point_copy = point
                    point_copy["Point Value"] = value
                    points.append(point_copy)
                else:
                    points.append(point)

        if not found:
            raise RuntimeError("Point {} not found on CSV Device".format(self.point_name))
        else:
            with open(self.csv_path, "w") as csv_device:
                writer = DictWriter(csv_device, fieldnames=field_names)
                writer.writeheader()
                writer.writerows([dict(row) for row in points])
        return self.get_state()

At this point, we should be able to scrape the CSV device using the Master Driver, and set points using the actuator.

Creating Driver Configurations
------------------------------
The configuration files for the CSV driver are very simple, but in general, the device configuration should specify
the parameters which the interface requires to communicate with the device, and the registry configuration contains
rows which correspond to registers, and specifies their usage.

Here's the driver configuration for the CSV driver:

.. code-block:: json

    {
        "driver_config": {"csv_path": "csv_driver.csv"},
        "driver_type": "csvdriver",
        "registry_config":"config://csv_registers.csv",
        "interval": 30,
        "timezone": "UTC"
    }

.. Note:: the "driver_type" value must match the name of the driver's python file, as this is what the Master Driver will look for when searching for the correct interface.

And here's the registry configuration:

.. csv-table::

    Volttron Point Name,Point Name,Writable
    test1,test1,true
    test2,test2,true
    test3,test3,true

The BACNet and Modbus driver docs and example configurations can be used to compare these configurations to more complex
configurations.

Testing your driver
===================
To test the driver's scrape all functionality, one can install a ListenerAgent and Master Driver with the driver's
configurations, and run them. To do so for the CSV driver using the configurations above: activate the Volttron
environment start the platform, tail the platform's log file, then try the following:

    | python scripts/install-agent.py -s examples/ListenerAgent
    | python scripts/install-agent.py -s services/core/MasterDriverAgent -c
        services/core/MasterDriverAgent/master-driver.agent
    | vctl config store platform.driver devices/<campus>/<building>/csv_driver <path to driver configuration>
    | vctl config store platform.driver <registry config path from driver configuration> <path to registry configuration>

.. Note:: "vctl config list platform.driver" will list device and registry configurations stored for the master driver and "vctl config delete platform.driver <config in configs list>" can be used to remove a configuration entry - these commands are very useful for debugging

After the Master Driver starts, the driver's output should appear in the logs at regular intervals based on the Master
Driver's configuration.
Here is some sample CSV driver output:

    | 2019-11-15 10:32:00,010 (listeneragent-3.3 22996) listener.agent INFO: Peer: pubsub, Sender: platform.driver:, Bus:
    | , Topic: devices/pnnl/isb1/csv_driver/all, Headers: {'Date': '2019-11-15T18:32:00.001360+00:00', 'TimeStamp':
    | '2019-11-15T18:32:00.001360+00:00', 'SynchronizedTimeStamp': '2019-11-15T18:32:00.000000+00:00',
    | 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
    | [{'test1': '0', 'test2': '1', 'test3': 'testpoint'},
    |  {'test1': {'type': 'integer', 'tz': 'UTC', 'units': None},
    |  'test2': {'type': 'integer', 'tz': 'UTC', 'units': None},
    |  'test3': {'type': 'integer', 'tz': 'UTC', 'units': None}}]

This output is an indication of the basic scrape all functionality working in the Interface class - in our
implementation this is also an indication of the basic functionality of the Interface class "get_point" method and
Register class "get_state" methods working (although edge cases should still be tested!).

To test the Interface's "set_point" method and Register's "set_state" method, we'll need to use the Actuator agent.
The following agent code can be used to alternate a point's value on a schedule using the actuator, as well as perform
an action based on a pubsub subscription to a single point:

.. code-block:: python

    def CsvDriverAgent(config_path, **kwargs):
        """Parses the Agent configuration and returns an instance of
        the agent created using that configuration.

        :param config_path: Path to a configuration file.

        :type config_path: str
        :returns: Csvdriveragent
        :rtype: Csvdriveragent
        """
        _log.debug("Config path: {}".format(config_path))
        try:
            config = utils.load_config(config_path)
        except Exception:
            config = {}

        if not config:
            _log.info("Using Agent defaults for starting configuration.")
        _log.debug("config_dict before init: {}".format(config))
        utils.update_kwargs_with_config(kwargs, config)
        return Csvdriveragent(**kwargs)


    class Csvdriveragent(Agent):
        """
        Document agent constructor here.
        """

        def __init__(self, csv_topic="", **kwargs):
            super(Csvdriveragent, self).__init__(**kwargs)
            _log.debug("vip_identity: " + self.core.identity)

            self.agent_id = "csv_actuation_agent"
            self.csv_topic = csv_topic

            self.value = 0
            self.default_config = {
                "csv_topic": self.csv_topic
            }

            # Set a default configuration to ensure that self.configure is called immediately to setup
            # the agent.
            self.vip.config.set_default("config", self.default_config)

            # Hook self.configure up to changes to the configuration file "config".
            self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

        def configure(self, config_name, action, contents):
            """
            Called after the Agent has connected to the message bus. If a configuration exists at startup
            this will be called before onstart.

            Is called every time the configuration in the store changes.
            """
            config = self.default_config.copy()
            config.update(contents)

            _log.debug("Configuring Agent")
            _log.debug(config)

            self.csv_topic = config.get("csv_topic", "")

            # Unsubscribe from everything.
            self.vip.pubsub.unsubscribe("pubsub", None, None)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix="devices/" + self.csv_topic + "/all",
                                      callback=self._handle_publish)

        def _handle_publish(self, peer, sender, bus, topic, headers, message):
            _log.info("Device {} Publish: {}".format(self.csv_topic, message))

        @Core.receiver("onstart")
        def onstart(self, sender, **kwargs):
            """
            This is method is called once the Agent has successfully connected to the platform.
            This is a good place to setup subscriptions if they are not dynamic or
            do any other startup activities that require a connection to the message bus.
            Called after any configurations methods that are called at startup.

            Usually not needed if using the configuration store.
            """
            self.core.periodic(30, self.actuate_point)

        def actuate_point(self):
            _now = get_aware_utc_now()
            str_now = format_timestamp(_now)
            _end = _now + td(seconds=10)
            str_end = format_timestamp(_end)
            schedule_request = [[self.csv_topic, str_now, str_end]]
            result = self.vip.rpc.call(
                'platform.actuator', 'request_new_schedule', self.agent_id, 'my_test', 'HIGH', schedule_request).get(
                timeout=4)
            point_topic = self.csv_topic + "/" + "test1"
            result = self.vip.rpc.call(
                'platform.actuator', 'set_point', self.agent_id, point_topic, self.value).get(
                timeout=4)
            self.value = 0 if self.value is 1 else 1

        @Core.receiver("onstop")
        def onstop(self, sender, **kwargs):
            """
            This method is called when the Agent is about to shutdown, but before it disconnects from
            the message bus.
            """
            pass


    def main():
        """Main method called to start the agent."""
        utils.vip_main(CsvDriverAgent,
                       version=__version__)


    if __name__ == '__main__':
        # Entry point for script
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            pass

While this code runs, since the Actuator is instructing the Interface to set points on the device, the pubsub all
publish can be used to check that the values are changing as expected.
