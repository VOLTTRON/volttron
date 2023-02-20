from enum import IntEnum


class DeviceCategoryType(IntEnum):
    """
    DeviceCategoryType defined from 20305-2018_IIEStandardforSmartEnergyProfileApplicationsProtocol.pdf Appendix
    B.2.3.4 Types package
    """
    # The Device category types defined.
    # Bit positions SHALL be defined as follows:
    PROGRAMMABLE_COMMUNICATING_THERMOSTAT = 0
    STRIP_HEATERS = 1
    BASEBOARD_HEATERS = 2
    WATER_HEATER = 3
    POOL_PUMP = 4
    SAUNA = 5
    HOT_TUB = 6
    SMART_APPLIANCE = 7
    IRRIGATION_PUMP = 8
    MANAGED_COMMERCIAL_AND_INDUSTRIAL_LOADS = 9
    SIMPLE_RESIDENTIAL_LOADS = 10   # On/Off loads
    EXTERIOR_LIGHTING = 11
    INTERIOR_LIGHTING = 12
    LOAD_CONTROL_SWITCH = 13
    ENERGY_MANAGEMENT_SYSTEM = 14
    SMART_ENERGY_MODULE = 15
    ELECTRIC_VEHICLE = 16
    ELECTRIC_VEHICLE_SUPPLY_EQUIPMENT = 17
    VIRTUAL_OR_MIXED_DER = 18
    RECIPROCATING_ENGINE = 19  # Synchronous Machine
    FUEL_CELL = 20  # Battery
    PHOTOVOLTAIC_SYSTEM = 21  # Solar
    COMBINED_HEAT_AND_POWER = 22
    COMBINED_PV_AND_STORAGE = 23
    OTHER_GENERATION_SYSTEMS = 24
    OTHER_STORAGE_SYSTEMS = 25

    # Additional here for Aggregator
    AGGREGATOR = 99
    OTHER_CLIENT = 100


#     0 - Programmable Communicating Thermostat
#     1 - Strip Heaters
#     2 - Baseboard Heaters
#     3 - Water Heater
#     4 - Pool Pump
#     5 - Sauna
#     6 - Hot tub
#     7 - Smart Appliance
#     8 - Irrigation Pump
#     9 - Managed Commercial and Industrial Loads
#     10 - Simple Residential Loads
#     11 - Exterior Lighting
#     12 - Interior Lighting
#     13 - Electric Vehicle
#     14 - Generation Systems
#     15 - Load Control Switch
#     16 - Smart Inverter
#     17 - EVSE
#     18 - Residential Energy Storage Unit
#     19 - Energy Management System
#     20 - Smart Energy Module
