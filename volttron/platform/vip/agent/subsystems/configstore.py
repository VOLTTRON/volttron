# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
import logging
import traceback
import os
import weakref
import fnmatch
import greenlet
import inspect

from .base import SubsystemBase
from volttron.platform.storeutils import list_unique_links, check_for_config_link
from volttron.platform.vip.agent import errors
from volttron.platform.agent.known_identities import CONFIGURATION_STORE

from collections import defaultdict
from copy import deepcopy

"""The configstore subsystem manages the agent side of the configuration store.
It is responsible for processing change notifications from the platform
 and triggering the correct callbacks with the contents of a configuration.
"""

__docformat__ = 'reStructuredText'
__version__ = '1.0'

_log = logging.getLogger(__name__)

VALID_ACTIONS = set(["NEW", "UPDATE", "DELETE"])

class ConfigStore(SubsystemBase):
    def __init__(self, owner, core, rpc):
        self._core = weakref.ref(core)
        self._rpc = weakref.ref(rpc)

        self._ref_map = {} #For triggering callbacks.
        self._reverse_ref_map = defaultdict(set)  # For triggering callbacks.
        self._store = {}
        self._default_store = {}
        self._callbacks = {}
        self._name_map = {}
        self._default_name_map = {}

        self._initialized = False
        self._initial_callbacks_called = False

        self._process_callbacks_code_object = self._process_callbacks.__code__

        def sub_factory():
            return defaultdict(set)

        self._subscriptions = defaultdict(sub_factory)

        def onsetup(sender, **kwargs):
            rpc.export(self._update_config, 'config.update')
            rpc.export(self._initial_update, 'config.initial_update')

        core.onsetup.connect(onsetup, self)
        core.configuration.connect(self._onconfig, self)

    def _onconfig(self, sender, **kwargs):
        if not self._initialized:
            try:
                self._rpc().call(CONFIGURATION_STORE, "get_configs").get()
            except errors.Unreachable as e:
                _log.error("Connected platform does not support the Configuration Store feature.")
                return
            except errors.VIPError as e:
                _log.error("Error retrieving agent configurations: {}".format(e))
                return


        affected_configs = {}
        for config_name in self._store:
            affected_configs[config_name] = "NEW"
        for config_name in self._default_store:
            affected_configs[config_name] = "NEW"

        self._process_callbacks(affected_configs)
        self._initial_callbacks_called = True

    def _add_refs(self, config_name, contents):
        refs = list_unique_links(contents)
        self._ref_map[config_name] = refs

        for ref in refs:
            self._reverse_ref_map[ref].add(config_name)

    def _update_refs(self, config_name, contents):
        self._delete_refs(config_name)

        self._add_refs(config_name, contents)


    def _delete_refs(self, config_name):
        #Delete refs if they exist.
        old_refs = self._ref_map.pop(config_name, set())

        for ref in old_refs:
            reverse_ref_set = self._reverse_ref_map[ref]
            reverse_ref_set.remove(config_name)
            if not reverse_ref_set:
                del self._reverse_ref_map[ref]


    def _initial_update(self, configs, reset_name_map=True):
        self._initialized = True
        self._store = {key.lower(): value for (key, value) in configs.items()}
        if reset_name_map:
            self._name_map = {key.lower(): key for key in configs}

        for config_name, config_contents in self._store.items():
            self._add_refs(config_name, config_contents)

        for config_name, config_contents in self._default_store.items():
            if config_name not in self._store:
                self._add_refs(config_name, config_contents)


    def _process_links(self, config_contents, already_gathered):
        if isinstance(config_contents, dict):
            for key, value in config_contents.items():
                if isinstance(value, (dict, list)):
                    self._process_links(value, already_gathered)
                elif isinstance(value, str):
                    config_name = check_for_config_link(value)
                    if config_name is not None:
                        config_contents[key] = self._gather_child_configs(config_name, already_gathered)
        elif isinstance(config_contents, list):
            for i, value in enumerate(config_contents):
                if isinstance(value, (dict, list)):
                    self._process_links(value, already_gathered)
                elif isinstance(value, str):
                    config_name = check_for_config_link(value)
                    if config_name is not None:
                        config_contents[i] = self._gather_child_configs(config_name, already_gathered)

    def _gather_child_configs(self, config_name, already_gathered):
        if config_name in already_gathered:
            return already_gathered[config_name]

        config_contents = self._store.get(config_name)
        if config_contents is None:
            config_contents = self._default_store.get(config_name)

        config_contents = deepcopy(config_contents)
        already_gathered[config_name] = config_contents

        self._process_links(config_contents, already_gathered)

        return config_contents


    def _gather_config(self, config_name):
        config_contents = self._store.get(config_name)
        if config_contents is None:
            config_contents = self._default_store.get(config_name)

        if config_contents is None:
            raise KeyError("{} not in store".format(config_name))

        already_configured = {}

        return self._gather_child_configs(config_name, already_configured)



    def _gather_affected(self, config_name, seen_dict):
        reverse_refs = self._reverse_ref_map[config_name]
        for ref in reverse_refs:
            if ref not in seen_dict:
                seen_dict[ref] = "UPDATE"
                self._gather_affected(ref, seen_dict)


    def _update_config(self, action, config_name, contents=None, trigger_callback=False):
        """Called by the platform to push out configuration changes."""
        #If we haven't yet grabbed the initial callback state we just bail.
        if not self._initialized:
            return

        affected_configs = {}

        #Update local store.
        if action == "DELETE":
            config_name_lower = config_name.lower()
            if config_name_lower in self._store:
                del self._store[config_name_lower]

                if config_name_lower not in self._default_store:
                    affected_configs[config_name_lower] = "DELETE"
                    self._gather_affected(config_name_lower, affected_configs)
                    self._delete_refs(config_name_lower)
                else:
                    affected_configs[config_name_lower] = "UPDATE"
                    self._gather_affected(config_name_lower, affected_configs)
                    self._update_refs(config_name_lower, self._default_store[config_name_lower])

        if action == "DELETE_ALL":
            for name in self._store:
                affected_configs[name] = "DELETE"
            #Just assume all default stores updated.
            for name in self._default_store:
                affected_configs[name] = "UPDATE"
            self._ref_map = {}
            self._reverse_ref_map = defaultdict(set)
            self._initial_update({}, False)

        if action in ("NEW", "UPDATE"):
            config_name_lower = config_name.lower()
            self._store[config_name_lower] = contents
            self._name_map[config_name_lower] = config_name
            if config_name_lower in self._default_store:
                action = "UPDATE"
            affected_configs[config_name_lower] = action
            self._update_refs(config_name_lower, self._store[config_name_lower])
            self._gather_affected(config_name_lower, affected_configs)


        if trigger_callback and self._initial_callbacks_called:
            self._process_callbacks(affected_configs)

        if action == "DELETE":
            del self._name_map[config_name_lower]

        if action == "DELETE_ALL":
            self._name_map.clear()



    def _process_callbacks(self, affected_configs):
        _log.debug("Processing callbacks for affected files: {}".format(affected_configs))
        all_map = self._default_name_map.copy()
        all_map.update(self._name_map)
        #Always process "config" first.
        if "config" in affected_configs:
            self._process_callbacks_one_config("config", affected_configs["config"], all_map)

        for config_name, action in affected_configs.items():
            if config_name == "config":
                continue
            self._process_callbacks_one_config(config_name, action, all_map)


    def _process_callbacks_one_config(self, config_name, action, name_map):
        callbacks = set()
        for pattern, actions in self._subscriptions.items():
            if fnmatch.fnmatchcase(config_name, pattern) and action in actions:
                callbacks.update(actions[action])

        for callback in callbacks:
            try:
                if action == "DELETE":
                    contents = None
                else:
                    contents = self._gather_config(config_name)
                callback(name_map[config_name], action, contents)
            except Exception:
                tb_str = traceback.format_exc()
                _log.error("Problem processing callback:")
                _log.error(tb_str)

    def list(self):
        """Returns a list of configuration names for this agent.

        :returns: Configuration names
        :rtype: list

        :Return Values:
        A list of all the configuration names available for this agent.
        """
        # Handle case were we are called during "onstart".
        if not self._initialized:
            try:
                self._rpc().call(CONFIGURATION_STORE, "get_configs").get()
            except errors.Unreachable as e:
                _log.error("Connected platform does not support the Configuration Store feature.")
            except errors.VIPError as e:
                _log.error("Error retrieving agent configurations: {}".format(e))

        all_map = self._default_name_map.copy()
        all_map.update(self._name_map)

        store_set = set(self._store.keys())
        default_set = set(self._default_store.keys())
        config_list =  list(all_map[x] for x in (store_set|default_set))
        config_list.sort()
        return config_list

    def get(self, config_name="config"):
        """Returns the contents of a configuration.

        :param config_name: Name of configuration to add to store.
        :type config_name: str
        :returns: Configuration contents
        :rtype: dict, list, or string

        :Return Values:
        The contents of the configuration specified.
        """
        #Handle case were we are called during "onstart".

        #If we fail to initialize we don't raise an exception as there still
        #may be a default configuration to grab.
        if not self._initialized:
            try:
                self._rpc().call(CONFIGURATION_STORE, "get_configs").get()
            except errors.Unreachable as e:
                _log.error("Connected platform does not support the Configuration Store feature.")
            except errors.VIPError as e:
                _log.error("Error retrieving agent configurations: {}".format(e))

        config_name = config_name.lower()

        return self._gather_config(config_name)

    def _check_call_from_process_callbacks(self):
        frame_records = inspect.stack()
        try:
            #Don't create any unneeded references to frame objects.
            for frame, *_ in frame_records:
                if self._process_callbacks_code_object is frame.f_code:
                    raise RuntimeError("Cannot request changes to the config store from a configuration callback.")
        finally:
            del frame_records


    def set(self, config_name, contents, trigger_callback=False, send_update=True):
        """Called to set the contents of a configuration.

        May not be called before the onstart phase of an agents lifetime.

        May not be called from a configuration callback. Will produce a runtime error if done so.

        :param config_name: Name of configuration to add to store.
        :param contents: Contents of the configuration. May be a string, dictionary, or list.
        :param trigger_callback: Tell the platform to trigger callbacks on the agent for this change.

        :type config_name: str
        :type contents: str, dict, list
        :type trigger_callback: bool
        """
        self._check_call_from_process_callbacks()

        self._rpc().call(CONFIGURATION_STORE, "set_config", config_name, contents,
                         trigger_callback=trigger_callback,
                         send_update=send_update).get(timeout=10.0)

    def set_default(self, config_name, contents):
        """Called to set the contents of a default configuration file. Default configurations are used if the
        configuration store does not contain a configuration with that name.

        May not be called after the onsetup phase of an agents lifetime. Will produce a runtime error if done so.

        :param config_name: Name of configuration to add to store.
        :param contents: Contents of the configuration. May be a string, dictionary, or list.
        :type config_name: str
        :type contents: str, dict, list
        """
        if self._initialized:
            raise RuntimeError("Cannot request changes to default configurations after onsetup.")

        if not isinstance(contents, (str, list, dict)):
            raise ValueError("Invalid content type: {}".format(contents.__class__.__name__))

        config_name_lower = config_name.lower()
        self._default_store[config_name_lower] = contents
        self._default_name_map[config_name_lower] = config_name

        if config_name_lower in self._store:
            return

        self._update_refs(config_name_lower, self._default_store[config_name_lower])

    def delete_default(self, config_name):
        """Called to delete the contents of a default configuration file.

            May not be called after the onsetup phase of an agents lifetime. Will produce a runtime error if done so.

            :param config_name: Configuration to remove from store.
            :type config_name: str
            """
        if self._initialized:
            raise RuntimeError("Cannot request changes to default configurations after onsetup.")

        config_name_lower = config_name.lower()
        del self._default_store[config_name_lower]
        del self._default_name_map[config_name_lower]

        if config_name_lower in self._store:
            return

        self._update_refs(config_name_lower, self._store[config_name_lower])


    def delete(self, config_name, trigger_callback=False, send_update=True):
        """Delete a configuration by name. May not be called from a callback as this will cause
            deadlock with the platform. Will produce a runtime error if done so.

        :param config_name: Configuration to remove from store.
        :param trigger_callback: Tell the platform to trigger callbacks on the agent for this change.
        :type config_name: str
        :type trigger_callback: bool
            """
        self._check_call_from_process_callbacks()

        self._rpc().call(CONFIGURATION_STORE, "delete_config", config_name,
                         trigger_callback=trigger_callback,
                         send_update=send_update).get(timeout=10.0)

    def subscribe(self, callback, actions=VALID_ACTIONS, pattern="*"):
        """Subscribe to changes to a configuration.

        :param callback: Function to call in response to changes to a configuration.
        :param actions: Change actions to respond to. Valid values are "NEW", "UPDATE", and "DELETE". May be a single action or a list of actions.
        :param pattern: Configuration name pattern to match to.  Uses Unix style filename pattern matching.

        :type callback: str
        :type actions: str or list
        :type pattern: str
        """
        if isinstance(actions, str):
            actions = (actions,)

        actions = set(action.upper() for action in actions)

        invalid_actions = actions - VALID_ACTIONS
        if (invalid_actions):
            raise ValueError("Invalid actions: " + list(invalid_actions))

        pattern = pattern.lower()

        for action in actions:
            self._subscriptions[pattern][action].add(callback)

    def unsubscribe_all(self):
        """Remove all subscriptions."""
        self._subscriptions.clear()









