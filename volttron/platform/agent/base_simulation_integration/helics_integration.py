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

try:
    import helics as h
    HAS_HELICS = True
except ImportError:
    HAS_HELICS = False
    RuntimeError('HELICS must be installed before running this script ')

import logging
import gevent
from volttron.platform.agent.base_simulation_integration import BaseSimIntegration


_log = logging.getLogger(__name__)
__version__ = '1.0'


class HELICSSimIntegration(BaseSimIntegration):
    def __init__(self, config_path):
        super(HELICSSimIntegration, self).__init__(config_path)
        self.fed = None
        self._work_callback = None
        self._simulation_started = False
        self._simulation_complete = False
        self._simulation_delta = self.config.get('timedelta', 1.0) #seconds
        self._simulation_length = self.config.get('simulation_length', 60) #seconds
        self.current_time = None
        self.inputs = []
        self.outputs = []
        self.endpoints = {}
        self.current_values = {}

    def start_simulation(self):
        h.helicsFederateEnterExecutingMode(self.fed)

    def register_inputs(self, config=None, callback=None):
        self._work_callback = callback
        self.fed = h.helicsCreateCombinationFederateFromConfig(self.config_path)
        federate_name = h.helicsFederateGetName(self.fed)
        _log.debug("Federate name: {}".format(federate_name))
        endpoint_count = h.helicsFederateGetEndpointCount(self.fed)
        _log.debug("Endpoint count: {}".format(endpoint_count))
        subkeys_count = h.helicsFederateGetInputCount(self.fed)
        _log.debug("Subscription key count: {}".format(subkeys_count))
        pubkeys_count = h.helicsFederateGetPublicationCount(self.fed)
        _log.debug("Publication key count: {}".format(endpoint_count))

        for i in range(0, endpoint_count):
            endpt_idx = h.helicsFederateGetEndpointByIndex(self.fed, i)
            endpt_name = h.helicsEndpointGetName(endpt_idx)
            self.endpoints[endpt_name] = endpt_idx

        for i in range(0, subkeys_count):
            inputs = dict()
            idx = h.helicsFederateGetInputByIndex(self.fed, i)
            inputs['sub_id'] = idx
            inputs['type'] = h.helicsInputGetType(idx)
            inputs['key'] = h.helicsSubscriptionGetKey(idx)
            self.inputs.append(inputs)
            data = dict(type=inputs['type'], value=None)
            self.current_values[inputs['key']] = data

        for i in range(0, pubkeys_count):
            outputs = dict()
            idx = h.helicsFederateGetPublicationByIndex(self.fed, i)
            outputs['pub_id'] = idx
            outputs['type'] = h.helicsPublicationGetType(idx)
            outputs['key'] = h.helicsPublicationGetKey(idx)
            self.outputs.append(outputs)
            data = dict(type=outputs['type'], value=None)
            self.current_values[outputs['key']] = data

    def _sim_loop(self):
        _log.info("Starting simulation loop")
        self._simulation_started = True
        while self.current_time < self._simulation_length:
            for in_put in self.inputs:
                info = self.current_values[in_put['key']]
                info['value'] = self._get_input_based_on_type(in_put)
            self._work_callback()
            # This allows other event loops to run
            gevent.sleep(0.000000001)
        # Check if anything to publish
        self._simulation_complete = True
        self.stop_simulation()

    def publish_to_simulation(self, topic, message):
        try:
            info = self.outputs[topic]
            info['value'] = message
            self._publish_based_on_type(info)
        except KeyError as e:
            _log.error("Unknown publication key {}".format(topic))

    def _publish_based_on_type(self, output):
        if output['type'] == 'integer':
            h.helicsPublicationPublishInteger(output['pub_id'], output['value'])
        elif output['type'] == 'double':
            h.helicsPublicationPublishDouble(output['pub_id'], output['value'])
        elif output['type'] == 'string':
            h.helicsPublicationPublishString(output['pub_id'], output['value'])
        elif output['type'] == 'complex':
            h.helicsPublicationPublishComplex(output['pub_id'], output['value'])
        elif output['type'] == 'vector':
            h.helicsPublicationPublishVector(output['pub_id'], output['value'])
        elif output['type'] == 'boolean':
            h.helicsPublicationPublishBoolean(output['pub_id'], output['value'])
        else:
            _log.error("Unknown datatype: {}".format(output['type']))

    def _get_input_based_on_type(self, in_put):
        val = None
        sub_id = in_put['sub_id']
        if in_put['type'] == 'integer':
            val = h.helicsInputGetInteger(sub_id)
        elif in_put['type'] == 'double':
            val = h.helicsInputGetDouble(sub_id)
        elif in_put['type'] == 'string':
            val = h.helicsInputGetString(sub_id)
        elif in_put['type'] == 'complex':
            real, imag = h.helicsInputGetComplex(sub_id)
            val = [real, imag]
        elif in_put['type'] == 'vector':
            val = h.helicsInputGetVector(sub_id)
        elif in_put['type'] == 'boolean':
            val = h.helicsInputGetBoolean(sub_id)
        else:
            _log.error("Unknown datatype: {}".format(in_put['type']))
        return val

    def make_time_request(self, time_request=None):
        if time_request is None:
            time_request = self.current_time + self._simulation_delta
        granted_time = h.helicsFederateRequestTime(self.fed, time_request)
        self.current_time = granted_time

    def pause_simulation(self):
        pass

    def resume_simulation(self):
        pass

    def is_sim_installed(self):
        return HAS_HELICS

    def send_to_endpoint(self, endpoint, destination='', value=0):
        endpoint_idx = self.endpoints[endpoint]
        h.helicsEndpointSendMessageRaw(endpoint_idx, destination, str(value))

    def stop_simulation(self):
        h.helicsFederateFinalize(self.fed)
        h.helicsFederateFree(self.fed)
        h.helicsCloseLibrary()
