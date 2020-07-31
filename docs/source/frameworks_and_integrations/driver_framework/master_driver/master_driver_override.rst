.. _Master_Driver_Override:

======================
Master Driver Override
======================

By default, every user is allowed write access to the devices by the master driver. The override
feature will allow the user (for example, building administrator) to override this default
behavior and enable the user to lock the write access on the devices for a specified duration of
time or indefinitely.

Set Override On
---------------

The Master Driver's "set_override_on" RPC method can be used to set the override condition for
all drivers with topic matching the provided pattern. This can be specific devices, groups of
devices, or even all configured devices. The pattern matching is based on bash style filename
matching semantics.

Parameters:

     pattern:
        Override pattern to be applied. For example,
            If pattern is campus/building1/* - Override condition is applied for all the
            devices under campus/building1/.
            If pattern is campus/building1/ahu1 - Override condition is applied for only
            campus/building1/ahu1. The pattern matching is based on bash style filename
            matching semantics.
     duration:
        Time duration for the override in seconds. If duration <= 0.0, it implies as
        indefinite duration.
     failsafe_revert:
        Flag to indicate if all the devices falling under the override condition has to be set
        to its default state/value immediately.
     staggered_revert:
        If this flag is set, reverting of devices will be staggered.

Example "set_override_on" RPC call:

::

    self.vip.rpc.call(PLATFORM_DRIVER, "set_override_on", <override pattern>, <override duration>)

Set Override Off
----------------

The override condition can also be toggled off based on a provided pattern using the Master
Driver's "set_override_off" RPC call.

Parameters:

     pattern:
        Override pattern to be applied. For example,
            If pattern is campus/building1/* - Override condition is applied for all the
            devices under campus/building1/.
            If pattern is campus/building1/ahu1 - Override condition is applied for only
            campus/building1/ahu1. The pattern matching is based on bash style filename
            matching semantics.

Example "set_override_off" RPC call:

::

    self.vip.rpc.call(PLATFORM_DRIVER, "set_override_off", <override pattern>)

Get Override Devices
--------------------

A list of all overridden devices can be obtained with the Master Driver's "get_override_devices"
RPC call.

This method call has no additional parameters

Example "get_override_devices" RPC call:

::

    self.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices")

Get Override Patterns
---------------------

A list of all patterns which have been requested for override can be obtained with the Master
Driver's "get_override_patterns" RPC call.

This method call has no additional parameters

Example "get_override_patterns" RPC call:

::

    self.vip.rpc.call(PLATFORM_DRIVER, "get_override_patterns")

Clear Overrides
---------------

All overrides set by RPC calls described above can be toggled off at using a single
"clear_overrides" RPC call.

This method call has no additional parameters

Example "clear_overrides" RPC call:

::

    self.vip.rpc.call(PLATFORM_DRIVER, "clear_overrides")
