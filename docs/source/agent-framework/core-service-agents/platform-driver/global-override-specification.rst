.. _Global-Override-Specification:

=============================
Global Override Specification
=============================

This document describes the specification for the global override feature.  By default, every user is allowed write
access to the devices by the platform driver.  The override feature will allow the user (for example, a building
administrator) to override this default behavior and enable the user to lock the write access on the devices for a
specified duration of time or indefinitely.


Functional Capabilities
=======================

1. User shall be able to specify the following when turning on the override behavior on the devices.

    * Override pattern examples:

         * If pattern is ``campus/building1/*`` - Override condition is turned on for all the devices under
           `campus/building1/`.

         * If pattern is ``campus/building1/ahu1`` - Override condition is turned on for only `campus/building1/ahu1`

         * The pattern matching shall use bash style filename matching semantics.

    * Time duration over which override behavior is applicable - If the time duration is negative, then the override
      condition is applied indefinitely.

    * Optional `revert-to-fail-safe-state` flag - If the flag is set, the platform driver shall set all the set points
      falling under the override condition to its default state/value immediately.  This is to ensure that the devices
      are in fail-safe state when the override/lock feature is removed.  If the flag is not set, the device state/value
      is untouched.

    * Optional staggered revert flag - If this flag is set, reverting of devices will be staggered.

2. User shall be able to disable/turn off the override behavior on devices by specifying:

    * Pattern on which the override/lock feature has be disabled. (example: ``campus/building/\*``)

3. User shall be able to get a list of all the devices with the override condition set.

4. User shall be able to get a list of all the override patterns that are currently active.

5. User shall be able to clear all the overrides.

6. Any changes to override patterns list shall be stored in the config store.  On startup, list of override patterns and
   corresponding end times are retrieved from the config store.  If the end time is indefinite or greater than current
   time for any pattern, then override is set on the matching devices for remaining duration of time.

7. Whenever a device is newly configured, a check is made to see if it is part of the overridden patterns.  If yes, it
   is added to list of overridden devices.

8. When a device is being removed, a check is made to see if it is part of the overridden devices.  If yes, it is
   removed from the list of overridden devices.


Driver RPC Methods
******************

- *set_override_on(pattern, duration=0.0, failsafe_revert=True, staggered_revert=True)* - Turn on override condition on all the devices matching the pattern. Time duration for the override condition has to be in seconds. For indefinite duration, the time duration has to be <= 0.0.

- *set_override_off(pattern)* - Turn off override condition on all the devices matching the pattern.  The specified
  pattern will be removed from the override patterns list. All the devices falling under the given pattern will be
  removed from the list of overridden devices.

- *get_override_devices()* - Get a list of all the devices with override condition.

- *get_override_patterns()* - Get a list of override patterns that are currently active.

- *clear_overrides()* - Clear all the overrides.
