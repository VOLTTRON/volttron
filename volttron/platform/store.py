# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
import glob
import os
import os.path
import errno
from csv import DictReader
from io import StringIO

from volttron.platform import jsonapi
from gevent.lock import Semaphore

from volttron.utils.persistance import PersistentDict
from volttron.platform.agent.utils import parse_json_config
from volttron.platform.vip.agent import errors
from volttron.platform.jsonrpc import RemoteError, MethodNotFound
from volttron.platform.agent.utils import parse_timestamp_string, format_timestamp, get_aware_utc_now
from volttron.platform.storeutils import check_for_recursion, strip_config_name, store_ext
from .vip.agent import Agent, Core, RPC


_log = logging.getLogger(__name__)

UPDATE_TIMEOUT = 30.0

def process_store(identity, store):
    """Parses raw store data and returns contents.
    Called at startup to initialize the parsed version of the store."""
    results = {}
    name_map = {}
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

        if config_name.lower() in name_map:
            _log.error("Conflicting names in store, dropping {}".format(config_name))
            sync_store = True
            del store[config_name]

        else:
            name_map[config_name.lower()] = config_name

    if sync_store:
        _log.warning("Removing invalid configurations for Agent {}".format(identity))
        store.sync()

    return results, name_map


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
        _log.info("Initializing configuration store service.")

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
            _log.debug("Processing store for agent {}".format(agent_identity))
            store = PersistentDict(filename=store_path, flag='c', format='json')
            parsed_configs, name_map = process_store(agent_identity, store)
            self.store[agent_identity] = {"configs": parsed_configs,
                                          "store": store,
                                          "name_map": name_map,
                                          "lock": Semaphore()}

    @RPC.export
    @RPC.allow('edit_config_store')
    def manage_store(self, identity, config_name, raw_contents, config_type="raw"):
        contents = process_raw_config(raw_contents, config_type)
        self._add_config_to_store(identity, config_name, raw_contents, contents, config_type,
                                  trigger_callback=True)

    @RPC.export
    @RPC.allow('edit_config_store')
    def manage_delete_config(self, identity, config_name):
        self.delete(identity, config_name, trigger_callback=True)

    @RPC.export
    @RPC.allow('edit_config_store')
    def manage_delete_store(self, identity):
        agent_store = self.store.get(identity)
        if agent_store is None:
            return

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]
        agent_name_map = agent_store["name_map"]

        agent_configs.clear()
        agent_disk_store.clear()
        agent_name_map.clear()

        # Sync will delete the file if the store is empty.
        agent_disk_store.async_sync()

        with agent_store_lock:
            try:
                self.vip.rpc.call(identity, "config.update",
                                  "DELETE_ALL", None,
                                  trigger_callback=True).get(timeout=UPDATE_TIMEOUT)
            except errors.Unreachable:
                _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
            except RemoteError as e:
                _log.error("Agent {} failure when all configurations: {}".format(identity, e))
            except MethodNotFound as e:
                _log.error(
                    "Agent {} failure when deleting configuration store: {}".format(identity, e))

        # If the store is still empty (nothing jumped in and added to it while
        # we were informing the agent) then remove it from the global store.
        if not agent_disk_store:
            self.store.pop(identity, None)

    @RPC.export
    def manage_list_configs(self, identity):
        result = list(self.store.get(identity, {}).get("store", {}).keys())
        result.sort()
        return result

    @RPC.export
    def manage_list_stores(self):
        result = list(self.store.keys())
        result.sort()
        return result

    @RPC.export
    def manage_get(self, identity, config_name, raw=True):
        agent_store = self.store.get(identity)
        if agent_store is None:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_name_map = agent_store["name_map"]

        config_name = strip_config_name(config_name)
        config_name_lower = config_name.lower()

        if config_name_lower not in agent_name_map:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        real_config_name = agent_name_map[config_name_lower]

        if raw:
            return agent_disk_store[real_config_name]["data"]

        return agent_configs[real_config_name]

    @RPC.export
    def manage_get_metadata(self, identity, config_name):
        agent_store = self.store.get(identity)
        if agent_store is None:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        agent_disk_store = agent_store["store"]
        agent_name_map = agent_store["name_map"]

        config_name = strip_config_name(config_name)
        config_name_lower = config_name.lower()

        if config_name_lower not in agent_name_map:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        real_config_name = agent_name_map[config_name_lower]

        real_config =  agent_disk_store[real_config_name]

        #Set modified to none if we predate the modified flag.
        if real_config.get("modified") is None:
            real_config["modified"] = None

        return real_config

    @RPC.export
    def set_config(self, config_name, contents, trigger_callback=False, send_update=True):
        identity = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        self.store_config(identity, config_name, contents, trigger_callback=trigger_callback, send_update=send_update)


    @RPC.export
    def get_configs(self):
        """
        Called by an Agent at startup to trigger initial configuration state
        push.
        """
        identity = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")

        #We need to create store and lock if it doesn't exist in case someone
        # tries to add a configuration while we are sending the initial state.
        agent_store = self.store.get(identity)

        if agent_store is None:
            # Initialize a new store.
            store_path = os.path.join(self.store_path, identity + store_ext)
            store = PersistentDict(filename=store_path, flag='c', format='json')
            agent_store = {
                "configs": {}, "store": store, "name_map": {},
                "lock": Semaphore()
            }
            self.store[identity] = agent_store

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]

        with agent_store_lock:
            try:
                self.vip.rpc.call(identity, "config.initial_update",
                                  agent_configs).get(timeout=UPDATE_TIMEOUT)
            except errors.Unreachable:
                _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
            except RemoteError as e:
                _log.error("Agent {} failure when performing initial update: {}".format(identity, e))
            except MethodNotFound as e:
                _log.error(
                    "Agent {} failure when performing initial update: {}".format(identity, e))
            except errors.VIPError as e:
                _log.error("VIP Error sending initial agent configuration: {}".format(e))

        # If the store is empty (and nothing jumped in and added to it while we
        # were informing the agent) then remove it from the global store.
        if not agent_disk_store:
            self.store.pop(identity, None)

    @RPC.export
    def delete_config(self, config_name, trigger_callback=False, send_update=True):
        """Called by an Agent to delete a configuration."""
        identity = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        self.delete(identity, config_name, trigger_callback=trigger_callback,
                    send_update=send_update)

    # Helper method to allow the local services to delete configs before message
    # bus in online.
    def delete(self, identity, config_name, trigger_callback=False, send_update=True):
        agent_store = self.store.get(identity)
        if agent_store is None:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]
        agent_name_map = agent_store["name_map"]

        config_name = strip_config_name(config_name)
        config_name_lower = config_name.lower()

        if config_name_lower not in agent_name_map:
            raise KeyError('No configuration file "{}" for VIP IDENTIY {}'.format(config_name, identity))

        real_config_name = agent_name_map[config_name_lower]

        agent_configs.pop(real_config_name)
        agent_disk_store.pop(real_config_name)
        agent_name_map.pop(config_name_lower)

        # Sync will delete the file if the store is empty.
        agent_disk_store.async_sync()

        if send_update:
            with agent_store_lock:
                try:
                    self.vip.rpc.call(identity, "config.update", "DELETE", config_name, trigger_callback=trigger_callback).get(timeout=UPDATE_TIMEOUT)
                except errors.Unreachable:
                    _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
                except RemoteError as e:
                    _log.error("Agent {} failure when deleting configuration {}: {}".format(identity, config_name, e))
                except MethodNotFound as e:
                    _log.error(
                        "Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))

        # If the store is empty (and nothing jumped in and added to it while we
        # were informing the agent) then remove it from the global store.
        if not agent_disk_store:
            self.store.pop(identity, None)

    # Helper method to allow the local services to store configs before message
    # bus is online.
    def store_config(self, identity, config_name, contents,
                     trigger_callback=False, send_update=True):
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

        self._add_config_to_store(identity, config_name, raw_data,contents,
                                  config_type,
                                  trigger_callback=trigger_callback,
                                  send_update=send_update)

    def _add_config_to_store(self, identity, config_name, raw, parsed,
                             config_type, trigger_callback=False,
                             send_update=True):
        """Adds a processed configuration to the store."""
        agent_store = self.store.get(identity)

        action = "UPDATE"

        if agent_store is None:
            #Initialize a new store.
            store_path = os.path.join(self.store_path, identity+ store_ext)
            store = PersistentDict(filename=store_path, flag='c', format='json')
            agent_store = {"configs": {}, "store": store, "name_map": {}, "lock": Semaphore()}
            self.store[identity] = agent_store

        agent_configs = agent_store["configs"]
        agent_disk_store = agent_store["store"]
        agent_store_lock = agent_store["lock"]
        agent_name_map = agent_store["name_map"]

        config_name = strip_config_name(config_name)
        config_name_lower = config_name.lower()

        if config_name_lower not in agent_name_map:
            action = "NEW"

        if check_for_recursion(config_name, parsed, agent_configs):
            raise ValueError("Recursive configuration references detected.")

        if config_name_lower in agent_name_map:
            old_config_name = agent_name_map[config_name_lower]
            del agent_configs[old_config_name]

        agent_configs[config_name] = parsed
        agent_name_map[config_name_lower] = config_name

        agent_disk_store[config_name] = {"type": config_type,
                                         "modified": format_timestamp(get_aware_utc_now()),
                                         "data": raw}

        agent_disk_store.async_sync()

        _log.debug("Agent {} config {} stored.".format(identity, config_name))

        if send_update:
            with agent_store_lock:
                try:
                    self.vip.rpc.call(identity, "config.update", action, config_name, contents=parsed, trigger_callback=trigger_callback).get(timeout=UPDATE_TIMEOUT)
                except errors.Unreachable:
                    _log.debug("Agent {} not currently running. Configuration update not sent.".format(identity))
                except RemoteError as e:
                    _log.error("Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))
                except MethodNotFound as e:
                    _log.error(
                        "Agent {} failure when adding/updating configuration {}: {}".format(identity, config_name, e))
