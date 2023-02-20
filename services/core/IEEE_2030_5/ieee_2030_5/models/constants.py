import enum
""" Metering
"""


class RtgNormalCategoryType(enum.IntEnum):
    not_specified = 0
    category_a = 1
    category_b = 2


class RtgAbnormalCategoryType(enum.IntEnum):
    not_specified = 0
    category_I = 1
    category_II = 2
    category_III = 3


class DataQualifierType(enum.IntEnum):
    Not_applicable = 0
    Average = 2
    Maximum = 8
    Minimum = 9
    Normal = 12
    Standard_deviation_of_population = 29
    Standard_deviation_of_sample = 30


class CommodityType(enum.IntEnum):
    Not_applicable = 0
    Electricity_secondary_metered = 1
    Electricity_primary_metered = 2
    Air = 4
    NaturalGas = 7
    Propane = 8
    PotableWater = 9
    Steam = 10
    WasteWater = 11
    HeatingFluid = 12
    CoolingFluid = 13


class FlowDirectionType(enum.IntEnum):
    Not_applicable = 0
    Forward = 1
    Reverse = 19


class UomType(enum.IntEnum):
    Not_applicable = 0
    Amperes = 5
    Kelvin = 6
    Degrees_celsius = 23
    Voltage = 29
    Joule = 31
    Hz = 33
    W = 38
    M_cubed = 42
    VA = 61
    VAr = 63
    CosTheta = 65
    V_squared = 67
    A_squared = 69
    VAh = 71
    Wh = 72
    VArh = 73
    Ah = 106
    Ft_cubed = 119
    Ft_cubed_per_hour = 122
    M_cubed_per_hour = 125
    US_gallons = 128
    UG_gallons_per_hour = 129
    Imperial_gallons = 130
    Imperial_gallons_per_hour = 131
    BTU = 132
    BTU_per_hour = 133
    Liter = 134
    Liter_per_hour = 137
    PA_gauge = 140
    PA_absolute = 155
    Therm = 169


class RoleFlagsType(enum.Flag):
    IsMirror = 0
    IsPremiseAggregationPoint = 1
    IsPEV = 2
    IsDER = 4
    IsRevenueQuality = 8
    IsDC = 16
    IsSubmeter = 32


class AccumlationBehaviourType(enum.IntEnum):
    Not_applicable = 0
    Cumulative = 3
    DeltaData = 4
    Indicating = 6
    Summation = 9
    Instantaneous = 12


class ServiceKind(enum.IntEnum):
    Electricity = 0
    Gas = 1
    Water = 2
    Time = 3
    Pressure = 4
    Heat = 5
    Cooling = 6


class QualityFlagsType(enum.Flag):
    Valid = 0
    Manually_edited = 1
    estimated_using_reference_day = 2
    estimated_using_linear_interpolation = 4
    questionable = 8
    derived = 16
    projected = 32


# p163
class ConsumptionBlockType(enum.IntEnum):
    Not_applicable = 0
    Block_1 = 1
    Block_2 = 2
    Block_3 = 3
    Block_4 = 4
    Block_5 = 5
    Block_6 = 6
    Block_7 = 7
    Block_8 = 8
    Block_9 = 9
    Block_10 = 10
    Block_11 = 11
    Block_12 = 12
    Block_13 = 13
    Block_14 = 14
    Block_15 = 15
    Block_16 = 16


# p170
class TOUType(enum.IntEnum):
    Not_applicable = 0
    TOU_A = 1
    TOU_B = 2
    TOU_C = 3
    TOU_D = 4
    TOU_E = 5
    TOU_F = 6
    TOU_G = 7
    TOU_H = 8
    TOU_I = 9
    TOU_J = 10
    TOU_K = 11
    TOU_L = 12
    TOU_M = 13
    TOU_N = 14
    TOU_O = 15


class KindType(enum.IntEnum):
    Not_applicable = 0
    Currency = 3
    Demand = 8
    Energy = 12
    Power = 37


class PhaseCode(enum.IntEnum):
    Not_applicable = 0
    Phase_C = 32    # and S2
    Phase_CN = 33    # and S2N
    Phase_CA = 40
    Phase_B = 64
    Phase_BN = 65
    Phase_BC = 66
    Phase_A = 128    # and S1
    Phase_AN = 129    # and S1N
    Phase_AB = 132
    Phase_ABC = 224


""" Subscription/Notification
"""


class ResponseRequiredType(enum.Flag):
    enddevice_shall_indicate_that_message_was_received = 0
    enddevice_shall_indicate_specific_response = 1
    enduser_customer_response_is_required = 2


class SubscribableType(enum.IntEnum):
    resource_does_not_support_subscriptions = 0
    resource_supports_non_conditional_subscriptions = 1
    resource_supports_conditional_subscriptions = 2
    resource_supports_both_conditional_and_non_conditional_subscriptions = 3
