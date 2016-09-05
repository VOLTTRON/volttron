# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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

# }}}


import logging
import glob
import os
import os.path
import errno
from string import whitespace
from csv import DictReader
from StringIO import StringIO

from zmq.utils import jsonapi
from gevent.lock import Semaphore

from volttron.utils.persistance import PersistentDict
from volttron.platform.agent.utils import parse_json_config
from volttron.platform.vip.agent import errors
from volttron.platform.jsonrpc import RemoteError, MethodNotFound

from .vip.agent import Agent, Core, RPC


_log = logging.getLogger(__name__)

store_ext = ".store"
link_prefix = "config://"

def strip_config_name(config_name):
    return config_name.strip(whitespace + r'\/')

def _list_unique_links(config):
    """Returns a set of config files referenced in this configuration"""
    results = set()
    if isinstance(config, dict):
        values = config.values()
    elif isinstance(config, list):
        values = config
    else:
        #Raw config has no links
        return results


    for value in values:
        if isinstance(value, (dict,list)):
            results.update(_list_unique_links(value))
        elif isinstance(value, str):
            if value.startswith(link_prefix):
                config_name = value.replace(link_prefix, '', 1)
                config_name = strip_config_name(config_name)
                results.add(config_name)

    return results


def check_for_recursion(new_config_name, new_config, existing_configs):
    return _follow_links(set(), new_config_name, new_config_name, new_config, existing_configs)

def _follow_links(seen, new_config_name, current_config_name, current_config, existing_configs):
    children = _list_unique_links(current_config)

    if new_config_name in children:
        return True

    seen.add(current_config_name)

    for child_config_name in children - seen:
        child_config = existing_configs.get(child_config_name)
        if child_config is None:
            #Link to a non-existing config, skip in the future.
            seen.add(child_config_name)
            continue
        if _follow_links(seen, new_config_name, child_config_name, child_config, existing_configs):
            return True

    return False


def process_store(identity, store):
    """Parses raw store data and returns contents.
    Called at startup to initialize the parsed version of the store."""
    results = {}
    sync_store = False
    for config_name, config_data in store.items():
        config_type = config_data["type"]
        config_string = config_data["data"]
        try:
            processed_config = process_raw_config(config_string, config_type)
            if check_for_recursion(config_name, processed_config, results):
                raise ValueError("Recursive configuration references")
            results[config_name] = processed_config
        except ValueError as e:
            _log.error("Error processing Agent {} config {}: {}".format(identity, config_name, str(e)))
            sync_store = True
            del store[config_name]

    if sync_store:
        _log.warning("Removing invalid configurations for Agent {}".format(identity))
        store.sync()

    return results

def process_raw_config(config_string, config_type="raw"):
    """Parses raw config string into python objects"""
    if config_type == "raw":
        return config_string
    elif config_type == "json":
        config = parse_json_config(config_string)
        if not isinstance(config, (list, dict)):
            raise ValueError("Configuration must be a list or object.")
        return config
    elif config_type == "csv":
        f = StringIO(config_string)
        return [x for x in DictReader(f)]

    raise ValueError("Unsupported configuration type.")


class ConfigStoreService(Agent):
    def __init__(self, *args, **kwargs):
        super(ConfigStoreService, self).__init__(*args, **kwargs)

        # This agent is started before the router so we need
        # to keep it from blocking.
        self.core.delay_running_event_set = False

        self.store = {}
        self.store_path = os.path.join(os.environ['VOLTTRON_HOME'], 'configuration_store')

    @Core.receiver('onsetup')
    def _setup(self, sender, **kwargs):
        _log.info("Initializing configuration store")
        try:
            os.makedirs(self.store_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                _log.critical("Failed to create configuration store directory: " + str(e))
                raise
            else:
                _log.debug("Configuration directory already exists.")

        config_store_iter = glob.iglob(os.path.join(self.store_path, "*" + store_ext))

        for store_path in config_store_iter:
            root, ext = os.path.splitext(store_path)
            agent_identity = os.path.basename(root)
            _log.info("Processing store for agent {}".format(agent_identity))
            store = PersistentDict(filename=store_path, flag='c', format='json')
            parsed_configs = process_store(agent_identity, store)
            self.store[agent_identity] = {"configs": parsed_configs, "store": store, "lock": Semaphore()}




    @RPC.export
    def manage_store(self, identity, config_name, raw_contents, config_type="raw"):
        contents = process_raw_config(raw_contents, config_type)
        self._add_config_to_store(identity, config_name, raw_contents, contents, config_type,
                                  trigger_callback=True)

    @RPC.export
    def manage_delete_config(self, identity, config_name):
        self.delete(identity, config_name, trigger_callback=True)

    @RPC.export
    def manage_delete_store(self, identity):
        agent_store = self.store.get(identity)
        if agent_store is None:
            return

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]

        agent_configs.clear()
        agent_disk_store.clear()

        # Sync will delete the file if the store is empty.
        agent_disk_store.async_sync()

        with agent_store_lock:
            try:
                self.vip.rpc.call(identity, "update_config", None, "DELETE_ALL", trigger_callback=True).get(
                    timeout=10.0)
            except errors.Unreachable:
                _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
            except RemoteError as e:
                _log.error("Agent {} failure when all configurations: {}".format(identity, e))
            except MethodNotFound as e:
                _log.error(
                    "Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))

        # If the store is still empty (nothing jumped in and added to it while we were informing the agent)
        # then remove it from the global store.
        if not agent_disk_store:
            self.store.pop(identity)

    @RPC.export
    def manage_list_configs(self, identity):
        return self.store.get(identity, {}).get("store", {}).keys()

    @RPC.export
    def manage_list_stores(self):
        return self.store.keys()

    @RPC.export
    def manage_get(self, identity, config_name, raw=True):
        agent_store = self.store.get(identity)
        if agent_store is None:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]

        if config_name not in agent_disk_store:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        if raw:
            return agent_disk_store[config_name]["data"]

        return agent_configs[config_name]

    @RPC.export
    def set_config(self, config_name, contents, trigger_callback=False):
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        self.store_config(identity, config_name, contents, trigger_callback=trigger_callback)


    @RPC.export
    def get_configs(self):
        """Called by an Agent at startup to get the initial configuration state."""
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        return self.store.get(identity, {}).get("configs", {})

    @RPC.export
    def delete_config(self, config_name, trigger_callback=False):
        """Called by an Agent to delete a configuration."""
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        self.delete(identity, config_name, trigger_callback=trigger_callback)

    #Helper method to allow the local services to delete configs before message bus in online.
    def delete(self, identity, config_name, trigger_callback=False):
        agent_store = self.store.get(identity)
        if agent_store is None:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]

        if config_name not in agent_disk_store:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        agent_configs.pop(config_name)
        agent_disk_store.pop(config_name)

        #Sync will delete the file if the store is empty.
        agent_disk_store.async_sync()

        with agent_store_lock:
            try:
                self.vip.rpc.call(identity, "update_config", config_name, "DELETE", trigger_callback=trigger_callback).get(timeout=10.0)
            except errors.Unreachable:
                _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
            except RemoteError as e:
                _log.error("Agent {} failure when deleting configuration {}: {}".format(identity, config_name, e))
            except MethodNotFound as e:
                _log.error(
                    "Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))

        #If the store is empty (and nothing jumped in and added to it while we were informing the agent)
        # then remove it from the global store.
        if not agent_disk_store:
            self.store.pop(identity)

    # Helper method to allow the local services to store configs before message bus is online.
    def store_config(self, identity, config_name, contents, trigger_callback=False):
        config_type = None
        raw_data = None
        if isinstance(contents, (dict, list)):
            config_type = 'json'
            raw_data = jsonapi.dumps(contents)
        elif isinstance(contents, str):
            config_type = 'raw'
            raw_data = contents
        else:
            raise ValueError("Unsupported configuration content type: {}".format(str(type(contents))))

        self._add_config_to_store(identity, config_name, raw_data,contents, config_type, trigger_callback=trigger_callback)

    def _add_config_to_store(self, identity, config_name, raw, parsed, config_type, trigger_callback=False):
        """Adds a processed configuration to the store."""
        agent_store = self.store.get(identity)

        action = "UPDATE"

        if agent_store is None:
            #Initialize a new store.
            store_path = os.path.join(self.store_path, identity+ store_ext)
            store = PersistentDict(filename=store_path, flag='c', format='json')
            agent_store = {"configs": {}, "store": store, "lock": Semaphore()}
            self.store[identity] = agent_store

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]

        config_name = strip_config_name(config_name)

        if config_name not in agent_configs:
            action = "NEW"

        if check_for_recursion(config_name, parsed, agent_configs):
            raise ValueError("Recursive configuration references detected.")

        agent_configs[config_name] = parsed
        agent_disk_store[config_name] = {"type": config_type, "data": raw}

        agent_disk_store.async_sync()

        _log.info("Agent {} config {} stored.".format(identity, config_name))

        with agent_store_lock:
            try:
                self.vip.rpc.call(identity, "update_config", action, contents=parsed, trigger_callback=trigger_callback).get(timeout=10.0)
            except errors.Unreachable:
                _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
            except RemoteError as e:
                _log.error("Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))
            except MethodNotFound as e:
                _log.error(
                    "Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))
