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

#}}}

import logging
import sys

import greenlet
from zmq.utils import jsonapi

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green, utils, matching
from volttron.platform.messaging import topics
#from volttron.platform.messaging import headers as headers_mod

import settings


_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)


def afdd(agent):
    #Data from Voltron
    _log.debug("Rob: AFDD2 is running...")
    data = agent.get_new_data()
    
    return_temp = data["ReturnAirTemperature"]
    outdoor_temp = data["OutsideAirTemperature"]
    mixed_temp = data["MixedAirTemperature"]
    
    # Main Algorithm
    if ((mixed_temp < outdoor_temp and mixed_temp < return_temp) or
            (mixed_temp > outdoor_temp and mixed_temp > return_temp)):
        if not agent.set_point('Damper', 0, settings.sync_trial_time):
            _log.debug("Lock not Received from controller")
            return 29

        agent.sleep(settings.afdd2_seconds_to_steady_state)
        data = agent.get_new_data()
        delta = abs(data["MixedAirTemperature"] -
                    data["ReturnAirTemperature"])
        if delta < settings.afdd2_temperature_sensor_threshold:
            _log.debug("Outdoor-air temperature sensor problem")
            return 21
        if not agent.set_point('Damper', 100, settings.sync_trial_time):
            _log.debug("Lock not Received from controller")
            return 29

        agent.sleep(settings.afdd2_seconds_to_steady_state)
        data = agent.get_new_data()
        delta = abs(data["MixedAirTemperature"] -
                    data["OutsideAirTemperature"])
        if delta < settings.afdd2_temperature_sensor_threshold:
            _log.debug("Return-air temperature sensor problem")
            return 22

        #If it comes here => both tests fail
        _log.debug("Mixed-air temperature sensor problem")
        return 23
    _log.debug("No Temperature Sensor faults detected")
    return 20



def AFDDAgent(config_path, **kwargs):
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])

    class Agent(PublishMixin, BaseAgent):
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.lock_timer = None
            self.lock_acquired = False
            self.tasklet = None
            self.data_queue = green.WaitQueue(self.timer)
            self.value_queue = green.WaitQueue(self.timer)

        def setup(self):
            super(Agent, self).setup()
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            self.lock_timer = self.periodic_timer(1, self.publish,
                    topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path), headers)

        def start(self, algo=None):
            if algo is None:
                algo = afdd
            self.tasklet = greenlet.greenlet(algo)
            self.tasklet.switch(self)

        @matching.match_exact(topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path))
        def on_lock_sent(self, topic, headers, message, match):
            self.lock_timer.cancel()

        @matching.match_exact(topics.ACTUATOR_LOCK_RESULT(**rtu_path))
        def on_lock_result(self, topic, headers, message, match):
            msg = jsonapi.loads(message[0])
            holding_lock = self.lock_acquired
            if headers['requesterID'] == agent_id:
                self.lock_acquired = msg == 'SUCCESS'
            elif msg == 'SUCCESS':
                self.lock_acquired = False
            if self.lock_acquired and not holding_lock:
                self.start()

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def on_new_data(self, topic, headers, message, match):
            data = jsonapi.loads(message[0])
            self.data_queue.notify_all(data)
    
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **rtu_path))
        def on_set_result(self, topic, headers, message, match):
            self.value_queue.notify_all((match.group(1), True))
    
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **rtu_path))
        def on_set_error(self, topic, headers, message, match):
            self.value_queue.notify_all((match.group(1), False))

        def sleep(self, timeout):
            _log.debug('sleep({})'.format(timeout))
            green.sleep(timeout, self.timer)

        def get_new_data(self, timeout=None):
            _log.debug('get_new_data({})'.format(timeout))
            return self.data_queue.wait(timeout)

        def set_point(self, point_name, value, timeout=None):
            _log.debug('set_point({}, {}, {})'.format(point_name, value, timeout))
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            self.publish(topics.ACTUATOR_SET(point=point_name, **rtu_path),
                         headers, str(value))
            try:
                return self.value_queue.wait(timeout)
            except green.Timeout:
                return None

    Agent.__name__ = 'AFDDAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(AFDDAgent,
                       description='VOLTTRON platform™ AFDD agent',
                       argv=argv)


def test():
    import threading, time
    from volttron.platform.agent import periodic

    def TestAgent(config_path, condition, **kwargs):
        config = utils.load_config(config_path)
        agent_id = config['agentid']
        rtu_path = dict((key, config[key])
                        for key in ['campus', 'building', 'unit'])

        class Agent(PublishMixin, BaseAgent):
            def __init__(self, **kwargs):
                super(Agent, self).__init__(**kwargs)
                
            def setup(self):
                super(Agent, self).setup()
                self.damper = 0
                with condition:
                    condition.notify()                

            @matching.match_regex(topics.ACTUATOR_LOCK_ACQUIRE() + '(/.*)')
            def on_lock_result(self, topic, headers, message, match):
                _log.debug("Topic: {topic}, {headers}, Message: {message}".format(
                        topic=topic, headers=headers, message=message))
                self.publish(topics.ACTUATOR_LOCK_RESULT() + match.group(0),
                             headers, jsonapi.dumps('SUCCESS'))

            @matching.match_regex(topics.ACTUATOR_SET() + '(/.*/([^/]+))')
            def on_new_data(self, topic, headers, message, match):
                _log.debug("Topic: {topic}, {headers}, Message: {message}".format(
                        topic=topic, headers=headers, message=message))
                if match.group(2) == 'Damper':
                    self.damper = int(message[0])
                self.publish(topics.ACTUATOR_VALUE() + match.group(0),
                             headers, message[0])

            @periodic(5)
            def send_data(self):
                data = {
                    'ReturnAirTemperature': 55,
                    'OutsideAirTemperature': 50,
                    'MixedAirTemperature': 45,
                    'Damper': self.damper
                }
                self.publish_ex(topics.DEVICES_VALUE(point='all', **rtu_path),
                                {}, ('application/json', jsonapi.dumps(data)))

        Agent.__name__ = 'TestAgent'
        return Agent(**kwargs)

    settings.afdd2_seconds_to_steady_state = 3
    settings.sync_trial_time = 10
    condition = threading.Condition()
    t = threading.Thread(target=utils.default_main, args=(TestAgent, 'test'),
                         kwargs={'condition': condition})
    t.daemon = True
    t.start()
    with condition:
        condition.wait()
    main()


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(test())
    except KeyboardInterrupt:
        pass
