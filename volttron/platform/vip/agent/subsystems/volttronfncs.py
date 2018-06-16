# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, Battelle Memorial Institute.
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


from __future__ import absolute_import

import logging
import weakref

from .base import SubsystemBase
from volttron.platform.agent import json
from ..errors import VIPError
from ..results import ResultsDictionary
from zmq import ZMQError
from zmq.green import ENOTSOCK

import gevent

__all__ = ['FNCS']


_log = logging.getLogger(__name__)


try:
    from fncs import fncs
    HAS_FNCS = True
except ImportError:
    HAS_FNCS = False


# noinspection PyMethodMayBeStatic
class FNCS(SubsystemBase):
    """ The fncs subsystem allows an integration point between VOLTTRON and FNCS.

    """

    def __init__(self, owner, core, rpc):
        self.core = weakref.ref(core)
        self._greenlets = []
        self._federate_name = self.core().identity
        self._broker = "tcp://localhost:5570"
        self._time_delta = "1s"
        self._poll_timeout = 60
        self._registered_fncs_topics = {}
        self._registered_fncs_topic_callbacks = {}
        self._current_timestep = 0

        def onsetup(sender, **kwargs):
            rpc.export(self.is_fncs_installed, 'fncs.fncs_installed')
            rpc.export(self.fncs_version, "fncs.fncs_version")
            rpc.export(self.initialize, "fncs.initialize")
            rpc.export(self.next_timestep, "fncs.next_timestep")
            rpc.export(self.publish, "fncs.publish")
            rpc.export(self.publish_anon, "fncs.publish_anon")
            rpc.export(self.get_current_timestep, "fncs.get_current_timestep")
            rpc.export(self.reset, "fncs.reset")
            # rpc.export(self.get_status, 'health.get_status')
            # rpc.export(self.send_alert, 'health.send_alert')
        core.onsetup.connect(onsetup, self)
        #self._results = ResultsDictionary()
        #core.register('hello', self._handle_hello, self._handle_error)

    def is_fncs_installed(self):
        """ Allows caller to determine if the fncs module is available.
        """
        return HAS_FNCS

    def __raise_if_not_installed(self):
        if not self.is_fncs_installed():
            raise RuntimeError("Missing fncs python library.")

    def fncs_version(self):
        self.__raise_if_not_installed()
        return fncs.get_version()

    def initialize(self, topic_maping, federate_name=None, broker_location="tcp://localhost:5570",
                   time_delta="1s", poll_timeout=60):
        """ Configure the agent to act as a federated connection to FNCS

        federate_name - MUST be unique to the broker.  If None, then will be the
                        identity of the current agent process.

        broker - tcp location of the fncs broker

        time_delta - Minimum timestep supported for the federate.

        :param federate_name:
        :param broker_location:
        :param kwargs:
        :return:
        """
        self.__raise_if_not_installed()

        if fncs.is_initialized():
            raise RuntimeError("Invalid state, fncs has alreayd been initialized")

        if not topic_maping:
            raise ValueError("Must supply a topic mapping with topics to map onto.")

        if federate_name:
            self._federate_name = federate_name
        if broker_location:
            self._broker = broker_location
        if time_delta:
            self._time_delta = time_delta

        for k, v in topic_maping.items():
            if not v.get('fncs_topic'):
                raise ValueError("Invalid fncs_topic specified in key {}.".format(k))

            entry = dict(fncs_topic=v.get('fncs_topic'))
            if 'volttron_topic' in v.keys():
                entry['volttron_topic'] = v['volttron_topic']

            self._registered_fncs_topics[k] = entry

        self.__register_federate()

    def __register_federate(self):
        self.__raise_if_not_installed()
        cfg = """name = {0[name]}
time_delta = {0[time_delta]}
broker = {0[broker]}
""".format(dict(name=self._federate_name, broker=self._broker, time_delta=self._time_delta))

        if self._registered_fncs_topics:
            cfg += "values"
            for k, v in self._registered_fncs_topics.items():
                cfg += "\n\t{}\n\t\ttopic = {}\n".format(k, v['fncs_topic'])
                if v.get("default"):
                    cfg += "\t\tdefault = {}\n".format(v.get('default'))
                if v.get("data_type"):
                    cfg += "\t\ttype = {}\n".format(v.get('data_type'))
                if v.get("list"):
                    cfg += "\t\tlist = true\n"
        _log.debug(cfg)
        cfg = cfg.replace("\t", "    ")
        fncs.initialize(cfg)
        _log.debug(fncs.is_initialized())
        gevent.spawn(self._fncs_loop)
        gevent.sleep(0.0001)
        if not fncs.is_initialized():
            raise RuntimeError("Intialization error for fncs.")

    # def register_topic_map(self, topic_map):
    #     """ Registers a topic map with fncs
    #
    #     :param topic_map:
    #     :return:
    #     """
    #     if fncs.is_initialized:
    #         raise RuntimeError("Invalid state, fncs has alreayd been initialized")
    #
    #     for k, v in topic_map.items():
    #         if not v.get('fncs_topic'):
    #             raise ValueError("Invalid fncs_topic specified.")
    #
    #         entry = dict(topic=v.get('fncs_topic'))
    #         if 'volttron_topic' in v.keys():
    #             entry['volttron_topic'] = v['volttron_topic']
    #
    #         self._registered_fncs_topics[k] = entry



    # def register_topic(self, key, fncs_topic, volttron_topic, default=None, data_type=None):
    #     """ register a fncs topic to called when a message comes in.
    #
    #     :param topic:
    #     :param callback:
    #     :param aslist:
    #     :param default:
    #     :param data_type:
    #     :return:
    #     """
    #     self._registered_fncs_topics[key] = dict(topic=topic,
    #                                              is_list=str(aslist).lower(),
    #                                              default=default,
    #                                              type=data_type)
    #     self._registered_fncs_topic_callbacks[key] = callback
    #     _log.debug("registered fncs key: {} topic: {}".format(key, topic))

    def get_current_timestep(self):
        self.__raise_if_not_installed()
        return self._current_timestep

    def next_timestep(self):
        self.__raise_if_not_installed()
        # TODO: Change from using 5 to using time_delta.
        granted_time = fncs.time_request(self._current_timestep + 5)
        self._current_timestep = granted_time
        _log.debug("Granted time is: {}".format(granted_time))

    def publish(self, topic, message):
        self.__raise_if_not_installed()
        payload = dict(topic=topic, message=message)
        fncs.publish(topic, message) #.agentPublish(json.dumps(payload))

    def publish_anon(self, topic, message):
        self.__raise_if_not_installed()
        payload = dict(topic=topic, message=message)
        fncs.publish_anon(topic, message)

    def reset(self):
        self.__raise_if_not_installed()
        fncs.die()

    def _fncs_loop(self):
        _log.info("Starting fncs loop")
        while fncs.is_initialized():
            subKeys = fncs.get_events()

            if subKeys:
                _log.debug("Subkeys are: %s", subKeys)
            else:
                if fncs.get_value("a"):
                    _log.debug(fncs.get_value("a"))

            # This allows other event loops to run
            gevent.sleep(0.000000001)



