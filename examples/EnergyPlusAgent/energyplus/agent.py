# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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


__docformat__ = 'reStructuredText'

import gevent
import logging
import sys
import collections
from datetime import datetime

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from integrations.energyplus_integration import EnergyPlusSimIntegration
from volttron.platform.messaging import headers as headers_mod
from datetime import timedelta as td
from math import modf

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'


def energyplus_example(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: EnergyPlusAgent
    :rtype: EnergyPlusAgent
    """
    _log.debug("CONFIG PATH: {}".format(config_path))
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    _log.debug("CONFIG: {}".format(config))
    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    return EnergyPlusAgent(config, **kwargs)


class EnergyPlusAgent(Agent):
    def __init__(self, config, **kwargs):
        super(EnergyPlusAgent, self).__init__(enable_store=False, **kwargs)
        self.config = config
        self.inputs = []
        self.outputs = []
        self.cosimulation_advance = None
        self._now = None
        self.num_of_pub = None
        self.tns_actuate = None
        self.rt_periodic = None
        self.EnergyPlus_sim = EnergyPlusSimIntegration(self.config, self.vip.pubsub, self.core)
        _log.debug("vip_identity: " + self.core.identity)

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        if 'outputs' in self.config:
            self.outputs = self.config['outputs']

        self.cosimulation_advance = self.config.get('cosimulation_advance', None)
        self._now = datetime.utcnow()
        self.num_of_pub = 0

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        """
        Subscribe to VOLTTRON topics on VOLTTRON message bus.
        Register config parameters with EnergyPlus
        Start EnergyPlus simulation.
        """
        # Exit if EnergyPlus isn't installed in the current environment.
        if not self.EnergyPlus_sim.is_sim_installed():
            _log.error("EnergyPlus is unavailable please install it before running this agent.")
            self.core.stop()
            return

        # Register the config and output callback with EnergyPlus
        self.EnergyPlus_sim.register_inputs(self.config, self.do_work)

        # Pick out VOLTTRON topics and subscribe to VOLTTRON message bus
        self.subscribe()
        self.clear_last_update()
        self.cosimulation_advance = self.config.get('cosimulation_advance', None)

        if self.cosimulation_advance is not None:
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=self.cosimulation_advance,
                                      callback=self.advance_simulation)
        # Start EnergyPlus simulation
        self.EnergyPlus_sim.start_simulation()

    def subscribe(self):
        """
        Subscribe to VOLTTRON topics
        :return:
        """
        for obj in self.EnergyPlus_sim.inputs:

            topic = obj.get('topic', None)
            if topic is not None:
                callback = self.on_match_topic
                _log.info('subscribed to ' + topic)
                self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=callback)

    def publish_all_outputs(self):
        """
        Pull out relevant fields from EnergyPlus output message
        and publish on VOLTTRON message bus using corresponding topic
        :param args:
        :return:
        """
        _now = self._create_simulation_datetime()
        _log.info(f"Publish the building response for timestamp: {_now}.")

        headers = {headers_mod.DATE: _now, headers_mod.TIMESTAMP: _now}
        topics = collections.OrderedDict()

        for obj in self.outputs:
            if 'topic' in obj and 'value' in obj:
                topic = obj.get('topic', None)
                value = obj.get('value', None)
                field = obj.get('field', None)
                metadata = obj.get('meta', {})
                if topic is not None and value is not None:
                    if topic not in topics:
                        topics[topic] = {'values': None, 'fields': None}
                    if field is not None:
                        if topics[topic]['fields'] is None:
                            topics[topic]['fields'] = [{}, {}]
                        topics[topic]['fields'][0][field] = value
                        topics[topic]['fields'][1][field] = metadata
                    else:
                        if topics[topic]['values'] is None:
                            topics[topic]['values'] = []
                        topics[topic]['values'].append([value, metadata])

        for topic, obj in topics.items():
            if obj['values'] is not None:
                for value in obj['values']:
                    out = value
                    _log.info('Sending: ' + topic + ' ' + str(out))
                    self.vip.pubsub.publish('pubsub', topic, headers, out).get()
            if obj['fields'] is not None:
                out = obj['fields']
                _log.info(f"Sending: {topic} {out}")
                while True:
                    try:
                        self.vip.pubsub.publish('pubsub', topic, headers, out).get()
                    except:
                        _log.debug("Again ERROR: retrying publish")
                        gevent.sleep(0.1)
                        continue
                    break
            self.num_of_pub += 1

    def _create_simulation_datetime(self):
        """
        Build simulation datetime
        :return:
        """
        self._now = self._now + td(minutes=1)

        if self.EnergyPlus_sim.month is None or \
                self.EnergyPlus_sim.day is None or \
                self.EnergyPlus_sim.minute is None or \
                self.EnergyPlus_sim.hour is None:
            _now = self._now
        else:
            if self.num_of_pub >= 1:
                if abs(self.EnergyPlus_sim.minute - 60.0) < 0.5:
                    self.EnergyPlus_sim.hour += 1.0
                    self.EnergyPlus_sim.minute = 0.0
                if abs(self.EnergyPlus_sim.hour - 24.0) < 0.5:
                    self.EnergyPlus_sim.hour = 0.0
                    self.EnergyPlus_sim.day += 1.0
            else:
                self.EnergyPlus_sim.hour = 0.0
                self.EnergyPlus_sim.minute = 0.0
            second, minute = modf(self.EnergyPlus_sim.minute)
            self.EnergyPlus_sim.second = int(second * 60.0)
            self.EnergyPlus_sim.minute = int(minute)
            date_string = '2017-' + str(self.EnergyPlus_sim.month).replace('.0', '') + \
                          '-' + str(self.EnergyPlus_sim.day).replace('.0', '') + ' ' + \
                          str(self.EnergyPlus_sim.hour).replace('.0', '') + ':' + \
                          str(self.EnergyPlus_sim.minute) + ':' + \
                          str(self.EnergyPlus_sim.second)
            _now = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        _now = _now.isoformat(' ') + 'Z'
        return _now

    def on_match_topic(self, peer, sender, bus, topic, headers, message):
        """
        Callback to capture VOLTTRON messages
        :param peer: 'pubsub'
        :param sender: sender identity
        :param bus:
        :param topic: topic for the message
        :param headers: message header
        :param message: actual message
        :return:
        """
        msg = message if type(message) == type([]) else [message]
        _log.info(f"Received: {topic} {msg}")
        self.update_topic(topic, headers, msg)

    def update_topic(self, topic, headers, message):
        """
        :param topic: topic for the message
        :param headers: message header
        :param message: actual message
        :return:
        """
        objs = self.get_inputs_from_topic(topic)
        if objs is None:
            return
        for obj in objs:
            value = message[0]
            if type(value) is dict and 'field' in obj and obj.get('field') in value:
                value = value.get(obj.get('field'))
            obj['value'] = value
            obj['message'] = message[0]
            obj['message_meta'] = message[1]
            obj['last_update'] = headers.get(headers_mod.DATE, datetime.utcnow().isoformat(' ') + 'Z')
            self.send_on_all_inputs_updated()

    def send_on_all_inputs_updated(self):
        """
        Check if all input messages have been updated and then send to EnergyPlus
        :return:
        """
        if self.all_topics_updated():
            self.clear_last_update()
            self.EnergyPlus_sim.send_eplus_msg()

    def all_topics_updated(self):
        """
        Check if all input messages have been updated
        :return:
        """
        for obj in self.EnergyPlus_sim.inputs:
            if 'topic' in obj:
                last_update = obj.get('last_update', None)
                if last_update is None:
                    return False
        return True

    def clear_last_update(self):
        """
        Clear 'last_update' flag
        :return:
        """
        for obj in self.EnergyPlus_sim.inputs:
            if 'topic' in obj:
                obj['last_update'] = None

    def get_inputs_from_topic(self, topic):
        """
        Find all input objects that best match the topic
        :param topic: topic to  match
        :return:
        """
        objs = []
        for obj in self.EnergyPlus_sim.inputs:
            _log.debug("EPLUS: get_inputs_from_topic: {}".format(obj))
            if obj.get('topic') == topic:
                objs.append(obj)
        topic = "/".join(["devices", topic, "all"])
        for obj in self.outputs:
            if obj.get('topic') == topic:
                objs.append(obj)
        if len(objs):
            return objs
        return None

    def find_best_match(self, topic):
        """
        Find all input objects that best match the topic
        :param topic: topic to  match
        :return:
        """
        topic = topic.strip('/')
        device_name, point_name = topic.rsplit('/', 1)
        objs = self.get_inputs_from_topic(device_name)

        if objs is not None:
            for obj in objs:
                # we have matches to the <device topic>,
                # so get the first one has a field matching <point name>
                if obj.get('field', None) == point_name:
                    return obj
        objs = self.get_inputs_from_topic(topic)
        if objs is not None and len(objs):  # we have exact matches to the topic
            return objs[0]
        return None

    def do_work(self):
        """
        Agent callback to receive EnergyPlus outputs
        - Publish all outputs on VOLTTRON message bus
        - Periodically advance simulation by sending and receiving messages to EnergyPlus
        :return:
        """
        _log.debug("do_work:")
        self.outputs = self.EnergyPlus_sim.outputs
        if self.EnergyPlus_sim.sim_flag != '1':
            _log.debug("do_work: self.EnergyPlus_sim.sim_flag != '1'")
            self.publish_all_outputs()
        if self.EnergyPlus_sim.cosimulation_sync:
            _log.debug("do_work: cosimulation_sync == True")
            self.check_advance()
        if self.EnergyPlus_sim.real_time_periodic and self.rt_periodic is None:
            _log.debug("do_work: self.EnergyPlus_sim.timestep: {}".format(self.EnergyPlus_sim.timestep))
            self.EnergyPlus_sim.timestep = 60. / (self.EnergyPlus_sim.timestep * self.EnergyPlus_sim.time_scale) * 60.
            _log.debug("do_work: self.EnergyPlus_sim.timestep: {}".format(self.EnergyPlus_sim.timestep))
            self.rt_periodic = self.core.periodic(self.EnergyPlus_sim.timestep,
                                                  self.run_periodic,
                                                  wait=self.EnergyPlus_sim.timestep)

    def check_advance(self):
        if self.EnergyPlus_sim.real_time_periodic:
            return
        timestep = int(60 / self.EnergyPlus_sim.timestep)

        if not self.EnergyPlus_sim.real_time_flag:
            self.cosim_sync_counter += timestep
            if self.cosim_sync_counter < self.EnergyPlus_sim.co_sim_timestep:
                self.advance_simulation(None, None, None, None, None, None)
            else:
                self.cosim_sync_counter = 0
                self.vip.pubsub.publish('pubsub',
                                        self.tns_actuate,
                                        headers={},
                                        message={}).get(timeout=10)
        else:
            if self.EnergyPlus_sim.hour > self.EnergyPlus_sim.currenthour or self.EnergyPlus_sim.passtime:
                self.EnergyPlus_sim.passtime = True
                self.cosim_sync_counter += timestep
                if self.cosim_sync_counter < self.EnergyPlus_sim.co_sim_timestep:
                    self.advance_simulation(None, None, None, None, None, None)
                else:
                    self.cosim_sync_counter = 0
                    self.vip.pubsub.publish('pubsub',
                                            self.tns_actuate,
                                            headers={},
                                            message={}).get(timeout=10)
            else:
                self.advance_simulation(None, None, None, None, None, None)

        return

    def run_periodic(self):
        """
        Advance the simulation periodically and publish all outputs to VOLTTRON bus
        :return:
        """
        self.advance_simulation(None, None, None, None, None, None)
        self.EnergyPlus_sim.send_eplus_msg()

    def advance_simulation(self, peer, sender, bus, topic, headers, message):
        _log.info('Advancing simulation.')

        for obj in self.EnergyPlus_sim.inputs:
            set_topic = obj['topic'] + '/' + obj['field']
            external = obj.get('external', False)
            if external:
                value = obj['value'] if 'value' in obj else obj['default']
            else:
                value = obj['default']
            self.update_topic_rpc(sender, set_topic, value, external)
        return

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown.
        Stop EnergyPlus simulation
        """
        self.EnergyPlus_sim.stop_simulation()

    @RPC.export
    def request_new_schedule(self, requester_id, task_id, priority, requests):
        """RPC method

        Requests one or more blocks on time on one or more device.
        In this agent, this does nothing!

        :param requester_id: Requester name.
        :param task_id: Task name.
        :param priority: Priority of the task. Must be either HIGH, LOW, or LOW_PREEMPT
        :param requests: A list of time slot requests

        :type requester_id: str
        :type task_id: str
        :type priority: str
        :type request: list
        :returns: Request result
        :rtype: dict

        """
        _log.debug(requester_id + " requests new schedule " + task_id + " " + str(requests))
        result = {'result': SUCCESS,
                  'data': {},
                  'info': ''}
        return result

    @RPC.export
    def request_cancel_schedule(self, requester_id, task_id):
        """RPC method

        Requests the cancelation of the specified task id.
        In this agent, this does nothing!

        :param requester_id: Requester name.
        :param task_id: Task name.

        :type requester_id: str
        :type task_id: str
        :returns: Request result
        :rtype: dict

        """
        _log.debug(requester_id + " canceled " + task_id)
        result = {'result': SUCCESS,
                  'data': {},
                  'info': ''}
        return result

    @RPC.export
    def get_point(self, topic, **kwargs):
        """RPC method

        Gets the value of a specific point on a device_name.
        Does not require the device_name be scheduled.

        :param topic: The topic of the point to grab in the
                      format <device_name topic>/<point name>
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :returns: point value
        :rtype: any base python type

        """
        obj = self.find_best_match(topic)
        if obj is not None:  # we have an exact match to the  <device_name topic>/<point name>, so return the first value
            value = obj.get('value', None)
            if value is None:
                value = obj.get('default', None)
            return value
        return None

    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        """RPC method

        Sets the value of a specific point on a device.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the point to set in the
                      format <device topic>/<point name>
        :param value: Value to set point to.
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str
        :type value: any basic python type
        :returns: value point was actually set to.
        :rtype: any base python type

        """
        topic = topic.strip('/')
        external = True
        if value is None:
            result = self.revert_point(requester_id, topic)
        else:
            result = self.update_topic_rpc(requester_id, topic, value, external)
            _log.debug("Writing: {topic} : {value} {result}".format(topic=topic, value=value, result=result))
        if result == SUCCESS:
            return value
        else:
            raise RuntimeError("Failed to set value: " + result)

    @RPC.export
    def revert_point(self, requester_id, topic, **kwargs):
        """RPC method

        Reverts the value of a specific point on a device to a default state.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the point to revert in the
                      format <device topic>/<point name>
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str

        """
        obj = self.find_best_match(topic)
        if obj and 'default' in obj:
            value = obj.get('default')
            _log.debug("Reverting topic " + topic + " to " + str(value))
            external = False
            result = self.update_topic_rpc(requester_id, topic, value, external)
        else:
            result = FAILURE
            _log.warning("Unable to revert topic. No topic match or default defined!")
        return result

    @RPC.export
    def revert_device(self, requester_id, device_name, **kwargs):
        """RPC method

        Reverts all points on a device to a default state.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the device to revert (without a point!)
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str

        """
        device_name = device_name.strip('/')
        # we will assume that the topic is only the <device topic> and revert all matches at this level!
        objs = self.get_inputs_from_topic(device_name)
        if objs is not None:
            for obj in objs:
                point_name = obj.get('field', None)
                topic = device_name + "/" + point_name if point_name else device_name
                external = False
                if 'default' in obj:
                    value = obj.get('default')
                    _log.debug("Reverting " + topic + " to " + str(value))
                    self.update_topic_rpc(requester_id, topic, value, external)
                else:
                    _log.warning("Unable to revert " + topic + ". No default defined!")

    def update_topic_rpc(self, requester_id, topic, value, external):
        """
        Find the best match for the topic and update the objects with
        received values
        :param requester_id:
        :param topic:
        :param value:
        :param external:
        :return:
        """
        obj = self.find_best_match(topic)
        if obj is not None:
            obj['value'] = value
            obj['external'] = external
            obj['last_update'] = datetime.utcnow().isoformat(' ') + 'Z'
            if not self.EnergyPlus_sim.real_time_periodic:
                self.on_update_topic_rpc(requester_id, topic, value)
            return SUCCESS
        return FAILURE

    def on_update_topic_rpc(self, requester_id, topic, value):
        """
        Send to EnergyPlus
        :param requester_id:
        :param topic:
        :param value:
        :return:
        """
        self.send_on_all_inputs_updated()


def main():
    """Main method called to start the agent."""
    utils.vip_main(energyplus_example, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
