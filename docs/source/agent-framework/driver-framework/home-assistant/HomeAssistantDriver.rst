.. _HomeAssistant-Driver:

Home Assistant Driver
==============================

The Home Assistant driver enables VOLTTRON to access any data point from a Home Assistant device, currently facilitating control of lights and thermostats.

For further details, refer to the README for the platform driver `here <https://github.com/riley206/Rileys_volttron/blob/55146b78d3ab7f53d08598df272cdda2d0aa8d3d/services/core/PlatformDriverAgent/README.md>`_.

.. mermaid::

   sequenceDiagram
       HomeAssistant Driver->>HomeAssistant: Retrieve Entity Data (REST API)
       HomeAssistant-->>HomeAssistant Driver: Entity Data (Status Code: 200)
       HomeAssistant Driver->>PlatformDriverAgent: Publish Entity Data
       PlatformDriverAgent->>Controller Agent: Publish Entity Data

       Controller Agent->>HomeAssistant Driver: Instruct to Turn Off Light
       HomeAssistant Driver->>HomeAssistant: Send Turn Off Light Command (REST API)
       HomeAssistant-->>HomeAssistant Driver: Command Acknowledgement (Status Code: 200)

Before proceeding, find your Home Assistant IP address and long-lived access token from `here <https://developers.home-assistant.io/docs/auth_api/#long-lived-access-token>`_.

Clone the repository, install the listener agent, and the platform driver agent.

- `Listener agent <https://volttron.readthedocs.io/en/main/introduction/platform-install.html#installing-and-running-agents>`_
- `Platform driver agent <https://volttron.readthedocs.io/en/main/agent-framework/core-service-agents/platform-driver/platform-driver-agent.html?highlight=platform%20driver%20isntall#configuring-the-platform-driver>`_

After cloning, populate your configuration file, and registry file. Each device requires one configuration file and one registry file. Ensure your registry_config links to your device's registry file from the config store. Examples for lights and thermostats are provided below. Be sure to include the full entity id, including but not limited to "light." and "climate.".
The driver uses these prefixes to convert states into integers. Like mentioned before, the driver can only control lights and thermostats.

Lights
------
.. code-block:: json

   {
       "driver_config": {
           "ip_address": "Your Home Assistant IP",
           "access_token": "Your Home Assistant Access Token",
           "port": "Your Port"
       },
       "driver_type": "home_assistant",
       "registry_config": "config://light.example.json",
       "interval": 30,
       "timezone": "UTC"
   }

Your registry file should contain one device, with the ability to add attributes. The Entity ID extracts data from Home Assistant, and Volttron Point Name retrieves the state or attributes defined. Below is an example file named light.example.json:

.. code-block:: json

   [
       {
           "Entity ID": "light.example",
           "Volttron Point Name": "state",
           "Units": "On / Off",
           "Units Details": "on/off",
           "Writable": true,
           "Starting Value": true,
           "Type": "boolean",
           "Notes": "lights hallway"
       },
       {
           "Entity ID": "light.example",
           "Volttron Point Name": "brightness",
           "Units": "int",
           "Units Details": "light level",
           "Writable": true,
           "Starting Value": 0,
           "Type": "int",
           "Notes": "brightness control, 0 - 255"
       }
   ]

Thermostats
-----------

For thermostats, the state is converted into numbers as follows: "1: Off, 2: heat, 3: Cool, 4: Auto",

.. code-block:: json

   [
       {
           "Entity ID": "climate.my_thermostat",
           "Volttron Point Name": "state",
           "Units": "Enumeration",
           "Units Details": "0: Off, 2: heat, 3: Cool, 4: Auto",
           "Writable": true,
           "Starting Value": 1,
           "Type": "int",
           "Notes": "Mode of the thermostat"
       },
       {
           "Entity ID": "climate.my_thermostat",
           "Volttron Point Name": "current_temperature",
           "Units": "F",
           "Units Details": "Current Ambient Temperature",
           "Writable": true,
           "Starting Value": 72,
           "Type": "float",
           "Notes": "Current temperature reading"
       },
       {
           "Entity ID": "climate.my_thermostat",
           "Volttron Point Name": "temperature",
           "Units": "F",
           "Units Details": "Desired Temperature",
           "Writable": true,
           "Starting Value": 75,
           "Type": "float",
           "Notes": "Target Temp"
       }
   ]

Attributes can be located in the developer tools in the Home Assistant GUI.

.. image:: https://github.com/riley206/Rileys_volttron/assets/89715390/a367e61e-8b73-4f35-a179-dfda235ddcbe

Transfer the registers files and the config files into the VOLTTRON config store using the commands below:

.. code-block:: bash

   vctl config store platform.driver light.example.json HomeAssistant_Driver/light.example.json
   vctl config store platform.driver devices/BUILDING/ROOM/light.example HomeAssistant_Driver/light.example.config

Upon completion, initiate the platform driver. Utilize the listener agent to verify the driver output:

.. code-block:: bash

   2023-09-12 11:37:00,226 (listeneragent-3.3 211531) __main__ INFO: Peer: pubsub, Sender: platform.driver:, Bus: , Topic: devices/BUILDING/ROOM/light.example/all, Headers: {'Date': '2023-09-12T18:37:00.224648+00:00', 'TimeStamp': '2023-09-12T18:37:00.224648+00:00', 'SynchronizedTimeStamp': '2023-09-12T18:37:00.000000+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
   [{'brightness': 254, 'state': 'on'},
    {'brightness': {'type': 'integer', 'tz': 'UTC', 'units': 'int'},
     'state': {'type': 'integer', 'tz': 'UTC', 'units': 'On / Off'}}]
