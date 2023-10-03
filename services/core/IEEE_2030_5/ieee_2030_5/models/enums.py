from enum import IntEnum


class PrimacyType(IntEnum):
    # Values possible for indication of "Primary" provider:
    # 0: In home energy management system
    # 1: Contracted premises service provider
    # 2: Non-contractual service provider
    # 3 - 64: Reserved
    # 65 - 191: User-defined
    #192 - 255: Reserved
    InHomeManagementSystem = 0
    ContractedPremisesServiceProvider = 1
    NonContractualServiceProvider = 2
        

class DERUnitRefType(IntEnum):
    # 0 - N/A
    # 1 - %setMaxW
    # 2 - %setMaxVar
    # 3 - %statVarAvail
    # 4 - %setEffectiveV
    # 5 - %setMaxChargeRateW
    # 6 - %setMaxDischargeRateW
    # 7 - %statWAvail
    NA = 0
    setMaxW = 1
    setMaxVar = 2
    statVarAvail = 3
    setEffectiveV = 4
    setMaxChargeRateW = 5
    setMaxDischargeRateW = 6
    statWAvail = 7

class CurveType(IntEnum):
    # 0 - opModFreqWatt (Frequency-Watt Curve Mode)
    # 1 - opModHFRTMayTrip (High Frequency Ride Through, May Trip Mode)
    # 2 - opModHFRTMustTrip (High Frequency Ride Through, Must Trip Mode)
    # 3 - opModHVRTMayTrip (High Voltage Ride Through, May Trip Mode)
    # 4 - opModHVRTMomentaryCessation (High Voltage Ride Through, Momentary Cessation
    # Mode)
    # 5 - opModHVRTMustTrip (High Voltage Ride Through, Must Trip Mode)
    # 6 - opModLFRTMayTrip (Low Frequency Ride Through, May Trip Mode)
    # 7 - opModLFRTMustTrip (Low Frequency Ride Through, Must Trip Mode)
    # 8 - opModLVRTMayTrip (Low Voltage Ride Through, May Trip Mode)
    # 9 - opModLVRTMomentaryCessation (Low Voltage Ride Through, Momentary Cessation
    # Mode)
    # 10 - opModLVRTMustTrip (Low Voltage Ride Through, Must Trip Mode)
    # 11 - opModVoltVar (Volt-Var Mode)
    # 12 - opModVoltWatt (Volt-Watt Mode)
    # 13 - opModWattPF (Watt-PowerFactor Mode)
    # 14 - opModWattVar (Watt-Var Mode)
    opModFreqWatt = 0
    opModHFRTMayTrip = 1
    opModHFRTMustTrip = 2
    opModHVRTMayTrip = 3
    opModHVRTMomentaryCessation = 4
    opModHVRTMustTrip = 5
    opModLFRTMayTrip = 6
    opModLFRTMustTrip = 7
    opModLVRTMayTrip = 8
    opModLVRTMomentaryCessation = 9
    opModLVRTMustTrip = 10
    opModVoltVar = 11
    opModVoltWatt = 12
    opModWattPF = 13
    opModWattVar = 14


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
    SIMPLE_RESIDENTIAL_LOADS = 10    # On/Off loads
    EXTERIOR_LIGHTING = 11
    INTERIOR_LIGHTING = 12
    LOAD_CONTROL_SWITCH = 13
    ENERGY_MANAGEMENT_SYSTEM = 14
    SMART_ENERGY_MODULE = 15
    ELECTRIC_VEHICLE = 16
    ELECTRIC_VEHICLE_SUPPLY_EQUIPMENT = 17
    VIRTUAL_OR_MIXED_DER = 18
    RECIPROCATING_ENGINE = 19    # Synchronous Machine
    FUEL_CELL = 20    # Battery
    PHOTOVOLTAIC_SYSTEM = 21    # Solar
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
