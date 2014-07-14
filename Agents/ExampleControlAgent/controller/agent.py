# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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


import sys
import random

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils, matching
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics


def ControllerAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            value = kwargs.pop(name)
        except KeyError:
            return config[name]

    agent_id = get_config('agentid')
    rtu_path = {
        'campus': get_config('campus'),
        'building': get_config('building'),
        'unit': get_config('unit'),
    }
    fan_point = get_config('fan_point')

    class Agent(PublishMixin, BaseAgent):
        '''Agent to control cool fan speed with outside air temperature.

        This agent listens for outdoor temperature readings then changes
        the cool fan speed.  It demonstrates pub/sub interaction with
        the RTU Controller.

        Requirements for running this agent (or any agent wishing to
        interact with the RTU:

          * Edit the driver.ini file to reflect the sMAP key, UUID, and
            other settings for your installation.
          * Activate the project Python from the project dir: .
            bin/activate.
          * Launch the sMAP driver by starting (from the project
            directory): twistd -n smap your_driver.ini.
          * Launch the ActuatorAgent just as you would launch any other
            agent.

        With these requirements met:

          * Subscribe to the outside air temperature topic.
          * If the new reading is higher than the old reading then
            * Request the actuator lock for the rtu
          * If it receives a lock request success it randomly sets the
            cool supply fan to a new reading.
          * If it does not get the lock, it will try again the next time
            the temperature rises.
          * If the set result is a success, it releases the lock.
        '''

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.prev_temp = 0

        def change_coolspeed(self):
            '''Setup our request'''
            headers = {
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                'requesterID': agent_id
            }
            self.publish(topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path), headers)

        @matching.match_exact(topics.DEVICES_VALUE(point='OutsideAirTemperature',
                                               **rtu_path))
        def on_outside_temp(self, topic, headers, message, match):
            '''Respond to the outside air temperature events.'''

            print "Topic: {topic}, {headers}, Message: {message}".format(
                    topic=topic, headers=headers, message=message)
            #Content type is json, load it for use
            cur_temp = jsonapi.loads(message[0])
            #If temp has risen, attempt to set cool supply fan
            if cur_temp > self.prev_temp:
                self.change_coolspeed()
            self.prev_temp = cur_temp

        @matching.match_exact(topics.ACTUATOR_LOCK_RESULT(**rtu_path))
        def on_lock_result(self, topic, headers, message, match):
            '''Respond to lock result events.'''

            print "Topic: {topic}, {headers}, Message: {message}".format(
                    topic=topic, headers=headers, message=message)
            if headers['requesterID'] != agent_id:
                #If we didn't request this lock, we don't care about the result
                print "Not me, don't care."
                return

            mess = jsonapi.loads(message[0])
            #If we got a success then set it at a random value
            if mess == 'SUCCESS':
                setting = random.randint(10, 90)
                headers[headers_mod.CONTENT_TYPE] = (
                        headers_mod.CONTENT_TYPE.PLAIN_TEXT)
                headers['requesterID'] = agent_id
                self.publish(topics.ACTUATOR_SET(point=fan_point, **rtu_path),
                        headers, agent_id)
            elif mess == 'RELEASE':
                #Our lock release result was a success
                print "Let go of lock"

        @matching.match_exact(topics.ACTUATOR_VALUE(point=fan_point, **rtu_path))
        def on_set_result(self, topic, headers, message, match):
            '''Result received, release the lock'''
            print "Topic: {topic}, {headers}, Message: {message}".format(
                    topic=topic, headers=headers, message=message)
            self.publish(topics.ACTUATOR_LOCK_RELEASE(**rtu_path),
                    headers, agent_id)
    Agent.__name__ = 'ControllerAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(ControllerAgent,
                       description='Example VOLTTRON platform™ controller agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

