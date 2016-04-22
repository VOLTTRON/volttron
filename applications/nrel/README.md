##Directory to release VOLTTRON agents

**Directory structure**

NREL:

    bin:
        functional_test.sh
        start.sh

    agents:
        RadioThermostatRelayAgent
        CEA2045RelayAgent
        VolttimeAgent
        SC_HouseAgent

    docs:
        README.md
        requiremtnts.txt
        topics.txt

    Makefile:

    README.md    


**Agents:**

**CEA-2045:**

The CEA-2045 standard specifies a modular communications interface (MCI) to facilitate communications with residential devices for applications such as energy management. The MCI provides a standard interface for energy management signals and messages to reach devices. Typical devices include energy management controllers, appliances, sensors, and other consumer products. CEA-2045 standard is analogous to the USB standard for the computer electronics; any residential devices that is CEA-2045 compliant should be play-and-plug.

**Radio Thermostat:**

Implementing the most common functions.
Radio Thermostat Company of America, Wi-Fi USNAP Module API, Version 1.3, March 22, 2012. Available on http://lowpowerlab.com/downloads/RadioThermostat_CT50_Honeywell_Wifi_API_V1.3.pdf. Retrieved on April 6, 2016.

**SC_House-Agent:**

Shows example controls for the Relays

**Volttime-Agent:**

Synchronize time

**For information on using the agents refer to docs/README.md**
