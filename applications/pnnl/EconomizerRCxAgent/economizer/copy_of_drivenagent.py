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


from datetime import datetime
import logging
import posixpath
import sys

from volttron.platform.agent import BaseAgent, PublishMixin, matching, utils
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import topics


__author__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'
__copyright__ = 'Copyright (c) 2015, Battelle Memorial Institute'
__license__ = 'FreeBSD'


def DrivenAgent(config_path, **kwargs):
    config = utils.load_config(config_path)
    agent_id = config.get('agentid')

    validation_error = ""
    device_topic = config.get('device')
    if not device_topic:
        validation_error += "Invalid device specified in config\n"
    else:
        if not device_topic[-4:] == '/all':
            device_topic += '/all'

    application = config.get('application')
    if not application:
        validation_error += "Invalid application specified in config\n"

    utils.setup_logging()
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
    if validation_error:
        _log.error(validation_error)
        raise ValueError(validation_error)
    config.update(kwargs)

    klass = _get_class(application)
    # This instances is used to call the applications run method when
    # data comes in on the message bus.  It is constructed here so that
    # each time run is called the application can keep it state.
    app_instance = klass(**config)


    class Agent(PublishMixin, BaseAgent):
        '''Agent listens to message bus device and runs when data is published.
        '''

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)

            self._update_event = None
            self._update_event_time = None
            self._device_states = {}
            self._kwargs = kwargs
            _log.debug("device_topic is set to: "+device_topic)

        @matching.match_exact(device_topic)
        def on_received_message(self, topic, headers, message, matched):
            _log.debug("Message received")
            _log.debug("MESSAGE: "+ jsonapi.dumps(message[0]))
            _log.debug("TOPIC: "+ topic)
            data = jsonapi.loads(message[0])

            results = app_instance.run(datetime.now(),data)
            self._process_results(results)



        def _process_results(self, results):
            _log.debug('Processing Results!')
            for key, value in results.commands.iteritems():
                _log.debug("COMMAND: {}->{}".format(key, value))
            for value in results.log_messages:
                _log.debug("LOG: {}".format(value))
            for key, value in results.table_output.iteritems():
                _log.debug("TABLE: {}->{}".format(key, value))



    Agent.__name__ = 'DrivenLoggerAgent'
    return Agent(**kwargs)

def _get_class( kls ):
    parts = kls.split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)
    return m

def main(argv=sys.argv):
    '''
    Main method called by the eggsecutable.
    '''
    utils.default_main(DrivenAgent,
                       description='Example VOLTTRON platform™ driven agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
