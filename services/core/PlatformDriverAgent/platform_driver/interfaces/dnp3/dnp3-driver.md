# DNP3 Driver

Distributed Network Protocol (DNP
or [DNP3](https://en.wikipedia.org/wiki/DNP3))
has achieved a large-scale acceptance since its introduction in 1993. This
protocol is an immediately deployable solution for monitoring remote sites because it was developed for communication of
critical infrastructure status, allowing for reliable remote control.

DNP3 is typically used between centrally located masters and distributed remotes. The master provides the interface
between the human network manager and the monitoring system. The remote (RTUs and intelligent electronic devices)
provides the interface between the master and the physical device(s) being monitored and/or controlled.
The DNP3-Driver is a wrapper on the DNP3 master following
the [VOLTTRON driver framework](https://volttron.readthedocs.io/en/develop/agent-framework/driver-framework/drivers-overview.html#driver-framework).

Note that the DNP3-Driver requires a DNP3 outstation instance to properly function. e.g., polling data, setting point
values, etc. The [dnp3-python](https://github.com/VOLTTRON/dnp3-python) can provide the essential outstation
functionality, and as part of the DNP3-Driver dependency, it is immediately available after the DNP3-Driver is
installed.

### Requirements

The DNP3 driver requires the [dnp3-python](https://github.com/VOLTTRON/dnp3-python) package, a wrapper on Pydnp3
package.
This package can be installed in an activated environment with:

    pip install dnp3-python==0.2.3b3

### Quick Start

The following recipe walks through the steps to install and configure a DNP3 Driver. Note that it uses default setup to
work out-of-the-box. Please feel free to refer to related documentations for details.

1. Install volttron and start the platform.

   Refer
   to [VOLTTRON Quick Start](https://volttron.readthedocs.io/en/main/tutorials/quick-start.html#volttron-quick-start) to
   install the platform.
   Then start the platform with the following command. (Please see `volttron --help` for more details.)

    ```shell
    # Start platform with output going to volttron.log
    volttron -vv -l volttron.log &
    ```

1. Install the volttron platform driver:

   Install the required dependency for driver using `python bootstrap.py --drivers`. (Please
   see `python bootstrap.py --help` for more details.)

   Note: for reproducibility, this demo will install platform driver with `vip-identity==platform_driver_for_dnp3`.
   Free feel to specify any agent vip-identity as desired.

    ```shell
    vctl install services/core/PlatformDriverAgent/ \
    --vip-identity platform_driver_for_dnp3 \
    --agent-config services/core/PlatformDriverAgent/platform-driver.agent \
    --tag platform_driver_for_dnp3 \
    -f \
    --start
    ```

    <details>
    <summary>Verify with `vctl status`.</summary>

    ```shell
    (env) kefei@ubuntu-22:~/sandbox/dnp3-driver-sandbox$ vctl status
    
    UUID   AGENT                             IDENTITY                     TAG PRIORITY STATUS          HEALTH                                   
    
    5      platform_driveragent-4.0 platform_driver_for_dnp3                  running [23217] GOOD
    ```

### Configure the DNP3 driver

1. Install a DNP3 Driver onto the Platform Driver.

   Installing a DNP3 driver in the Platform Driver Agent requires adding copies of the device configuration and registry
   configuration files to the Platform Driver’s configuration store. For demo purpose, we will use default configure
   files.

   Prepare the default config files:

    ```shell
    # Create config file place holders
    mkdir config
    touch config/dnp3-config.json
    touch config/dnp3.csv
    ```

   An example config file is available at "
   services/core/PlatformDriverAgent/platform_driver/interfaces/udd_dnp3/examples/dnp3.config"

    ```json
    {
      "driver_config": {
        "master_ip": "0.0.0.0",
        "outstation_ip": "127.0.0.1",
        "master_id": 2,
        "outstation_id": 1,
        "port": 20000
      },
      "registry_config": "config://dnp3.csv",
      "driver_type": "dnp3",
      "interval": 5,
      "timezone": "UTC",
      "publish_depth_first_all": true,
      "heart_beat_point": "random_bool"
    }
    ```

   Another example config file is available at "
   services/core/PlatformDriverAgent/platform_driver/interfaces/udd_dnp3/examples/dnp3.csv"

    ```csv
    Point Name,Volttron Point Name,Group,Variation,Index,Scaling,Units,Writable,Notes
    AnalogInput_index0,AnalogInput_index0,30,6,0,1,NA,FALSE,Double Analogue input without status
    AnalogInput_index1,AnalogInput_index1,30,6,1,1,NA,FALSE,Double Analogue input without status
    AnalogInput_index2,AnalogInput_index2,30,6,2,1,NA,FALSE,Double Analogue input without status
    AnalogInput_index3,AnalogInput_index3,30,6,3,1,NA,FALSE,Double Analogue input without status
    BinaryInput_index0,BinaryInput_index0,1,2,0,1,NA,FALSE,Single bit binary input with status
    BinaryInput_index1,BinaryInput_index1,1,2,1,1,NA,FALSE,Single bit binary input with status
    BinaryInput_index2,BinaryInput_index2,1,2,2,1,NA,FALSE,Single bit binary input with status
    BinaryInput_index3,BinaryInput_index3,1,2,3,1,NA,FALSE,Single bit binary input with status
    AnalogOutput_index0,AnalogOutput_index0,40,4,0,1,NA,TRUE,Double-precision floating point with flags
    AnalogOutput_index1,AnalogOutput_index1,40,4,1,1,NA,TRUE,Double-precision floating point with flags
    AnalogOutput_index2,AnalogOutput_index2,40,4,2,1,NA,TRUE,Double-precision floating point with flags
    AnalogOutput_index3,AnalogOutput_index3,40,4,3,1,NA,TRUE,Double-precision floating point with flags
    BinaryOutput_index0,BinaryOutput_index0,10,2,0,1,NA,TRUE,Binary Output with flags
    BinaryOutput_index1,BinaryOutput_index1,10,2,1,1,NA,TRUE,Binary Output with flags
    BinaryOutput_index2,BinaryOutput_index2,10,2,2,1,NA,TRUE,Binary Output with flags
    BinaryOutput_index3,BinaryOutput_index3,10,2,3,1,NA,TRUE,Binary Output with flags
    
    ```

   Add config to the configuration store:

    ```
    vctl config store platform_driver_for_dnp3 devices/campus/building/dnp3 services/core/PlatformDriverAgent/platform_driver/interfaces/udd_dnp3/examples/dnp3.config
    vctl config store platform_driver_for_dnp3 services/core/PlatformDriverAgent/platform_driver/interfaces/udd_dnp3/examples/dnp3.csv --csv
    ```

    <details>
    <summary>Verify with `vctl config list` and `vctl config get` command. 
    (Please refer to the `vctl config` documentation for more details.)</summary>

    ```shell
    (env) kefei@ubuntu-22:~/sandbox/dnp3-driver-sandbox$ vctl config get platform_driver_for_dnp3 devices/campus/building/dnp3
    {
      "driver_config": {
        "master_ip": "0.0.0.0",
        "outstation_ip": "127.0.0.1",
        "master_id": 2,
        "outstation_id": 1,
        "port": 20000
      },
      "registry_config": "config://dnp3.csv",
      "driver_type": "dnp3",
      "interval": 5,
      "timezone": "UTC",
      "publish_depth_first_all": true,
      "heart_beat_point": "random_bool"
    }
    
    (env) kefei@ubuntu-22:~/sandbox/dnp3-driver-sandbox$ vctl config get platform_driver_for_dnp3 dnp3.csv
    [
      {
        "Point Name": "AnalogInput_index0",
        "Volttron Point Name": "AnalogInput_index0",
        "Group": "30",
        "Variation": "6",
        "Index": "0",
    ...
    ]
    ```

    </details>

1. Verify with logging data

   When the DNP3-Driver is properly installed and configured, we can verify with logging data in "volttron.log".

    ```
    tail -f <path to folder containing volttron.log>/volttron.log
    ```

    <details>
    <summary>Expected logging example</summary>

    ```shell
    ...
    2023-03-13 23:26:56,611 (volttron-platform-driver-0.2.0rc1 23666) volttron.driver.base.driver(334) DEBUG: finish publishing: devices/campus/building/dnp3/all
    2023-03-13 23:26:57,897 () volttron.services.auth.auth_service(235) DEBUG: after getting peerlist to send auth updates
    2023-03-13 23:26:57,897 () volttron.services.auth.auth_service(239) DEBUG: Sending auth update to peers platform.control
    2023-03-13 23:26:57,897 () volttron.services.auth.auth_service(239) DEBUG: Sending auth update to peers platform_driver_for_dnp3
    2023-03-13 23:26:57,898 () volttron.services.auth.auth_service(239) DEBUG: Sending auth update to peers platform.health
    2023-03-13 23:26:57,898 () volttron.services.auth.auth_service(239) DEBUG: Sending auth update to peers platform.config_store
    2023-03-13 23:26:57,898 () volttron.services.auth.auth_service(193) INFO: auth file /home/kefei/.volttron/auth.json loaded
    2023-03-13 23:26:57,898 () volttron.services.auth.auth_service(172) INFO: loading auth file /home/kefei/.volttron/auth.json
    2023-03-13 23:26:57,898 () volttron.services.auth.auth_service(185) DEBUG: Sending auth updates to peers
    2023-03-13 23:26:58,241 (volttron-platform-driver-0.2.0rc1 23666) <stdout>(0) INFO: ['ms(1678768018241) INFO    tcpclient - Connecting to: 127.0.0.1']
    2023-03-13 23:26:58,241 (volttron-platform-driver-0.2.0rc1 23666) <stdout>(0) INFO: ['ms(1678768018241) WARN    tcpclient - Error Connecting: Connection refused']
    2023-03-13 23:26:59,905 () volttron.services.auth.auth_service(235) DEBUG: after getting peerlist to send auth updates
    2023-03-13 23:26:59,905 () volttron.services.auth.auth_service(239) DEBUG: Sending auth update to peers platform.control
    2023-03-13 23:26:59,905 () volttron.services.auth.auth_service(239) DEBUG: Sending auth update to peers platform_driver_for_dnp3...
    ]
    ```
    </details>

1. (Optional) Verify with published data polled from outstation

   To see data being polled from an outstation and published to the bus, we need to

    * Set up an outstation, and
    * install a [Listener Agent](https://pypi.org/project/volttron-listener/):

   **Set up an outstation**: The [dnp3-python](https://github.com/VOLTTRON/dnp3-python) is part of the dnp3-driver
   dependency, and it is immediately available after the DNP3-Driver is installed.

   **Open another terminal**, and run `dnp3demo outstation`. For demo purpose, we assign arbitrary values to the
   point. (
   More details about the "dnp3demo" module, please
   see [dnp3demo-Module.md](https://github.com/VOLTTRON/dnp3-python/blob/main/docs/dnp3demo-Module.md))

   ```shell
    ==== Outstation Operation MENU ==================================
    <ai> - update analog-input point value (for local reading)
    <ao> - update analog-output point value (for local control)
    <bi> - update binary-input point value (for local reading)
    <bo> - update binary-output point value (for local control)
    <dd> - display database
    <dc> - display configuration
    =================================================================
   
    ======== Your Input Here: ==(outstation)======
    ai
    You chose <ai> - update analog-input point value (for local reading)
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    
    ======== Your Input Here: ==(outstation)======
    0.1212 0
    {'Analog': {0: 0.1212, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None, 9: None}}
    You chose <ai> - update analog-input point value (for local reading)
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    
    ======== Your Input Here: ==(outstation)======
    1.2323 1
    {'Analog': {0: 0.1212, 1: 1.2323, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None, 9: None}}
    You chose <ai> - update analog-input point value (for local reading)
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
   ```
    <details>
    <summary>Example of interaction with the `dnp3demo outstation` sub-command</summary>

    ```shell
    (env) kefei@ubuntu-22:~/sandbox/dnp3-driver-sandbox$ dnp3demo outstation
    dnp3demo.run_outstation {'command': 'outstation', 'outstation_ip=': '0.0.0.0', 'port=': 20000, 'master_id=': 2, 'outstation_id=': 1}
    ms(1678770551216) INFO    manager - Starting thread (0)
    2023-03-14 00:09:11,216	control_workflow_demo	INFO	Connection Config
    2023-03-14 00:09:11,216	control_workflow_demo	INFO	Connection Config
    2023-03-14 00:09:11,216	control_workflow_demo	INFO	Connection Config
    ms(1678770551216) INFO    server - Listening on: 0.0.0.0:20000
    2023-03-14 00:09:11,216	control_workflow_demo	DEBUG	Initialization complete. Outstation in command loop.
    2023-03-14 00:09:11,216	control_workflow_demo	DEBUG	Initialization complete. Outstation in command loop.
    2023-03-14 00:09:11,216	control_workflow_demo	DEBUG	Initialization complete. Outstation in command loop.
    Connection error.
    Connection Config {'outstation_ip_str': '0.0.0.0', 'port': 20000, 'masterstation_id_int': 2, 'outstation_id_int': 1}
    Start retry...
    Connection error.
    Connection Config {'outstation_ip_str': '0.0.0.0', 'port': 20000, 'masterstation_id_int': 2, 'outstation_id_int': 1}
    ms(1678770565247) INFO    server - Accepted connection from: 127.0.0.1
    ==== Outstation Operation MENU ==================================
    <ai> - update analog-input point value (for local reading)
    <ao> - update analog-output point value (for local control)
    <bi> - update binary-input point value (for local reading)
    <bo> - update binary-output point value (for local control)
    <dd> - display database
    <dc> - display configuration
    =================================================================
    
    
    ======== Your Input Here: ==(outstation)======
    ai
    You chose <ai> - update analog-input point value (for local reading)
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    
    ======== Your Input Here: ==(outstation)======
    0.1212 0
    {'Analog': {0: 0.1212, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None, 9: None}}
    You chose <ai> - update analog-input point value (for local reading)
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    
    ======== Your Input Here: ==(outstation)======
    1.2323 1
    {'Analog': {0: 0.1212, 1: 1.2323, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None, 9: None}}
    You chose <ai> - update analog-input point value (for local reading)
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    
    ======== Your Input Here: ==(outstation)======
    ```
    </details>

   **Install the [Listener Agent](https://pypi.org/project/volttron-listener/)**:
   Run `vctl install volttron-listener --start`. Once installed, you should see the data being published by viewing the
   Volttron logs file. (i.e., `tail -f <path to folder containing volttron.log>/volttron.log`)
   > **Note**:
   > it is recommended to restart the Platform Driver after a specific driver is installed and configured. i.e.,
   > using the `vctl restart <agent-uuid>` command.) The expected logging will be similar as follows:

    ```shell
    2023-03-14 00:11:55,000 (volttron-platform-driver-0.2.0rc0 24737) volttron.driver.base.driver(277) DEBUG: scraping device: campus/building/dnp3
    2023-03-14 00:11:55,805 (volttron-platform-driver-0.2.0rc0 24737) volttron.driver.base.driver(330) DEBUG: publishing: devices/campus/building/dnp3/all
    2023-03-14 00:11:55,810 (volttron-listener-0.2.0rc0 24424) listener.agent(104) INFO: Peer: pubsub, Sender: platform_driver_for_dnp3:, Bus: , Topic: devices/campus/building/dnp3/all, Headers: {'Date': '2023-03-14T05:11:55.805245+00:00', 'TimeStamp': '2023-03-14T05:11:55.805245+00:00', 'SynchronizedTimeStamp': '2023-03-14T05:11:55.000000+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message: 
    [{'AnalogInput_index0': 0.1212,
      'AnalogInput_index1': 1.2323,
      'AnalogInput_index2': 0.0,
      'AnalogInput_index3': 0.0,
      'AnalogOutput_index0': 0.0,
      'AnalogOutput_index1': 0.0,
      'AnalogOutput_index2': 0.0,
      'AnalogOutput_index3': 0.0,
      'BinaryInput_index0': False,
      'BinaryInput_index1': False,
      'BinaryInput_index2': False,
      'BinaryInput_index3': False,
      'BinaryOutput_index0': False,
      'BinaryOutput_index1': False,
      'BinaryOutput_index2': False,
      'BinaryOutput_index3': False},
     {'AnalogInput_index0': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogInput_index1': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogInput_index2': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogInput_index3': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogOutput_index0': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogOutput_index1': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogOutput_index2': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'AnalogOutput_index3': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryInput_index0': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryInput_index1': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryInput_index2': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryInput_index3': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryOutput_index0': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryOutput_index1': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryOutput_index2': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'},
      'BinaryOutput_index3': {'type': 'integer', 'tz': 'UTC', 'units': 'NA'}}]
    2023-03-14 00:11:55,810 (volttron-platform-driver-0.2.0rc0 24737) volttron.driver.base.driver(334) DEBUG: finish publishing: devices/campus/building/dnp3/all
    2023-03-14 00:11:56,825 (volttron-listener-0.2.0rc0 24424) listener.agent(104) INFO: Peer: pubsub, Sender: volttron-listener-0.2.0rc0_2:, Bus: , Topic: heartbeat/volttron-listener-0.2.0rc0_2, Headers: {'TimeStamp': '2023-03-14T05:11:56.820827+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message: 
    
    ```

1. Shutdown the platform

   ```shell
   ./stop-volttron
   ```

### DNP3 Registry Configuration File

The driver's registry configuration file, a [CSV](https://en.wikipedia.org/wiki/Comma-separated_values) file,
specifies which DNP3 points the driver will read and/or write. Each row configures a single DNP3 point.

The following columns are required for each row:

- **Volttron Point Name** - The name used by the VOLTTRON platform and agents to refer to the point.
- **Group** - The point's DNP3 group number.
- **Variation** - THe permit negotiated exchange of data formatted, i.e., data type.
- **Index** - The point's index number within its DNP3 data type (which is derived from its DNP3 group number).
- **Scaling** - A factor by which to multiply point values.
- **Units** - Point value units.
- **Writable** - TRUE or FALSE, indicating whether the point can be written by the driver (FALSE = read-only).

Consult the **DNP3 data dictionary** for a point's Group and Index values. Point
definitions in the data dictionary are by agreement between the DNP3 Outstation and Master.
The VOLTTRON DNP3Agent loads the data dictionary of point definitions from the JSON file
at "point_definitions_path" in the DNP3Agent's config file.

### Testing

1. (If not satisfied,) install the dependencies for testing.

    ```shell
    python bootstrap.py --testing
    ```

1. Run pytest

   ```shell
   pytest ./services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/.
   ```

   Note: the tests run on port=20000 by default. Make sure there is no other dnp3 instances running on port 20000 when
   running the tests.

    <details>
    <summary> Example output </summary>

    ```shell
    ===================================================================================================== test session starts =====================================================================================================
    platform linux -- Python 3.10.6, pytest-7.1.2, pluggy-1.0.0 -- /home/kefei/project/volttron/env/bin/python
    cachedir: .pytest_cache
    rootdir: /home/kefei/project/volttron, configfile: pytest.ini
    plugins: rerunfailures-10.2, asyncio-0.19.0, timeout-2.1.0
    asyncio: mode=auto
    timeout: 300.0s
    timeout method: signal
    timeout func_only: False
    collected 27 items                                                                                                                                                                                                            
    
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDummy::test_dummy PASSED                                                                                               [  3%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestStation::test_station_init PASSED                                                                                      [  7%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestStation::test_station_get_val_analog_input_float PASSED                                                                [ 11%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestStation::test_station_set_val_analog_input_float PASSED                                                                [ 14%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNPRegister::test_init PASSED                                                                                          [ 18%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNPRegister::test_get_register_value_analog_float PASSED                                                               [ 22%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNPRegister::test_get_register_value_analog_int PASSED                                                                 [ 25%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNPRegister::test_get_register_value_binary PASSED                                                                     [ 29%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNP3RegisterControlWorkflow::test_set_register_value_analog_float PASSED                                               [ 33%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNP3RegisterControlWorkflow::test_set_register_value_analog_int PASSED                                                 [ 37%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNP3RegisterControlWorkflow::test_set_register_value_binary PASSED                                                     [ 40%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNP3InterfaceNaive::test_init PASSED                                                                                   [ 44%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNP3InterfaceNaive::test_get_reg_point PASSED                                                                          [ 48%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver.py::TestDNP3InterfaceNaive::test_set_reg_point PASSED                                                                          [ 51%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDummy::test_dummy PASSED                                                                          [ 55%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDummyAgentFixture::test_agent_dummy[volttron_instance0] SKIPPED (only for debugging purpose)      [ 59%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_interface_get_point[volttron_instance0] PASSED                                [ 62%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_interface_set_point[volttron_instance0] PASSED                                [ 66%]ms(1684117269227) INFO    manager - Exiting thread (0)
    
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDummyAgentFixture::test_agent_dummy[volttron_instance1] SKIPPED (RabbitMQ is not setup and/or...) [ 70%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_interface_get_point[volttron_instance1] SKIPPED (RabbitMQ is not setup an...) [ 74%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_interface_set_point[volttron_instance1] SKIPPED (RabbitMQ is not setup an...) [ 77%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDummyAgentFixture::test_agent_dummy[volttron_instance2] SKIPPED (only for debugging purpose)      [ 81%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_interface_get_point[volttron_instance2] PASSED                                [ 85%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_interface_set_point[volttron_instance2] PASSED                                [ 88%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_scrape_all SKIPPED (TODO)                                                     [ 92%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_revert_all SKIPPED (TODO)                                                     [ 96%]
    services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py::TestDnp3DriverRPC::test_revert_point SKIPPED (TODO)                                                   [100%]
    
    ====================================================================================================== warnings summary =======================================================================================================
    env/lib/python3.10/site-packages/wheel/paths.py:7
      /home/kefei/project/volttron/env/lib/python3.10/site-packages/wheel/paths.py:7: DeprecationWarning: The distutils package is deprecated and slated for removal in Python 3.12. Use setuptools or check PEP 632 for potential alternatives
        import distutils.command.install as install
    
    ../../../../usr/lib/python3.10/distutils/command/install.py:13
      /usr/lib/python3.10/distutils/command/install.py:13: DeprecationWarning: The distutils.sysconfig module is deprecated, use sysconfig instead
        from distutils.sysconfig import get_config_vars, is_virtual_environment
    
    -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
    =================================================================================================== short test summary info ===================================================================================================
    SKIPPED [2] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py: only for debugging purpose
    SKIPPED [1] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py: RabbitMQ is not setup and/or SSL does not work in CI
    SKIPPED [1] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py:65: RabbitMQ is not setup and/or SSL does not work in CI
    SKIPPED [1] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py:85: RabbitMQ is not setup and/or SSL does not work in CI
    SKIPPED [1] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py:104: TODO
    SKIPPED [1] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py:117: TODO
    SKIPPED [1] services/core/PlatformDriverAgent/platform_driver/interfaces/dnp3/tests/test_dnp3_driver_integration_volttron.py:129: TODO
    ==================================================================================== 19 passed, 8 skipped, 2 warnings in 227.38s (0:03:47) ====================================================================================
    ```

    </details>
