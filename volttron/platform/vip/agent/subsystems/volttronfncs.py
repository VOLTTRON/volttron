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

from datetime import datetime
import logging
import re
import weakref
import warnings

from .base import SubsystemBase
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

    def __init__(self, owner, core, pubsub):
        self.core = weakref.ref(core)
        self.pubsub = weakref.ref(pubsub)

        self._federate_name = self.core().identity
        self._broker = "tcp://localhost:5570"
        self._time_delta = "1s"
        self._poll_timeout = 60
        self._registered_fncs_topics = {}
        self._registered_fncs_topic_callbacks = {}
        self._current_step = 0
        self._current_simulation_time = None
        self._simulation_start_time = None
        self._simulation_delta = None
        self._simulation_length = None
        self._simulation_complete = False
        self._work_callback = None

    def initialize(self, sim_start_time, sim_length, topic_maping, work_callback, federate_name=None,
                   broker_location="tcp://localhost:5570", time_delta="1s", poll_timeout=60):
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

        if not sim_start_time:
            raise ValueError("sim_start_time must be specified.")

        if not sim_length:
            raise ValueError("sim_length must be specified.")

        if not time_delta:
            raise ValueError("time_delta must be specified.")

        if not federate_name:
            raise ValueError("federate_name must be specified.")

        if not broker_location:
            raise ValueError("broker_location must be specified.")

        if not work_callback:
            raise ValueError("work_callback must be specified.")

        if not isinstance(sim_start_time, datetime):
            raise ValueError("sim_start_time must be a datetime object.")

        self._broker = broker_location
        self._time_delta = time_delta
        self._current_simulation_time = self._simulation_start_time = sim_start_time
        self._simulation_delta = self.parse_time(time_delta)
        self._simulation_length = self.parse_time(sim_length)
        if federate_name:
            self._federate_name = federate_name
        self._work_callback = work_callback

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

    @property
    def current_simulation_step(self):
        self.__raise_if_not_installed()
        return self._current_step

    @property
    def current_simulation_time(self):
        self.__raise_if_not_installed()
        return self._current_simulation_time

    def next_timestep(self):
        self.__raise_if_not_installed()
        # TODO: Change from using 5 to using time_delta.
        granted_time = fncs.time_request(self._current_step + self._simulation_delta)
        self._current_step = granted_time
        # self._current_simulation_time = self._current_simulation_time + self._simulation_delta
        _log.debug("Granted time is: {}".format(granted_time))

    def parse_time(self, time_string):

        parssed_time = re.findall(r'(\d+)(\s?)(\D+)', time_string)
        if len(parssed_time) > 0:
            inTime = int(parssed_time[0][0])
            inUnit = parssed_time[0][2]
            if 's' in inUnit[0] or 'S' in inUnit[0]:
                timeMultiplier = 1
            elif 'm' in inUnit[0] or 'M' in inUnit[0]:
                timeMultiplier = 60
            elif 'h' in inUnit[0] or 'H' in inUnit[0]:
                timeMultiplier = 3600
            elif 'd' in inUnit[0] or 'D' in inUnit[0]:
                timeMultiplier = 86400
            else:
                warnings.warn("Unknown time unit supplied. Defaulting to seconds.")
                timeMultiplier = 1
        else:
            raise RuntimeError(
                "Unable to parse run time argument. Please provide run time in the following format: #s, #m, #h, #d, or #y.")
        return inTime * timeMultiplier

    def publish(self, topic, message):
        self.__raise_if_not_installed()
        payload = dict(topic=topic, message=message)
        new_topic = '/'.join([self._federate_name, topic])
        _log.debug("Publishing to: {}".format(new_topic))
        fncs.publish("a", str(message))

    def publish_anon(self, topic, message):
        self.__raise_if_not_installed()
        payload = dict(topic=topic, message=message)
        fncs.publish_anon(topic, message)

    def reset(self):
        self.__raise_if_not_installed()
        fncs.die()

    def _fncs_loop(self):
        _log.info("Starting fncs loop")
        while self._current_step < self._simulation_length:
            subKeys = fncs.get_events()
            # Block until the work is done here.
            self._work_callback()
            _log.debug("Wooot woot")
            if len(subKeys) > 0:
                for x in subKeys:
                    _log.debug("Publish to volttron: {}".format(self._registered_fncs_topics[x]['volttron_topic']))
                    _log.debug("{} is {}".format(x, fncs.get_value(x)))
            # if subKeys:
            #     _log.debug("Subkeys are: %s", subKeys)
            # else:
            #     if fncs.get_value("a"):
            #         for x in fncs.get_value('a'):
            #             _log.debug(fncs.get_value("a"))

            # This allows other event loops to run
            gevent.sleep(0.000000001)

        self._simulation_complete = True
        fncs.finalize()

    @property
    def fncs_installed(self):
        """ Allows caller to determine if the fncs module is available.
        """
        return HAS_FNCS

    def __raise_if_not_installed(self):
        if not self.fncs_installed:
            raise RuntimeError("Missing fncs python library.")

    @property
    def fncs_version(self):
        self.__raise_if_not_installed()
        return fncs.get_version()


