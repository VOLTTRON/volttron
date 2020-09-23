.. _IEEE2030_5-Specification:

=======================
IEEE 2030.5 DER Support
=======================

Version 1.0

Smart Energy Profile 2.0 (SEP 2.0, IEEE 2030.5) specifies a REST architecture built around the core HTTP verbs: GET,
HEAD, PUT, POST and DELETE.  A specification for the IEEE 2030.5 protocol can be found
`here <https://standards.ieee.org/content/dam/ieee-standards/standards/web/documents/presentations/smart_energy_slides.pdf>`_.

IEEE 2030.5 EndDevices (clients) POST XML resources representing their state, and GET XML resources containing command
and control information from the server.  The server never reaches out to the client unless a "subscription" is
registered and supported for a particular resource type.  This implementation does not use IEEE 2030.5 registered
subscriptions.

The IEEE 2030.5 specification requires HTTP headers, and it explicitly requires RESTful response codes, for example:

    -   201 - "Created"
    -   204 - "No Content"
    -   301 - "Moved Permanently"
    -   etc.

IEEE 2030.5 message encoding may be either XML or EXI.  Only XML is supported in this implementation.

IEEE 2030.5 requires HTTPS/TLS version 1.2 along with support for the cipher suite TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8.
Production installation requires a certificate issued by a IEEE 2030.5 CA.  The encryption requirement can be met by
using a web server such as Apache to proxy the HTTPs traffic.

IEEE 2030.5 discovery, if supported, must be implemented by an xmDNS server.  Avahi can be modified to perform this
function.


Function Sets
=============

IEEE 2030.5 groups XML resources into "Function Sets."  Some of these function sets provide a core set of functionality
used across higher-level function sets.  This implementation implements resources from the following function sets:

    -   Time
    -   Device Information
    -   Device Capabilities
    -   End Device
    -   Function Set Assignments
    -   Power Status
    -   Distributed Energy Resources


Distributed Energy Resources (DERs)
-----------------------------------

Distributed energy resources (DERs) are devices that generate energy, e.g., solar inverters, or store energy, e.g.,
battery storage systems, electric vehicle supply equipment (EVSEs).  These devices are managed by a IEEE 2030.5 DER
server using DERPrograms which are described by the IEEE 2030.5 specification as follows:

    Servers host one or more DERPrograms, which in turn expose DERControl events to DER clients.
    DERControl instances contain attributes that allow DER clients to respond to events
    that are targeted to their device type. A DERControl instance also includes scheduling
    attributes that allow DER clients to store and process future events. These attributes
    include start time and duration, as well an indication of the need for randomization of
    the start and / or duration of the event. The IEEE 2030.5 DER client model is based on the
    SunSpec Alliance Inverter Control Model [SunSpec] which is derived from
    IEC 61850-90-7 [61850] and [EPRI].

EndDevices post multiple IEEE 2030.5 resources describing their status.  The following is an
example of a Power Status resource that might be posted by an EVSE (vehicle charging station):

.. code-block:: xml

    <PowerStatus xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" href="/sep2/edev/96/ps">
        <batteryStatus>4</batteryStatus>
        <changedTime>1487812095</changedTime>
        <currentPowerSource>1</currentPowerSource>
        <estimatedChargeRemaining>9300</estimatedChargeRemaining>
        <PEVInfo>
            <chargingPowerNow>
                <multiplier>3</multiplier>
                <value>-5</value>
            </chargingPowerNow>
            <energyRequestNow>
                <multiplier>3</multiplier>
                <value>22</value>
            </energyRequestNow>
            <maxForwardPower>
                <multiplier>3</multiplier>
                <value>7</value>
            </maxForwardPower>
            <minimumChargingDuration>11280</minimumChargingDuration>
            <targetStateOfCharge>10000</targetStateOfCharge>
            <timeChargeIsNeeded>9223372036854775807</timeChargeIsNeeded>
            <timeChargingStatusPEV>1487812095</timeChargingStatusPEV>
        </PEVInfo>
    </PowerStatus>


Design Details
--------------

.. image:: files/volttron_ieee2030_5.jpg

VOLTTRON's IEEE 2030.5 implementation includes a IEEE 2030.5 Agent and a IEEE 2030.5 device driver, as described below.


VOLTTRON IEEE 2030.5 Device Driver
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The IEEE 2030.5 device driver is a new addition to VOLTTRON Master Driver Agent's family of standard device drivers.  It
exposes `get_point`/`set_point` calls for IEEE 2030.5 EndDevice fields.

The IEEE 2030.5 device driver periodically issues the IEEE 2030.5 Agent RPC calls to refresh its cached representation
of EndDevice data.  It issues RPC calls to the IEEE 2030.5 Agent as needed when responding to `get_point`, `set_point`
and `scrape_all` calls.

Field Definitions
^^^^^^^^^^^^^^^^^

These field IDs correspond to the ones in the IEEE 2030.5 device driver's configuration file, `ieee2030_5.csv`.
They have been used in that file's `Volttron Point Name` column and also in its `Point Name` column.

================= ============================= ==================================================== ======= ======
Field ID          IEEE 2030.5 Resource/Property Description                                          Units   Type
================= ============================= ==================================================== ======= ======
b1_Md             device_information            Model (32 char lim).                                         string
                    mfModel
b1_Opt            device_information            Long-form device identifier (32 char lim).                   string
                    lfdi
b1_SN             abstract_device               Short-form device identifier (32 char lim).                  string
                    sfdi
b1_Vr             device_information            Version (16 char lim).                                       string
                    mfHwVer
b113_A            mirror_meter_reading          AC current.                                          A       float
                    PhaseCurrentAvg
b113_DCA          mirror_meter_reading          DC current.                                          A       float
                    InstantPackCurrent
b113_DCV          mirror_meter_reading          DC voltage.                                          V       float
                    LineVoltageAvg
b113_DCW          mirror_meter_reading          DC power.                                            W       float
                    PhasePowerAvg
b113_PF           mirror_meter_reading          AC power factor.                                     %       float
                    PhasePFA
b113_WH           mirror_meter_reading          AC energy.                                           Wh      float
                    EnergyIMP
b120_AhrRtg       der_capability                Usable capacity of the battery.                      Ah      float
                    rtgAh                       Maximum charge minus minimum charge.
b120_ARtg         der_capability                Maximum RMS AC current level capability of the       A       float
                    rtgA                        inverter.
b120_MaxChaRte    der_capability                Maximum rate of energy transfer into the device.     W       float
                    rtgMaxChargeRate
b120_MaxDisChaRte der_capability                Maximum rate of energy transfer out of the device.   W       float
                    rtgMaxDischargeRate
b120_WHRtg        der_capability                Nominal energy rating of the storage device.         Wh      float
                    rtgWh
b120_WRtg         der_capability                Continuous power output capability of the inverter.  W       float
                    rtgW
b121_WMax         der_settings                  Maximum power output. Default to WRtg.               W       float
                    setMaxChargeRate
b122_ActWh        mirror_meter_reading          AC lifetime active (real) energy output.             Wh      float
                    EnergyEXP
b122_StorConn     der_status                    CONNECTED=0, AVAILABLE=1, OPERATING=2, TEST=3.               enum
                    storConnectStatus
b124_WChaMax      der_control                   Setpoint for maximum charge. This is the only        W       float
                    opModFixedFlow              field that is writable with a set_point call.
b403_Tmp          mirror_meter_reading          Pack temperature.                                    C       float
                    InstantPackTemp
b404_DCW          PEVInfo                       Power flow in or out of the inverter.                W       float
                    chargingPowerNow
b404_DCWh         der_availability              Output energy (absolute SOC).                        Wh      float
                    availabilityDuration        Calculated as (availabilityDuration / 3600) * WMax.
b802_LocRemCtl    der_status                    Control Mode: REMOTE=0, LOCAL=1.                             enum
                    localControlModeStatus
b802_SoC          der_status                    State of Charge %.                                   % WHRtg float
                    stateOfChargeStatus
b802_State        der_status                    DISCONNECTED=1, INITIALIZING=2, CONNECTED=3,                 enum
                    inverterStatus              STANDBY=4, SOC PROTECTION=5, FAULT=99.
================= ============================= ==================================================== ======= ======


Revising and Expanding the Field Definitions
--------------------------------------------

The IEEE 2030.5-to-SunSpec field mappings in this implementation are a relatively thin subset of all possible
field definitions.  Developers are encouraged to expand the definitions.

The procedure for expanding the field mappings requires you to make changes in two places:

1. Update the driver's point definitions in `services/core/MasterDriverAgent/master_driver/ieee2030_5.csv`
2. Update the IEEE 2030.5-to-SunSpec field mappings in `services/core/IEEE2030_5Agent/ieee2030_5/end_device.py` and
   `__init__.py`

When updating VOLTTRON's IEEE 2030.5 data model, please use field IDs that conform to the SunSpec
block-number-and-field-name model outlined in the SunSpec Information Model Reference (see the link below).


For Further Information
=======================

SunSpec References:

    -   Information model specification: http://sunspec.org/wp-content/uploads/2015/06/SunSpec-Information-Models-12041.pdf
    -   Information model reference spreadsheet: http://sunspec.org/wp-content/uploads/2015/06/SunSpec-Information-Model-Reference.xlsx
    -   Inverter models: http://sunspec.org/wp-content/uploads/2015/06/SunSpec-Inverter-Models-12020.pdf
    -   Energy storage models: http://sunspec.org/wp-content/uploads/2015/06/SunSpec-Energy-Storage-Models-12032.pdf

Questions? Please contact:

    -   Rob Calvert (rob@kisensum.com) or James Sheridan (james@kisensum.com)
