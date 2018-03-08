MODBUS_TK REGRESSION TEST README
================================


modbus_listener_agent.py
------------------------
Set-up listener agent to listen to master driver agent with TCP and RTU transport:

- Use "volttron-cfg" to set-up master driver agent with default fake_driver, add the int register "count"
to its csv config using this script:
    $ vctl config edit platform.driver fake.csv
- Add modbus_test driver config and csv using this script for tcp transport testing:
    $ vctl config store platform.driver modbus_test.csv <csv_path> --csv
    $ vctl config store platform.driver devices/modbus_test <config_path>
- Add watts_on_1 and watts_on_2 driver config and csv using similar script for rtu transport testing:
    $ vctl config store platform.driver watts_on.csv <csv_path> --csv
    $ vctl config store platform.driver watts_on_map.csv <csv_path> --csv
    $ vctl config store platform.driver devices/watts_on_1 <config_path>
    $ vctl config store platform.driver devices/watts_on_2 <config_path>
    For this paricular test, we need to connect to the Elkor Watts On meter by usb to the RS-485 interface
- run modbus server
- modbus_listener_agent.py listens to everything and response according to each request called on on_match

All the example driver config and csv are saved under example_config directory


test_modbus_tk_driver.py
------------------------
Regression test for modbus_tk interface with tcp transport:

- Build master driver agent and define two different modbus driver config and two different register csv set,
one followed the original modbus structure, and another followed the new modbus_tk structure
- With the set-up server running, do regression test on set_point, get_point, scrape_all, revert_point,
and revert_device for both drivers


test_scrape_all.py
------------------
Regression test for modbus_tk interface with tcp transport:

- Build master driver agent and define two different modbus driver config and two different register csv set,
one followed the original modbus structure, and another followed the new modbus_tk structure
- With the set-up server running, run scrape_all for both drivers in two different threads with some set-up
time interval
- One test with same reading interval for both devices, and another test for different reading interval for
each device


test_ion6200.py
---------------
Regression test for modbus_tk interface with tcp transport:
(Similar to test_modbus_tk_driver.py, but in ion6200 driver config and ion6200 registers set)


test_watts_on.py
----------------
Regression test for modbus_tk interface with rtu transport:

- For this paricular test, connect to the Elkor Watts On meter by usb to the RS-485 interface and make sure to have
a correct device_address and slave_id. On Mac OS, the device_address is /dev/tty.usbserial-AL00IEEY with default
slave_id 1
- Do regression test on set_point, get_point, and scrape_all


test_write_single_registers.py
------------------------------
Regression test for modbus_tk interface with tcp transport:

- Build master driver agent and define write_single_registers driver config and register csv set with the additional
feature write_multiple_registers = false (it means write single register with modbus function code 06)
- With the set-up server running, do regression test on set_point, get_point, scrape_all, revert_point,
and revert_device for the driver

