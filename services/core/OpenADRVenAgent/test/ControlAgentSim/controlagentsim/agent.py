# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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

from __future__ import print_function

from datetime import datetime as dt
from datetime import timedelta
import gevent
import json
import logging
import numpy
import sys

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.messaging import topics

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '1.0'

BASELINE_POWER_KW = 6.2                 # Constant baseline power
SINE_PERIOD_SECS = 600                  # Period of the measurement sine wave
REPORT_INTERVAL_SECS = 30               # How often to report telemetry


def control_agent(config_path, **kwargs):
    """
        Parse the ControlAgentSim configuration file and return an instance of
        the agent that has been created using that configuration.

        See initialize_config() method documentation for a description of each configurable parameter.

    :param config_path: (str) Path to a configuration file.
    :returns: ControlAgentSim instance
    """
    try:
        config = utils.load_config(config_path)
    except StandardError, err:
        _log.error("Error loading configuration: {}".format(err))
        config = {}
    venagent_id = config.get('venagent_id')
    opt_type = config.get('opt_type')
    return ControlAgentSim(venagent_id, opt_type, **kwargs)


class ControlAgentSim(Agent):
    """
        This is a sample ControlAgent for use while demonstrating and testing OpenADRVenAgent.
        It exercises the VEN agent's exposed RPC methods, and consumes messages published by
        OpenADRVenAgent.
    """

    def __init__(self, venagent_id, opt_type, **kwargs):
        super(ControlAgentSim, self).__init__(**kwargs)
        self.venagent_id = None
        self.default_opt_type = None
        self.default_config = {'venagent_id': venagent_id,
                               'opt_type': opt_type}
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        self.initialize_config(self.default_config)

    def _configure(self, config_name, action, contents):
        """The agent's config may have changed. Re-initialize it."""
        config = self.default_config.copy()
        config.update(contents)
        self.initialize_config(config)

    def initialize_config(self, config):
        """Initialize the agent's configuration."""
        _log.debug("Configuring agent")
        self.venagent_id = config.get('venagent_id')
        self.default_opt_type = config.get('opt_type')

        _log.debug('Configuration parameters:')
        _log.debug('\tvenagent_id={}'.format(self.venagent_id))
        _log.debug('\tOptIn/OptOut={}'.format(self.default_opt_type))

    @Core.receiver('onstart')
    def onstart_method(self, sender):
        """The agent has started. Perform initialization and spawn the main process loop."""
        _log.debug('Starting agent')

        # Subscribe to the VENAgent's event and report parameter publications.
        self.vip.pubsub.subscribe(peer='pubsub', prefix=topics.OPENADR_EVENT, callback=self.receive_event)
        self.vip.pubsub.subscribe(peer='pubsub', prefix=topics.OPENADR_STATUS, callback=self.receive_status)

        self.core.periodic(REPORT_INTERVAL_SECS, self.issue_rpcs)

    def issue_rpcs(self):
        """Periodically issue RPCs, including report_sample_telemetry, to the VEN agent."""
        self.report_sample_telemetry()
        self.get_events()
        self.get_report_parameters()
        self.set_telemetry_status(online='True', manual_override='False')

    def report_sample_telemetry(self):
        """
            At regular intervals, send sample metrics to the VEN agent as an RPC.

            Send measurements that simulate the following:
                - Constant baseline power
                - Measured power that is a sine wave with amplitude = baseline power
        """

        def sine_wave(t, p):
            """Return the current value at time t of a sine wave from -1 to 1 with period p."""
            seconds_since_hour = (60.0 * int(t.strftime('%M'))) + int(t.strftime('%S'))
            fraction_into_period = (seconds_since_hour % float(p)) / float(p)
            return numpy.sin(2 * numpy.pi * fraction_into_period)

        end_time = utils.get_aware_utc_now()
        start_time = end_time - timedelta(seconds=REPORT_INTERVAL_SECS)
        val = sine_wave(end_time, SINE_PERIOD_SECS)
        # Adjust the sine wave upward so that all values are positive, with amplitude = BASELINE_POWER_KW.
        measurement_kw = BASELINE_POWER_KW * ((val + 1) / 2)
        self.report_telemetry({'baseline_power_kw': str(BASELINE_POWER_KW),
                               'current_power_kw': str(measurement_kw),
                               'start_time': start_time.__str__(),
                               'end_time': end_time.__str__()})

    def receive_event(self, peer, sender, bus, topic, headers, message):
        """(Subscription callback) Receive a list of active events as JSON."""
        event = json.loads(message)
        debug_string = 'Received event: ID={}, status={}, start={}, end={}, opt_type={}, all params={}'
        _log.debug(debug_string.format(event['event_id'],
                                       event['status'],
                                       event['start_time'],
                                       event['end_time'],
                                       event['opt_type'],
                                       message))
        if event['opt_type'] != self.default_opt_type:
            # Send an optIn decision to the VENAgent.
            self.respond_to_event(event['event_id'], self.default_opt_type)

    def receive_status(self, peer, sender, bus, topic, headers, message):
        """(Subscription callback) Receive a list of report parameters as JSON."""
        report = json.loads(message)
        debug_string = 'Received report parameters: request_id={}, status={}, start={}, end={}, all params={}'
        _log.debug(debug_string.format(report['report_request_id'],
                                       report['status'],
                                       report['start_time'],
                                       report['end_time'],
                                       message))
        _log.debug('Received report(s) status: {}'.format(message))

    def respond_to_event(self, event_id, opt_type):
        """
            (Send RPC) Respond to an event, telling the VENAgent whether to opt in or out.

        @param event_id: (String) ID of an event.
        @param opt_type: (String) Whether to optIn or optOut of the event.
        """
        _log.debug('Sending an {} response for event ID {}'.format(opt_type, event_id))
        self.send_rpc('respond_to_event', event_id, opt_type)

    def get_events(self):
        """
            (Send RPC) Request a JSON list of events from the VENAgent.

        @return: (JSON) A list of events.
        """
        _log.debug('Requesting an event list')
        events_string = self.send_rpc('get_events')
        events_list = json.loads(events_string)
        if events_list:
            for event_dict in events_list:
                _log.debug('\tevent_id {}:'.format(event_dict.get('event_id')))
                for k, v in event_dict.iteritems():
                    _log.debug('\t\t{}={}'.format(k, v))
        else:
            _log.debug('\tNo active events')

    def get_report_parameters(self):
        """
            (Send RPC) Request a JSON list of report parameters from the VENAgent.

        @return: (JSON) A list of report parameters.
        """
        _log.debug('Requesting report parameters')
        param_dict = self.send_rpc('get_telemetry_parameters')

        if param_dict:
            for key, val in param_dict.iteritems():
                try:
                    loaded_val = json.loads(val)
                    if type(loaded_val) == dict:
                        _log.debug('\t{}:'.format(key))
                        for key2, val2 in loaded_val.iteritems():
                            if type(val2) == dict:
                                _log.debug('\t\t{}:'.format(key2))
                                for key3, val3 in val2.iteritems():
                                    _log.debug('\t\t\t{}={}'.format(key3, val3))
                            else:
                                _log.debug('\t\t{}={}'.format(key2, val2))
                    else:
                        _log.debug('\t{}={}'.format(key, loaded_val))
                except ValueError:
                    _log.debug('\t{}={}'.format(key, val))
        else:
            _log.debug('\tNo report parameters')

    def set_telemetry_status(self, online=None, manual_override=None):
        """
            (Send RPC) Update the VENAgent's reporting status.

        @param online: (Boolean) Whether the VENAgent's resource is online.
        @param manual_override: (Boolean) Whether resource control has been overridden.
        """
        _log.debug('Setting telemetry status: online={}, manual_override={}'.format(online, manual_override))
        self.send_rpc('set_telemetry_status', online, manual_override)

    def report_telemetry(self, telemetry):
        """
            (Send RPC) Update the VENAgent's report metrics.

        @param telemetry: (JSON) Current value of each report metric.
        """
        _log.debug('Reporting telemetry: {}'.format(telemetry))
        self.send_rpc('report_telemetry', telemetry=telemetry)

    def send_rpc(self, rpc_name, *args, **kwargs):
        """Send an RPC request to the VENAgent, and return its response (if any)."""
        response = self.vip.rpc.call(self.venagent_id, rpc_name, *args, **kwargs)
        return response.get(30)


def main():
    """Start the agent."""
    utils.vip_main(control_agent, identity='controlagentsim', version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
