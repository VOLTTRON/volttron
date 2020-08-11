.. _Modbus-TK-config:

Modbus-TK Driver Configuration
------------------------------

.. warning:: Currently the modbus_tk library is not able to make connections from 2 masters on one host to 2 slaves
    on one host - this will will prevent a single platform from being able to communicate to 2 slaves on IP as each
    instance of a Modbus_Tk driver creates a new Modbus master.
    `Issue on Modbus_Tk Github <https://github.com/ljean/modbus-tk/issues/124>`_.

VOLTTRON's Modbus-TK driver, built on the Python Modbus-TK library, is an alternative to the
original VOLTTRON modbus driver. Unlike the original modbus driver, the Modbus-TK driver
supports Modbus RTU as well as Modbus over TCP/IP.

The Modbus-TK driver introduces a map library and configuration builder, intended as a way
to streamline configuration file creation and maintenance.

The Modbus-TK driver is mostly backward-compatible with the parameter definitions in the original
Modbus driver's configuration (.config and .csv files).
If the config file's parameter names use the Modbus driver's name conventions, they are
translated to the Modbus-TK name conventions, e.g. a Modbus CSV file's "Point Address" is
interpreted as a Modbus-TK "Address". Backward-compatibility exceptions are:

    - If the config file has no **port**, the default is 0, not 502.
    - If the config file has no **slave_id**, the default is 1, not 0.

Requirements
------------
The Modbus-TK driver requires the modbus-tk package. This package can be installed in an
activated environment with:

::

    pip install modbus-tk

driver_config
*************

The **driver_config** section of a Modbus-TK device configuration file supports a variety of parameter definitions,
but only **device_address** is required:

    - **name** (Optional) - Name of the device. Defaults to "UNKNOWN".
    - **device_type** (Optional) - Name of the device type. Defaults to "UNKNOWN".
    - **device_address** (Required) - IP Address of the device.
    - **port** (Optional) - Port the device is listening on. Defaults to 0 (no port). Use port 0 for RTU transport.
    - **slave_id** (Optional) - Slave ID of the device. Defaults to 1. Use ID 0 for no slave.
    - **baudrate** (Optional) - Serial (RTU) baud rate. Defaults to 9600.
    - **bytesize** (Optional) - Serial (RTU) byte size: 5, 6, 7, or 8. Defaults to 8.
    - **parity** (Optional) - Serial (RTU) parity: none, even, odd, mark, or space. Defaults to none.
    - **stopbits** (Optional) - Serial (RTU) stop bits: 1, 1.5, or 2. Defaults to 1.
    - **xonxoff** (Optional) - Serial (RTU) flow control: 0 or 1. Defaults to 0.
    - **addressing** (Optional) - Data address table: offset, offset_plus, or address. Defaults to offset.
        - address: The exact value of the address without any offset value.
        - offset: The value of the address plus the offset value.
        - offset_plus: The value of the address plus the offset value plus one.
        - : If an offset value is to be added, it is determined based on a point's properties in the CSV file:
            - Type=bool, Writable=TRUE:       0
            - Type=bool, Writable=FALSE:  10000
            - Type!=bool, Writable=TRUE:  30000
            - Type!=bool, Writable=FALSE: 40000
    - **endian** (Optional) - Byte order: big or little. Defaults to big.
    - **write_multiple_registers** (Optional) - Write multiple coils or registers at a time. Defaults to true.
        - : If write_multiple_registers is set to false, only register types unsigned short (uint16) and boolean (bool)
          are supported. The exception raised during the configure process.
    - **register_map** (Optional) - Register map csv of unchanged register variables. Defaults to registry_config csv.

Sample Modbus-TK configuration files are checked into the VOLTTRON repository
in ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps``.

Here is a sample TCP/IP Modbus-TK device configuration:

.. code-block:: json

    {
        "driver_config": {
            "device_address": "10.1.1.2",
            "port": "5020",
            "register_map": "config://modbus_tk_test_map.csv"
        },
        "driver_type": "modbus_tk",
        "registry_config": "config://modbus_tk_test.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

Here is a sample RTU Modbus-TK device configuration, using all default settings:

.. code-block:: json

    {
        "driver_config": {
            "device_address": "/dev/tty.usbserial-AL00IEEY",
            "register_map": "config://modbus_tk_test_map.csv"
        },
        "driver_type": "modbus_tk",
        "registry_config":"config://modbus_tk_test.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

Here is a sample RTU Modbus-TK device configuration, with completely-specified settings:

.. code-block:: json

    {
        "driver_config": {
            "device_address": "/dev/tty.usbserial-AL00IEEY",
            "port": 0,
            "slave_id": 2,
            "name": "watts_on",
            "baudrate": 115200,
            "bytesize": 8,
            "parity": "none",
            "stopbits": 1,
            "xonxoff": 0,
            "addressing": "offset",
            "endian": "big",
            "write_multiple_registers": true,
            "register_map": "config://watts_on_map.csv"
        },
        "driver_type": "modbus_tk",
        "registry_config": "config://watts_on.csv",
        "interval": 120,
        "timezone": "UTC"
    }

.. _Modbus-TK-Driver:

Modbus-TK Register Map CSV File
*******************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file.
Each row configures a register definition on the device.

    - **Register Name** (Required) - The field name in the modbus client. This field is distinct and unchangeable.
    - **Address** (Required) - The point's modbus address. The **addressing** option in the driver configuration
      controls whether this is interpreted as an exact address or an offset.
    - **Type** (Required) - The point's data type: bool, string[length], float, int16, int32, int64, uint16,
      uint32, or uint64.
    - **Units** (Optional) - Used for metadata when creating point information on a historian. Default is an
      empty string.
    - **Writable** (Optional) - TRUE/FALSE. Only points for which Writable=TRUE can be updated by a VOLTTRON agent.
      Default is FALSE.
    - **Default Value** (Optional) - The point's default value. If it is reverted by an agent, it changes back
      to this value. If this value is missing, it will revert to the last known value not set by an agent.
    - **Transform** (Optional) - Scaling algorithm: scale(multiplier), scale_int(multiplier), scale_reg(register_name),
      scale_reg_power10(register_name), scale_decimal_int_signed(multiplier), mod10k(reverse),
      mod10k64(reverse), mod10k48(reveres) or none. Default is an empty string.
    - **Table** (Optional) - Standard modbus table name defining how information is stored in slave device.
      There are 4 different tables:

            - discrete_output_coils: read/write coil numbers 1-9999
            - discrete_input_contacts: read only coil numbers 10001-19999
            - analog_input_registers: read only register numbers 30001-39999
            - analog_output_holding_registers: read/write register numbers 40001-49999

      If this field is empty, the modbus table will be defined by **type** and **writable** fields. By that, when user
      sets read only for read/write coils/registers or sets read/write for read only coils/registers, it will select
      wrong table, and therefore raise exception.
    - **Mixed Endian** (Optional) - TRUE/FALSE. If Mixed Endian is set to TRUE, the order of the MODBUS registers will
      be reversed before parsing the value or writing it out to the device. By setting mixed endian, transform must be
      None (no op).
      Defaults to FALSE.
    - **Description** (Optional) - Additional information about the point. Default is an empty string.

Any additional columns are ignored.

Sample Modbus-TK registry CSV files are checked into the VOLTTRON repository
in ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps``.

Here is a sample Modbus-TK registry configuration:

.. csv-table::
        :header: Register Name,Address,Type,Units,Writable,Default Value,Transform,Table

        unsigned_short,0,uint16,None,TRUE,0,scale(10),analog_output_holding_registers
        unsigned_int,1,uint32,None,TRUE,0,scale(10),analog_output_holding_registers
        unsigned_long,3,uint64,None,TRUE,0,scale(10),analog_output_holding_registers
        sample_short,7,int16,None,TRUE,0,scale(10),analog_output_holding_registers
        sample_int,8,int32,None,TRUE,0,scale(10),analog_output_holding_registers
        sample_float,10,float,None,TRUE,0.0,scale(10),analog_output_holding_registers
        sample_long,12,int64,None,TRUE,0,scale(10),analog_output_holding_registers
        sample_bool,16,bool,None,TRUE,False,,analog_output_holding_registers
        sample_str,17,string[12],None,TRUE,hello world!,,analog_output_holding_registers

Modbus-TK Registry Configuration CSV File
*****************************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file.
Each row configures a point on the device.

    - **Volttron Point Name** (Required) - The name by which the platform and agents refer to the point.
      For instance, if the Volttron Point Name is HeatCall1, then an agent would use ``my_campus/building2/hvac1/HeatCall1``
      to refer to the point when using the RPC interface of the actuator agent.
    - **Register Name** (Required) - The field name in the modbus client.
      It must be matched with the field name from **register_map**.

Any additional columns will override the existed fields from **register_map**.

Sample Modbus-TK registry CSV files are checked into the VOLTTRON repository
in ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps``.

Here is a sample Modbus-TK registry configuration with defined **register_map**:

.. csv-table::
        :header: Volttron Point Name,Register Name

        unsigned short,unsigned_short
        unsigned int,unsigned_int
        unsigned long,unsigned_long
        sample short,sample_short
        sample int,sample_int
        sample float,sample_float
        sample long,sample_long
        sample bool,sample_bool
        sample str,sample_str

.. _Modbus-TK-Maps:

Modbus-TK Driver Maps
*********************

To help facilitate the creation of VOLTTRON device configuration entries (.config files) for Modbus-TK
devices, a library of device type definitions is now maintained
in ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps/maps.yaml``. A
command-line tool (described below under **MODBUS TK Config Command Tool**) uses the contents
of ``maps.yaml`` while generating .config files.

Each device type definition in ``maps.yaml`` consists of the following properties:

    - **name** (Required) - Name of the device type (see the driver_config parameters).
    - **file** (Required) - The name of the CSV file that defines all of the device type's supported points,
      e.g. watts_on.csv.
    - **description** (Optional) - A description of the device type.
    - **addressing** (Optional) - Data address type: offset, offset_plus, or address (see the driver_config parameters).
    - **endian** (Optional) - Byte order: big or little (see the driver_config parameters).
    - **write_multiple_registers** (Optional) - Write multiple registers at a time. Defaults to true.

A device type definition is a template for a device configuration. Some additional data must
be supplied when a specific device's configuration is generated. In particular, the device_address must be supplied.

A sample ``maps.yml`` file is checked into the VOLTTRON repository
in ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps/maps.yaml``.

Here is a sample ``maps.yaml`` file:

.. code-block:: yaml

    - name: modbus_tk_test
      description: Example of reading selected points for Modbus-TK driver testing
      file: modbus_tk_test_map.csv
      addressing: offset
      endian: little
      write_multiple_registers: true
    - name: watts_on
      description: Read selected points from Elkor WattsOn meter
      file: watts_on_map.csv
      addressing: offset
    - name: ion6200
      description: ION 6200 meter
      file: ion6200_map.csv
    - name: ion8600
      description: ION 8600 meter
      file: ion8600_map.csv

.. _Modbus-TK-Config-Cmd:

Modbus-TK Config Command Tool
*****************************

``config_cmd.py`` is a command-line tool for creating and maintaining VOLTTRON driver configurations. The tool
runs from the command line:

.. code-block:: shell

     $ cd services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps
     $ python config_cmd.py

``config_cmd.py`` supports the following commands:

    - **help** - List all commands.
    - **quit** - Quit the command-line tool.
    - **list_directories** - List all setup directories, with an option to edit their paths.
        + By default, all directories are in the VOLTTRON repository
          in ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps``.
        + It is important to use the correct directories when adding/editing device types and driver configs,
          and when loading configurations into VOLTTRON.

            * map_dir: directory in which ``maps.yaml`` is stored.
            * config_dir: directory in which driver config files are stored.
            * csv_dir: directory in which registry config CSV files are stored.
    - **edit_directories** - Add/Edit map directory, driver config directory, and/or CSV config directory.
      Press <Enter> if no change is needed. Exits if the directory does not exist.
    - **list_device_type_description** - List all device type descriptions in ``maps.yaml``.
      Option to edit device type descriptions.
    - **list_all_device_types** - List all device type information in ``maps.yaml``. Option to add more device types.
    - **device_type** - List information for a selected device type. Option to select another device type.
    - **add_device_type** - Add a device type to ``maps.yaml``. Option to add more than one device type.
      Each device type includes its name, CSV file, description, addressing, and endian, as explained
      in **MODBUS-TK Driver Maps**. If an invalid value is entered for addressing or endian,
      the default value is used instead.
    - **edit_device_type** - Edit an existing device type. If an invalid value is entered for addressing or endian,
      the previous value is left unchanged.
    - **list_drivers** - List all driver config names in ``config_dir``.
    - **driver_config <driver_name>** - Get a driver config from ``config_dir``.
      Option to select the driver if no driver is found with that name.
    - **add_driver_config <driver_name>** - Add/Edit ``<config_dir>/<driver name>.config``.
      Option to select the driver if no driver is found with that name. Press <Enter> to exit.
    - **load_volttron** - Load a driver config and CSV into VOLTTRON. Option to add the config or CSV file
      to config_dir or to csv_dir. VOLTTRON must be running when this command is used.
    - **delete_volttron_config** - Delete a driver config from VOLTTRON. VOLTTRON must be running
      when this command is used.
    - **delete_volttron_csv** - Delete a registry csv config from VOLTTRON. VOLTTRON must be running
      when this command is used.

The ``config_cmd.py`` module is checked into the VOLTTRON repository
as ``services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/config_cmd.py``.
