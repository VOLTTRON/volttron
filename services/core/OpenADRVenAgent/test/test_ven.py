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

from datetime import timedelta
import gevent
import json
import logging
import os
import pytest
import random
import requests
import sqlite3
import time

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttrontesting.platform.test_platform_web import _build_web_agent
from volttrontesting.utils.platformwrapper import start_wrapper_platform

utils.setup_logging()
_log = logging.getLogger(__name__)

DB_PATH = '$VOLTTRON_HOME/data/test_openadr.sqlite'
VEN_AGENT_ID = 'venagent'
CONTROL_AGENT_ID = 'vencontrolagent'
POLL_INTERVAL_SECS = 5

VEN_AGENT_CONFIG = {
    "ven_id": "0",
    "ven_name": "ven01",
    "vtn_id": "vtn01",
    # Configure an unreachable VTN address to avoid disturbing real VTNs with test behavior
    "vtn_address": "http://unreachable:8000",
    #
    # Other VEN parameters
    #
    "db_path": DB_PATH,
    "send_registration": "False",
    "security_level": "standard",
    "poll_interval_secs": POLL_INTERVAL_SECS,
    "log_xml": "True",
    "opt_in_timeout_secs": 3600,
    "opt_in_default_decision": "optOut",
    "request_events_on_startup": "False",
    #
    # VEN reporting configuration
    #
    "report_parameters": {
        "telemetry": {
            "report_name": "TELEMETRY_USAGE",
            "report_name_metadata": "METADATA_TELEMETRY_USAGE",
            "report_specifier_id": "telemetry",
            "report_interval_secs_default": "30",
            "telemetry_parameters": {
                "baseline_power_kw": {
                    "r_id": "baseline_power",
                    "report_type": "baseline",
                    "reading_type": "Direct Read",
                    "units": "powerReal",
                    "method_name": "get_baseline_power",
                    "min_frequency": 30,
                    "max_frequency": 60
                },
                "current_power_kw": {
                    "r_id": "actual_power",
                    "report_type": "reading",
                    "reading_type": "Direct Read",
                    "units": "powerReal",
                    "method_name": "get_current_power",
                    "min_frequency": 30,
                    "max_frequency": 60
                }
            }
        }
    }
}

CONTROL_AGENT_CONFIG = {
    "venagent_id": VEN_AGENT_ID,
    "opt_type": "optIn"
}

web_server_address = None


@pytest.fixture(scope="module")
def test_agent(request, get_volttron_instances):
    """Create test fixtures: a test agent plus a Volttron instance running a web agent, VEN agent, and ControlAgent."""

    instance = get_volttron_instances(1, should_start=False)
    start_wrapper_platform(instance, with_http=True)

    # Delete $VOLTTRON_HOME/data/test_openadr.sqlite so that old db data won't interfere with new testing.
    db_path = os.path.expandvars(DB_PATH)
    if os.path.exists(db_path):
        os.remove(db_path)

    # Install and start a WebAgent.
    web_agent = _build_web_agent(instance.volttron_home)
    gevent.sleep(1)
    web_agent_id = instance.install_agent(agent_dir=web_agent)

    global web_server_address
    web_server_address = instance.bind_web_address

    # Install and start an OpenADRVenAgent.
    agent_dir = 'services/core/OpenADRVenAgent'
    ven_agent_id = instance.install_agent(agent_dir=agent_dir,
                                          config_file=VEN_AGENT_CONFIG,
                                          vip_identity=VEN_AGENT_ID,
                                          start=True)

    # Install and start a ControlAgentSim.
    agent_dir = 'services/core/OpenADRVenAgent/test/ControlAgentSim'
    control_agent_id = instance.install_agent(agent_dir=agent_dir,
                                              config_file=CONTROL_AGENT_CONFIG,
                                              vip_identity=CONTROL_AGENT_ID,
                                              start=True)

    test_agt = instance.build_agent()

    def stop():
        instance.stop_agent(control_agent_id)
        instance.stop_agent(ven_agent_id)
        instance.stop_agent(web_agent_id)
        test_agt.core.stop()
        instance.shutdown_platform()

    request.addfinalizer(stop)

    yield test_agt


@pytest.mark.skip(reason="Dependencies on Python libraries in OpenADRVenAgent/requirements.txt")
class TestOpenADRVenAgent:
    """Regression tests for the Open ADR VEN Agent."""

    def test_event_opt_in(self, test_agent):
        """
            Test a control agent's event optIn.

            Create an event, then send an RPC that opts in. Get the event and confirm its optIn status.

        @param test_agent: This test agent.

        """
        self.vtn_request('EiEvent', 'test_vtn_distribute_event')
        self.send_rpc(test_agent, 'respond_to_event', '4', 'optIn')
        assert self.get_event_dict(test_agent, '4').get('opt_type') == 'optIn'

    def test_event_opt_out(self, test_agent):
        """
            Test a control agent's event optOut.

            Create an event, then send an RPC that opts out. Get the event and confirm its optOut status.

        @param test_agent: This test agent.

        """
        self.vtn_request('EiEvent', 'test_vtn_distribute_event')
        self.send_rpc(test_agent, 'respond_to_event', '4', 'optOut')
        assert self.get_event_dict(test_agent, '4').get('opt_type') == 'optOut'

    def test_event_activation(self, test_agent):
        """
            Test event activation at its start_time.

            Time the test so that the event's start_time arrives. Confirm the event's state change.

        @param test_agent: This test agent.
        """
        self.vtn_request_variable_event('6', utils.get_aware_utc_now(), 60 * 60 * 24)
        assert self.get_event_dict(test_agent, '6').get('status') == 'active'

    def test_event_completion(self, test_agent):
        """
            Test event completion at its end_time.

            Time the test so that the event's end_time arrives. Confirm the event's state change.

        @param test_agent: This test agent.
        """
        self.vtn_request_variable_event('7', utils.get_aware_utc_now(), 1)
        assert self.get_event_dict(test_agent, '7').get('status') == 'completed'

    def test_event_cancellation(self, test_agent):
        """
            Test event cancellation by the VTN.

            Create an event, then send an XML request to cancel it. Confirm the event's status change.

        @param test_agent: This test agent.
        """
        self.vtn_request('EiEvent', 'test_vtn_distribute_event_no_end')
        self.vtn_request('EiEvent', 'test_vtn_cancel_event')
        assert self.get_event_dict(test_agent, '5').get('status') == 'cancelled'

    def test_report_creation(self, test_agent):
        """
            Test report creation by the VTN.

            Create a report by sending an XML request. Confirm that the report is active.
        """
        self.vtn_request('EiReport', 'test_vtn_registered_report')
        response = self.send_rpc(test_agent, 'get_telemetry_parameters')
        report_params = response.get('report parameters')
        assert report_params.get('status') == 'active'

    def get_event_dict(self, agt, event_id):
        """
            Issue an RPC call to the VEN agent, getting a dictionary describing the test event.

        @param agt: This test agent.
        @param event_id: ID of the test event.
        """
        events_list = self.send_rpc(agt, 'get_events', event_id=event_id)
        print('events returned from get_events RPC call: {}'.format(events_list))
        assert len(events_list) > 0
        assert events_list[0].get('event_id') == event_id
        return events_list[0]

    @staticmethod
    def send_rpc(agt, rpc_name, *args, **kwargs):
        """
            Send an RPC request to the VENAgent and return its response.

        @param agt: This test agent.
        @param rpc_name: The name of the RPC request.
        """
        response = agt.vip.rpc.call(VEN_AGENT_ID, rpc_name, *args, **kwargs)
        return response.get(30)

    def vtn_request_variable_event(self, event_id, start_time, duration_secs):
        """
            Push an oadrDistributeEvent VTN request in which the event's start_time and duration
            are adjustable parameters.

        @param event_id: (String) The event's ID.
        @param start_time: (DateTime) The event's start_time.
        @param duration_secs: (Integer seconds) The event's duration.
        """
        import isodate                      # Import the library only if the test is not skipped
        self.vtn_request('EiEvent',
                         'test_vtn_distribute_event_variable',
                         event_id=event_id,
                         event_start_time=isodate.datetime_isoformat(start_time),
                         event_duration=isodate.duration_isoformat(timedelta(seconds=duration_secs)))
        # Sleep for an extra cycle to give the event time to change status to active, completed, etc.
        time.sleep(POLL_INTERVAL_SECS + 1)

    @staticmethod
    def vtn_request(service_name, xml_filename, event_id=None, event_start_time=None, event_duration=None):
        """
            Push a VTN request to the VEN, sending the contents of the indicated XML file.

        @param service_name: The service name as it appears in the URL.
        @param xml_filename: The distinguishing part of the sample data file name.
        @param event_id: The event ID.
        @param event_start_time: The time that the test event should become active. Modifies the XML string.
        @param event_duration: The test event's duration. Modifies the XML string.
        """
        global web_server_address
        xml_filename = get_services_core("OpenADRVenAgent/test/xml/{}.xml".format(xml_filename))
        with open(xml_filename, 'rb') as xml_file:
            xml_string = xml_file.read()
            if event_id:
                # Modify the XML, substituting in a custom event ID, start_time and duration.
                xml_string = xml_string.format(event_id=event_id,
                                               event_start_time=event_start_time,
                                               event_duration=event_duration)
            requests.post('{}/OpenADR2/Simple/2.0b/{}'.format(web_server_address, service_name),
                          data=xml_string,
                          headers={'content-type': 'application/xml'})
        time.sleep(POLL_INTERVAL_SECS + 1)           # Wait for the request to be dequeued and handled.

    @staticmethod
    def database_connection():
        """
            Initialize a connection to the sqlite database, and return the connection.
        """
        # This method isn't currently used. It's held in reserve in case tests need to look directly at db objects.
        return sqlite3.connect(os.path.expandvars(DB_PATH))
