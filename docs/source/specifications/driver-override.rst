.. _DriverOverride:

Driver Override Specification
==============================
This document describes the specification for the global override feature.
By default, every user is allowed write access to the devices by the master driver. The override feature will allow the user (for example, building administrator) to override this default behavior and enable the user to lock the write access on the devices for specified duration of time .

Functional Capabilities
-----------------------------

1. User shall be able to specify the following when turning on the override behavior on the devices.

    * Override pattern, for example,

         If pattern is campus/building1/* - Override condition is turned on for all the devices under campus/building1

         If pattern is campus/building1/ahu1 - Override condition is turned on for only campus/building1/ahu1

    * Time duration over which override behavior is applicable.

    * Optional revert-to-fail-safe-state flag. If the flag is set, master driver shall set all the set points falling under the override condition to its default state/value immediately. This is to ensure that the devices are in fail-safe state when the override/lock feature is removed. If the flag is not set, the device state/value is untouched.

    * Optional staggered revert flag. If this flag is set, reverting of devices will be staggered.

2. User shall be able to disable/turn off the override behavior on devices by specifying:

    * Pattern on which the override/lock feature has be disabled. (example: campus/building/*)

3. User shall be able to get a list of all the devices with the override condition set.

4. User shall be able to get a list of all the override patterns that are currently active.

5. User shall be able to clear all the overrides.

Driver RPC Methods
********************
set_override_on( pattern, duration=1.0, failsafe_revert=True, staggered_revert=True ) - Turn on override condition on all the devices matching the pattern.

set_override_off( pattern ) - Turn off override condition on all the devices matching the pattern.

get_override_devices( ) - Get a list of all the devices with override condition.

get_override_patterns( ) - Get a list of override patterns that are currently active.

clear_overrides( ) - Clear all the overrides.

