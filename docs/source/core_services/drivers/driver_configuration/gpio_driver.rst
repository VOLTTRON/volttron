GPIO Driver
===========

The GPIO driver is an implementation of a VOLTTRON driver frame work Interface. An instance of a VOLTTRON Interface
serves as an interface between the VOLTTRON Master Driver agent and some device. In the case of the GPIO driver, the
interface is responsible for providing a way for the master driver to communicate with and control GPIO devices. The
current implementation uses the gpiozero library to communicate with GPIO devices connected to a Raspberry Pi. The GPIO
driver allows both basic communication functionality (getting and setting values of GPIO devices), as well as more
complex functionality such as toggling the state of an output device or waiting for a change of state of a device.

Configuration File
------------------
The GPIO driver uses two configuration files, similar to many other VOLTTRON agents.

This is an example driver configuration:

::

    {
        "driver_config": {"pin_factory": "<gpiozero pin factory>",
                          "driver_path": "<devices/gpio>",
                          "remote_address": "<Public IP address of remote GPIO device>"},
        "driver_type": "gpio",
        "registry_config": "config://gpio_registers.csv",
        "interval": 5,
        "timezone": "UTC"
    }

The driver configuration works as follows:

    driver_config: this section specifies values used by the driver agent during operation.

        pin_factory - This is the gpiozero pin factory that will be used to communicate with the GPIO pins. The pin
        factory you specify should match one of the following: mock, rpi.gpio, native, or pigpio. If rpi.gpio or pigpio
        are chosen, the related python library must be installed during setup.

        driver_path - This should directly match the device topic used in the installation of the GPIO driver (see
        installation below).

        remote_address - This is the public IP address of the remote Raspberry Pi you want to communicate with.

    driver_type: This value should match the name of the python file which contains the interface class implementation
    for the GPIO driver. This should not change if the user has not changed the name of that Python file.

    registry_config: This should match the path to the registry configuration file specified during installation (see
    Installation below).

    interval: This should specify the time in seconds between publishes to the message bus by the Master Driver for the
    GPIO driver.

    timezone: Timezone to use for timestamps.

Registry Configuration
----------------------
This file is used to specify to the driver how to setup the GPIO registers. Specifying the correct device type for your
purpose is extremely important in being able to communicate with your device the way you want to. For example, input
devices are read only, while output devices can be written to.

This is an example registry configuration:

::

    Point Name,Pin,Device Type,Active High,Initial Value,Pull Up,Bounce Time
    Solenoid,24,output,TRUE,TRUE,,
    flowSensor,12,digital_input,,,TRUE,
    flowLED,13,output,TRUE,TRUE,,
    abortButton,16,digital_input,,,FALSE,
    sensorPoint,21,output,TRUE,TRUE,,

The configuration works as follows:

    Point Name - Name of a point as a user would like it to be referenced and displayed by Volttron.

    Pin - The broadcom pin number of the GPIO pin the device is connected to.

    Device Type - The type of device connected to the referenced GPIO pin. The three options are digital_input, output,
    and digital_output. These correspond to the gpiozero library classes: DigitalInputDevice, OutputDevice,
    and DigitalOutputDevice. If left empty, the default will be output.

    Active High - This specifies the active state of the device. The value provided here decides whether the device is
    considered active when its state is 'HIGH' or 'LOW.' The value provided must be either "True" (the device is active
    when 'HIGH') or "False" (the device is active when 'LOW'). (Note: for input devices "Active High" should only be
    specified if "Pull Up" is not, otherwise it will be ignored.)

    Initial Value - This value only affects and decides whether the initial state of an output device will be preserved.
    The value provided must be either "True" (the initial value is preserved) or "False" (the device will be off
    initially). If empty, the default will be "False."

    Pull Up - This value only affects input devices. The value provided must be either "True" (the pin is pulled
    up/high) or "False" (the pin is pulled low/down). (Note: if a value is not specified for "Pull Up," the active state
    must be specified via "Active High.")

    Bounce Time - This value only affects input devices. The value provided specifies the length in seconds after an
    initial state change during which subsequent changes will be ignored. The value provided must be a float. This may
    be left empty if not bounce time compensation is required.

Installation
------------

These are the most basic installation steps for the GPIO driver. This guide assumes the user is in the VOLTTRON_ROOT
directory, and the VOLTTRON platform has been installed and bootstrapped per the  instructions in the VOLTTRON README.

Below are the setup instructions.

    1. If the platform has not been started:

        ./start-volttron

    2. If the environment has not been activated - you should see (volttron) next to <user>@<host> in your terminal window

        . env/bin/activate

    3. Install a Master Driver if one is not yet installed

        python scripts/install-agent.py -s services/core/MasterDriverAgent -c <master driver configuration file>

    4. Load the driver configuration into the configuration store ("vctl config list platform.driver" can be used to show installed configurations)

        vctl config store platform.driver <device topic (mentioned in driver configuration section)>
        <path to driver configuration>

    6. Load the driver's registry configuration into the configuration store

        vctl config store platform.driver <registry configuration path from driver configuration>
        <path to registry configuration file> --csv

    7. Start the master driver

        vctl start platform.driver

At this point, the master driver will start, configure the driver agent, and
data should start to publish on the publish interval.

GPIO Driver Usage
-----------------
At the configured interval, the master driver will publish a JSON object with data obtained from each of the configured
GPIO registers.

The following is an example publish:

::

    '{"Solenoid": 0, "flowSensor": 0, "flowLED": 0, "abortButton": 0}'

get_point
^^^^^^^^^
Using the GPIO driver's get_point function, the value of a specified device can be retrieved. The parameter point_name
must match one of the point names provided in the registry configuration.

Base function call:

::

    get_point(point_name)

In an agent:

::

    self.vip.rpc.call(“platform.driver”, “get_point”, <device topic>, <point_name>)

set_point
^^^^^^^^^^
Using the GPIO driver's set_point function allows the user to set a point value, or perform a device type specific
action. The parameter point_name must match one of the point names provided in the registry configuration. The value
parameter must be an integer if you wish to set the point value, or a dictionary if you wish to perform a device type
specific action.

Base function call:

::

    _set_point(point_name, value)

In an agent for setting a point value:

::

    self.vip.rpc.call(“platform.driver”, “set_point”, <device topic>, <point_name>, <value>)

Setting up the value parameter as a dictionary:
"""""""""""""""""""""""""""""""""""""""""""""""
On - Turn an output device on.

::

    {"action": "on"}

Off - Turn an output device off.

::

    {"action": "off"}

Toggle - Switch the state of an output device.

::

    {"action": "toggle"}

Blink - Turn a device on and off at a specified interval.

::

    {"action": "blink",
     "on_time": <float, number of seconds on>,
     "off_time": <float, number of seconds off>,
     "number_of_blinks": <integer, number of blinks>,
     "background": <true or false, whether the process will be run in the background>}

Get Active High - Retrieve whether an output device is active when 'HIGH.'

::

    {"action": "get_active_high"}

Set Active High - Set whether an output device is active when 'HIGH.'

::

    {"action": "set_active_high", "active_high": "<true or false>"}

Wait for Active - Return when device is active.

::

    {"action": "wait_for_active"}

Wait for Inactive - Return when device is inactive.

::

    {"action": "wait_for_inactive"}

Get Active Time - Return time in seconds the device has been active for.

::

    {"action": "get_active_time"}

Get Inactive Time - Return time in seconds the device has been inactive for.

::

    {"action": "get_inactive_time"}

When Activated - when device becomes active, publish message to the message bus with the topic:

    device/<driver path specified in driver config>/<point name specified in registry config>

::

    {"action": "when_activated"}

When Deactivated - when device becomes inactive, publish message to the message bus with the topic:

    device/<driver path specified in driver config>/<point name specified in registry config>

::

    {"action": "when_deactivated"}
