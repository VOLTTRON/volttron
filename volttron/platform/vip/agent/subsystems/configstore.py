# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

import logging
import traceback
import os
import weakref
import fnmatch

from .base import SubsystemBase
from volttron.platform.storeutils import list_unique_links, check_for_config_link

from collections import defaultdict
from copy import deepcopy

"""The heartbeat subsystem adds an optional periodic publish to all agents.
Heartbeats can be started with agents and toggled on and off at runtime.
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

        self._processing_callbacks = False
        self._initialized = False
        self._initial_callbacks_called = False

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
            self._rpc().call("config.store", "get_configs").get()

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


    def _initial_update(self, configs):
        self._initialized = True
        self._store = configs

        for config_name, config_contents in self._store.iteritems():
            self._add_refs(config_name, config_contents)

        for config_name, config_contents in self._default_store.iteritems():
            if config_name not in self._store:
                self._add_refs(config_name, config_contents)


    def _process_links(self, config_contents, already_gathered):
        if isinstance(config_contents,dict ):
            for key in config_contents.keys():
                value = config_contents[key]
                if isinstance(value, (dict,list)):
                    self._process_links(value, already_gathered)
                elif isinstance(value, str):
                    config_name = check_for_config_link(value)
                    if config_name is not None:
                        config_contents[key] = self._gather_child_configs(config_name, already_gathered)

        if isinstance(config_contents,list):
            for i in xrange(len(config_contents)):
                value = config_contents[i]
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
            if config_name in self._store:
                del self._store[config_name]
                if config_name not in self._default_store:
                    affected_configs[config_name] = "DELETE"
                    self._gather_affected(config_name, affected_configs)
                    self._delete_refs(config_name)
                else:
                    affected_configs[config_name] = "UPDATE"
                    self._gather_affected(config_name, affected_configs)
                    self._update_refs(config_name, self._default_store[config_name])

        if action == "DELETE_ALL":
            for name in self._store:
                affected_configs[name] = "DELETE"
            #Just assume all default stores updated.
            for name in self._default_store:
                affected_configs[name] = "UPDATE"
            self._ref_map = {}
            self._reverse_ref_map = defaultdict(set)
            self._initial_update({})

        if action in ("NEW", "UPDATE"):
            self._store[config_name] = contents
            if config_name in self._default_store:
                action = "UPDATE"
            affected_configs[config_name] = action
            self._update_refs(config_name, self._store[config_name])
            self._gather_affected(config_name, affected_configs)


        if trigger_callback and self._initial_callbacks_called:
            self._process_callbacks(affected_configs)


    def _process_callbacks(self, affected_configs):
        _log.debug("Processing callbacks for affected files: {}".format(affected_configs))
        self._processing_callbacks = True
        try:
            for config_name, action in affected_configs.iteritems():
                callbacks = set()
                for pattern, actions in self._subscriptions.iteritems():
                    if fnmatch.fnmatchcase(config_name, pattern) and action in actions:
                        callbacks.update(actions[action])

                for callback in callbacks:
                    try:
                        if action == "DELETE":
                            contents = None
                        else:
                            contents = self._gather_config(config_name)
                        callback(config_name, action, contents)
                    except StandardError as e:
                        tb_str = traceback.format_exc()
                        _log.error("Problem processing callback:")
                        _log.error(tb_str)
        finally:
            self._processing_callbacks = False

    def list(self):
        # Handle case were we are called during "onstart".
        if not self._initialized:
            self._rpc().call("config.store", "get_configs").get()

        store_set = set(self._store.keys())
        default_set = set(self._default_store.keys())
        config_list =  list(store_set|default_set)
        config_list.sort()
        return config_list

    def get(self, config_name="config"):
        #Handle case were we are called during "onstart".
        if not self._initialized:
            self._rpc().call("config.store", "get_configs").get()

        config_name = config_name.lower()

        return self._gather_config(config_name)

    def set(self, config_name, contents, trigger_callback=False ):
        if self._processing_callbacks:
            raise RuntimeError("Cannot request changes to the config store from a configuration callback.")

        self._rpc().call("config.store", "set_config", config_name, contents, trigger_callback=trigger_callback)

    def set_default(self, config_name, contents, trigger_callback=False):
        if self._processing_callbacks:
            raise RuntimeError("Cannot request changes to the config store from a configuration callback.")

        if not isinstance(contents, (str, list, dict)):
            raise ValueError("Invalid content type: {}".format(contents.__class__.__name__))

        config_name = config_name.lower()
        action = "UPDATE" if config_name in self._default_store else "NEW"
        self._default_store[config_name] = contents

        if config_name in self._store:
            return

        affected_configs = {config_name: action}
        self._update_refs(config_name, self._default_store[config_name])
        if trigger_callback:
            self._gather_affected(config_name, affected_configs)
            self._process_callbacks(affected_configs)

    def delete_default(self, config_name, trigger_callback=False):
        if self._processing_callbacks:
            raise RuntimeError("Cannot request changes to the config store from a configuration callback.")

        config_name = config_name.lower()
        del self._default_store[config_name]

        if config_name in self._store:
            return

        affected_configs = {config_name: "DELETE"}
        self._gather_affected(config_name, affected_configs)
        self._update_refs(config_name, self._store[config_name])

        if trigger_callback:
            self._process_callbacks(affected_configs)


    def delete(self, config_name, trigger_callback=False):
        if self._processing_callbacks:
            raise RuntimeError("Cannot request changes to the config store from a configuration callback.")

        self._rpc().call("config.store", "delete_config", config_name, trigger_callback=trigger_callback)

    def subscribe(self, callback, actions=VALID_ACTIONS, pattern="*"):
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
        self._subscriptions.clear()









