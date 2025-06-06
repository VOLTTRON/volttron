# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
"""
==================
Driver Development
==================

New drivers are implemented by subclassing :py:class:`BaseInterface`.

While it is possible to create an Agent which handles communication with a new device
it will miss out on the benefits of creating a proper interface for the
Platform Driver Agent.

Creating an Interface for a device allows users of the device to automatically benefit
from the following platform features:

- Existing Agents can interact with the device via the Actuator Agent without any code changes.
- Configuration follows the standard form of other devices. Existing and future tools
    for configuring devices on the platform will work with the new device driver.
- Historians will automatically capture data published by the new device driver.
- Device data can be graphed in VOLTTRON Central in real time.
- If the device can receive a heartbeat signal the driver framework can be configured to
   automatically send a heartbeat signal.

- When the configuration store feature is rolled out the device can by dynamically configured
   through the platform.

Creating a New Interface
------------------------

To create a new device driver create a new module in the
:py:mod:`PlatformDriverAgent.platform_driver.interfaces` package. The name of
this module will be the name to use in the "driver_type" setting in
a :ref:`driver configuration file <Driver-configuration-file>` in order to
load the new driver.

In the new module create a subclass of :py:class:`BaseInterface` called `Interface`.

The `Interface` class must implement the following methods:

- :py:meth:`BaseInterface.configure`
- :py:meth:`BaseInterface.set_point`
- :py:meth:`BaseInterface.get_point`
- :py:meth:`BaseInterface.scrape_all`


These methods are required but can be implemented using the :py:class:`BasicRevert` mixin.

- :py:meth:`BaseInterface.revert_point`
- :py:meth:`BaseInterface.revert_all`

Each point on the device must be represented by an instance of the
:py:class:`BaseRegister`. Create one or more subclasses of :py:class:`BaseRegister`
as needed to represent the points on a device.


Interface Configuration and Startup
-----------------------------------

When processing a :ref:`driver configuration file <Driver-configuration-file>`
the Platform Driver Agent will use the "driver_type" setting to automatically find and load the
appropriate ``Interface`` class for the desired driver.

After loading the class the Platform Driver Agent will call :py:meth:`BaseInterface.configure`
with the contents of the "driver_config" section of the
:ref:`driver configuration file <Driver-Configuration-File>`
parsed into a python dictionary and the contents of the file referenced in
"registry_config" entry.

:py:meth:`BaseInterface.configure` must setup register representations of all points
on a device by creating instances of :py:class:`BaseRegister` (or a subclass) and adding them
to the Interface with :py:meth:`BaseInterface.insert_register`.

After calling :py:meth:`BaseInterface.configure` the Platform Driver Agent
will use the created registers to create meta data for each point on the device.

Device Scraping
---------------

The work scheduling and publish periodic device scrapes is handled by
the Platform Driver Agent. When a scrape starts the Platform Driver Agent calls the
:py:meth:`BaseInterface.scrape_all`. It will take the results of the
call and attach meta data and and publish as needed.

Device Interaction
------------------

Requests to interact with the device via any method supported by the platform
are routed to the correct Interface instance by the Platform Driver Agent.

Most commands originate from RPC calls to the
:py:class:`Actuator Agent<ActuatorAgent.actuator.agent>` and are forwarded
to the Platform Driver Agent.

- A command to set the value of a point on a device results in a call to
    :py:meth:`BaseInterface.set_point`.

- A request for the current value of a point on a device results in a call to
    :py:meth:`BaseInterface.get_point`.

- A request to revert a point on a device to its default state results in a call to
    :py:meth:`BaseInterface.revert_point`.

- A request to revert an entire device to its default state results in a call to
    :py:meth:`BaseInterface.revert_all`.


Registers
---------

The Platform Driver Agent uses the :py:meth:`BaseInterface.get_register_names` and
:py:meth:`BaseInterface.get_register_by_name` methods to get registers to setup meta data.

This means that its a requirement to use the BaseRegister class to store
information about points on a devices.


Using the BasicRevert Mixin
---------------------------

If the device protocol has no support for reverting to a default state an `Interface`
this functionality can be implemented with the :py:class:`BasicRevert` mixin.

When using the :py:class:`BasicRevert` mixin you must specify it first in the list
of parent classes, otherwise it won't Python won't detect that the
:py:meth:`BaseInterface.revert_point` and :py:meth:`BaseInterface.revert_all` have
been implemented.

If desired the :py:meth:`BasicRevert.set_default` can be used by the `Interface` class
to set values for each point to revert to.

"""

import abc
import logging
from typing import List

_log = logging.getLogger(__name__)


class DriverInterfaceError(Exception):
    pass


class BaseRegister:
    """
    Class for containing information about a point on a device.
    Should be extended to support the device protocol to
    be supported.

    The member variable ``python_type`` should be overridden with the equivalent
    python type object. Defaults to ``int``. This is used to generate meta data.

    :param register_type: Type of the register. Either "bit" or "byte". Usually "byte".
    :param read_only: Specify if the point can be written to.
    :param pointName: Name of the register.
    :param units: Units of the value of the register.
    :param description: Description of the register.

    :type register_type: str
    :type read_only: bool
    :type pointName: str
    :type units: str
    :type description: str

    The Platform Driver Agent will use :py:meth:`BaseRegister.get_units` to populate metadata for
    publishing. When instantiating register instances be sure to provide a useful
    string for the units argument.
    """

    def __init__(self, register_type, read_only, pointName, units, description=''):
        self.read_only = read_only
        self.register_type = register_type
        self.point_name = pointName
        self.units = units
        self.description = description
        self.python_type = int

    def get_register_python_type(self):
        """
        :return: The python type of the register.
        :rtype: type
        """
        return self.python_type

    def get_register_type(self):
        """
        :return: (register_type, read_only)
        :rtype: tuple
        """
        return self.register_type, self.read_only

    def get_units(self):
        """
        :return: Register units
        :rtype: str
        """
        return self.units

    def get_description(self):
        """
        :return: Register description
        :rtype: str
        """
        return self.description


class BaseInterface(object, metaclass=abc.ABCMeta):
    """
    Main class for implementing support for new devices.

    All interfaces *must* subclass this.

    :param vip: A reference to the PlatformDriverAgent vip subsystem.
    :param core: A reference to the parent driver agent's core subsystem.

    """

    def __init__(self, vip=None, core=None, device_path=None, **kwargs):
        # Object does not take any arguments to the init.
        super(BaseInterface, self).__init__()
        self.vip = vip
        self.core = core
        self.device_path = device_path
        self.point_map = {}

        self.build_register_map()

    def build_register_map(self):
        self.registers = {
            ('byte', True): [],
            ('byte', False): [],
            ('bit', True): [],
            ('bit', False): []
        }

    @abc.abstractmethod
    def configure(self, config_dict, registry_config_str):
        """
        Configures the :py:class:`Interface` for the specific instance of a device.

        :param config_dict: The "driver_config" section of the driver configuration file.
        :param registry_config_str: The contents of the registry configuration file.
        :type config_dict: dict
        :type registry_config_str: str


        This method must setup register representations of all points
        on a device by creating instances of :py:class:`BaseRegister` (or a subclass) and adding them
        to the Interface with :py:meth:`BaseInterface.insert_register`.
        """
        pass

    def get_register_by_name(self, name):
        """
        Get a register by it's point name.

        :param name: Point name of register.
        :type name: str
        :return: An instance of BaseRegister
        :rtype: :py:class:`BaseRegister`
        """
        try:
            return self.point_map[name]
        except KeyError:
            raise DriverInterfaceError("Point not configured on device: " + name)

    def get_register_names(self):
        """
        Get a list of register names.
        :return: List of names
        :rtype: list
        """
        return list(self.point_map.keys())

    def get_register_names_view(self):
        """
        Get a dictview of register names.
        :return: Dictview of names
        :rtype: dictview
        """
        return self.point_map.keys()

    def get_registers_by_type(self, reg_type, read_only) -> List[BaseRegister]:
        """
        Get a list of registers by type. Useful for an :py:class:`Interface` that needs to categorize
        registers by type when doing a scrape.

        :param reg_type: Register type. Either "bit" or "byte".
        :type reg_type: str
        :param read_only: Specify if the desired registers are read only.
        :type read_only: bool
        :return: An list of BaseRegister instances.
        :rtype: list
        """
        return self.registers[reg_type, read_only]

    def insert_register(self, register):
        """
        Inserts a register into the :py:class:`Interface`.

        :param register: Register to add to the interface.
        :type register: :py:class:`BaseRegister`
        """
        register_point = register.point_name
        self.point_map[register_point] = register

        register_type = register.get_register_type()
        self.registers[register_type].append(register)

    @abc.abstractmethod
    def get_point(self, point_name, **kwargs):
        """
        Get the current value for the point name given.

        :param point_name: Name of the point to retrieve.
        :param kwargs: Any interface specific parameters.
        :type point_name: str
        :return: Point value
        """

    @abc.abstractmethod
    def set_point(self, point_name, value, **kwargs):
        """
        Set the current value for the point name given.

        Implementations of this method should make a reasonable
        effort to return the actual value the point was
        set to. Some protocols/devices make this difficult.
        (I'm looking at you BACnet) In these cases it is
        acceptable to return the value that was requested
        if no error occurs.

        :param point_name: Name of the point to retrieve.
        :param value: Value to set the point to.
        :param kwargs: Any interface specific parameters.
        :type point_name: str
        :return: Actual point value set.
        """

    @abc.abstractmethod
    def scrape_all(self):
        """
        Method the Platform Driver Agent calls to get the current state
        of a device for publication.

        :return: Point names to values for device.
        :rtype: dict
        """

    @abc.abstractmethod
    def revert_all(self, **kwargs):
        """
        Revert entire device to it's default state

        :param kwargs: Any interface specific parameters.
        """

    @abc.abstractmethod
    def revert_point(self, point_name, **kwargs):
        """
        Revert point to it's default state.

        :param kwargs: Any interface specific parameters.
        """

    def get_multiple_points(self, path, point_names, **kwargs):
        """
        Read multiple points from the interface.

        :param path: Device path
        :param point_names: Names of points to retrieve
        :param kwargs: Any interface specific parameters
        :type path: str
        :type point_names: [str]
        :type kwargs: dict

        :returns: Tuple of dictionaries to results and any errors
        :rtype: (dict, dict)
        """
        results = {}
        errors = {}

        for point_name in point_names:
            return_key = path + '/' + point_name
            try:
                value = self.get_point(point_name, **kwargs)
                results[return_key] = value
            except Exception as e:
                errors[return_key] = repr(e)

        return results, errors

    def set_multiple_points(self, path, point_names_values, **kwargs):
        """
        Set multiple points on the interface.

        :param path: Device path
        :param point_names_values: Point names and values to be set to.
        :param kwargs: Any interface specific parameters
        :type path: str
        :type point_names: [(str, k)] where k is the new value
        :type kwargs: dict

        :returns: Dictionary of points to any exceptions raised
        :rtype: dict
        """
        results = {}

        for point_name, value in point_names_values:
            try:
                self.set_point(point_name, value, **kwargs)
            except Exception as e:
                results[path + '/' + point_name] = repr(e)

        return results


class RevertTracker:
    """
    A helper class for tracking the state of writable points on a device.
    """

    def __init__(self):
        self.defaults = {}
        self.clean_values = {}
        self.dirty_points = set()

    def update_clean_values(self, points):
        """
        Update all state of all the clean point values for a device.

        If a point is marked dirty it will not be updated.

        :param points: dict of point names to values.
        :type points: dict
        """
        clean_values = {}
        for k, v in points.items():
            if k not in self.dirty_points and k not in self.defaults:
                clean_values[k] = v
        self.clean_values.update(clean_values)

    def set_default(self, point, value):
        """
        Set the value to revert a point to. Overrides any clean value detected.

        :param point: name of point to set.
        :param value: value to set the point to.
        :type point: str
        """
        self.defaults[point] = value

    def get_revert_value(self, point):
        """
        Returns the clean value for a point if no default is set, otherwise returns
        the default value.

        If no default value is set and a no clean values have been submitted
        raises :py:class:`DriverInterfaceError`.

        :param point: Name of point to get.
        :type point: str
        :return: Value to revert to.
        """
        if point in self.defaults:
            return self.defaults[point]
        if point not in self.clean_values:
            raise DriverInterfaceError("Nothing to revert to for {}".format(point))

        return self.clean_values[point]

    def clear_dirty_point(self, point):
        """
        Clears the dirty flag on a point.

        :param point: Name of dirty point flag to clear.
        :type point: str
        """
        self.dirty_points.discard(point)

    def mark_dirty_point(self, point):
        """
        Sets the dirty flag on a point.

        Ignores points with a default value.

        :param point: Name of point flag to dirty.
        :type point: str
        """
        if point not in self.defaults:
            self.dirty_points.add(point)

    def get_all_revert_values(self):
        """
        Returns a dict of points to revert values.

        If no default is set use the clean value, otherwise returns
        the default value.

        If no default value is set and a no clean values have been submitted
        a point value will be an instance of :py:class:`DriverInterfaceError`.

        :param point: Name of point to get.
        :type point: str
        :return: Values to revert to.
        :rtype: dict
        """
        results = {}
        for point in self.dirty_points.union(self.defaults):
            try:
                results[point] = self.get_revert_value(point)
            except DriverInterfaceError:
                results[point] = DriverInterfaceError()

        return results


class BasicRevert(object, metaclass=abc.ABCMeta):
    """
    A mixin that implements the :py:meth:`BaseInterface.revert_all`
    and :py:meth:`BaseInterface.revert_point` methods on an
    :py:class:`Interface`.

    It works by tracking change to all writable points until a `set_point` call
    is made. When this happens the point is marked dirty and the previous
    value is remembered. When a point is reverted via either a `revert_all`
    or `revert_point` call the dirty values are set back to the clean value
    using the :py:meth:`BasicRevert._set_point` method.

    As it must hook into the setting and scraping of points it implements the
    :py:meth:`BaseInterface.scrape_all` and :py:meth:`BaseInterface.set_point`
    methods. It then adds :py:meth:`BasicRevert._set_point` and
    :py:meth:`BasicRevert._scrape_all` to the abstract interface. An existing
    interface that wants to use this class can simply mix it in and
    rename it's `set_point` and `scrape_all` methods to `_set_point` and
    `_scrape_all` respectively.

    An :py:class:`BaseInterface` may also override the detected clean value with
    its own value to revert to by calling :py:meth:`BasicRevert.set_default`.
    While default values can be set anytime they
    should be set in the :py:meth:`BaseInterface.configure` call.

    """

    def __init__(self, **kwargs):
        super(BasicRevert, self).__init__(**kwargs)
        self._tracker = RevertTracker()

    def _update_clean_values(self, points):
        self._tracker.update_clean_values(points)

    def set_default(self, point, value):
        """
        Set the value to revert a point to.

        :param point: name of point to set.
        :param value: value to set the point to.
        :type point: str
        """
        self._tracker.set_default(point, value)

    def set_point(self, point_name, value):
        """
        Implementation of :py:meth:`BaseInterface.set_point`

        Passes arguments through to :py:meth:`BasicRevert._set_point`
        """
        result = self._set_point(point_name, value)
        self._tracker.mark_dirty_point(point_name)
        return result

    def scrape_all(self):
        """
        Implementation of :py:meth:`BaseInterface.scrape_all`
        """
        result = self._scrape_all()
        self._update_clean_values(result)

        return result

    @abc.abstractmethod
    def _set_point(self, point_name, value):
        """
        Set the current value for the point name given.

        If using this mixin you must override this method
        instead of :py:meth:`BaseInterface.set_point`. Otherwise
        the purpose is exactly the same.

        Implementations of this method should make a reasonable
        effort to return the actual value the point was
        set to. Some protocols/devices make this difficult.
        (I'm looking at you BACnet) In these cases it is
        acceptable to return the value that was requested
        if no error occurs.

        :param point_name: Name of the point to retrieve.
        :param value: Value to set the point to.
        :param kwargs: Any interface specific parameters.
        :type point_name: str
        :return: Actual point value set.
        """

    @abc.abstractmethod
    def _scrape_all(self):
        """
        Method the Platform Driver Agent calls to get the current state
        of a device for publication.

        If using this mixin you must override this method
        instead of :py:meth:`BaseInterface.scrape_all`. Otherwise
        the purpose is exactly the same.

        :return: Point names to values for device.
        :rtype: dict
        """

    def revert_all(self, **kwargs):
        """
        Implementation of :py:meth:`BaseInterface.revert_all`

        Calls :py:meth:`BasicRevert._set_point` with `point_name`
        and the value to revert the point to for every writable
        point on a device.

        Currently \*\*kwargs is ignored.
        """
        """Revert entire device to it's default state"""
        points = self._tracker.get_all_revert_values()
        for point_name, value in points.items():
            if not isinstance(value, DriverInterfaceError):
                try:
                    self._set_point(point_name, value)
                    self._tracker.clear_dirty_point(point_name)
                except Exception as e:
                    _log.warning("Error while reverting point {}: {}".format(point_name, str(e)))

    def revert_point(self, point_name, **kwargs):
        """
        Implementation of :py:meth:`BaseInterface.revert_point`

        Revert point to its default state.

        Calls :py:meth:`BasicRevert._set_point` with `point_name`
        and the value to revert the point to.

        :param point_name: Name of the point to revert.
        :type point_name: str

        Currently \*\*kwargs is ignored.
        """
        try:
            value = self._tracker.get_revert_value(point_name)
        except DriverInterfaceError:
            return

        _log.debug("Reverting {} to {}".format(point_name, value))

        self._set_point(point_name, value)
        self._tracker.clear_dirty_point(point_name)
