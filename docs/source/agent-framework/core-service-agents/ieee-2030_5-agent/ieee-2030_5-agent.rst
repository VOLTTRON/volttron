.. _IEEE-2030_5-Agent:

=====================
IEEE 2030.5 DER Agent
=====================

The IEEE 2030.5 Agent (IEEE2030_5 in the VOLTTRON repository) implements a IEEE 2030.5 server that receives HTTP
`POST`/`PUT` requests from IEEE 2030.5 devices.  The requests are routed to the IEEE 2030.5 Agent over the VOLTTRON
message bus by VOLTTRON's Master Web Service.  The IEEE 2030.5 Agent returns an appropriate HTTP response.  In some
cases (e.g., DERControl requests), this response includes a data payload.

The IEEE 2030.5 Agent maps IEEE 2030.5 resource data to a VOLTTRON IEEE 2030.5 data model based on SunSpec, using block
numbers and point names as defined in the SunSpec Information Model, which in turn is harmonized with 61850.  The data
model is given in detail below.

Each device's data is stored by the IEEE 2030.5 Agent in an `EndDevice` memory structure.  This structure is not
persisted to a database.  Each `EndDevice` retains only the most recently received value for each field.

The IEEE2030_5 Agent exposes RPC calls for getting and setting EndDevice data.


VOLTTRON IEEE 2030.5 Device Driver
----------------------------------

The :ref:`IEEE 2030.5 device driver <IEEE-2030_5-Driver>` is a new addition to VOLTTRON Master Driver Agent's
family of standard device drivers.  It exposes ``get_point``/``set_point calls`` for IEEE 2030.5 EndDevice fields.

The IEEE 2030.5 device driver periodically issues IEEE2030_5 Agent RPC calls to refresh its cached representation of
EndDevice data.  It issues RPC calls to IEEE2030_5Agent as needed when responding to ``get_point``, ``set_point`` and
``scrape_all`` calls.


Field Definitions
^^^^^^^^^^^^^^^^^

These field IDs correspond to the ones in the IEEE 2030.5 device driver's configuration file, ``ieee2030_5.csv``.
They have been used in that file's "Volttron Point Name" column and also in its "Point Name" column.

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The IEEE 2030.5-to-SunSpec field mappings in this implementation are a relatively thin subset of all possible
field definitions. Developers are encouraged to expand the definitions.

The procedure for expanding the field mappings requires you to make changes in two places:

1. Update the driver's point definitions in ``services/core/MasterDriverAgent/master_driver/ieee2030_5.csv``
2. Update the IEEE 2030.5-to-SunSpec field mappings in ``services/core/IEEE2030_5Agent/ieee2030_5/end_device.py`` and
   ``__init__.py``

When updating VOLTTRON's IEEE 2030.5 data model, please use field IDs that conform to the SunSpec
block-number-and-field-name model outlined in the SunSpec Information Model Reference (see the link below).

View the :ref:`IEEE 2030.5 agent specification document <IEEE-2030_5-Specification>` to learn more about IEEE 2030.5 and
the IEEE 2030.5 agent and driver.


.. toctree::

   ieee-2030_5-specification
