# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import datetime
import dateutil
import gevent
import os
import pytest
import sys
import time
import zmq
from volttron.platform import get_ops

# from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper, get_rand_vip, cleanup_wrapper

DEBUGGER_CONFIG = {
    "agent": {
        "exec": "messagedebuggeragent-1.0-py2.7.egg --config \"%c\" --sub \"%s\" --pub \"%p\""
    },
    "agentid": "messagedebugger",
    "router_path": "$VOLTTRON_HOME/run/messagedebug",
    "monitor_path": "$VOLTTRON_HOME/run/messageviewer",
    "db_path": "$VOLTTRON_HOME/data/messagedebugger.sqlite"
}


@pytest.fixture(scope='module')
def agent(request, volttron_instance_msgdebug):
    platform_uuid = volttron_instance_msgdebug.install_agent(agent_dir=get_ops("MessageDebuggerAgent"),
                                                           config_file=DEBUGGER_CONFIG,
                                                           start=True)
    gevent.sleep(2)
    msg_debugger_agent = volttron_instance_msgdebug.build_agent()
    gevent.sleep(20)  # wait for the agent to start

    def stop():
        volttron_instance_msgdebug.stop_agent(platform_uuid)
        msg_debugger_agent.core.stop()

    request.addfinalizer(stop)
    return msg_debugger_agent


@pytest.mark.usefixtures('agent')
class TestMessageDebugger:
    """
        Regression tests for the MessageDebuggerAgent.
    """

    # @pytest.mark.skip(reason="Dependency on SQLAlchemy library")
    def test_rpc_calls(self, agent):
        """Test the full range of RPC calls to the MessageDebuggerAgent, except those related to streaming."""

        # Start by loading up two short (10-second) DebugSessions for testing purposes.
        # Each session contains at least one DebugMessage (i.e., for the RPC call generated from here).
        # This also confirm the ability to enable and disable message debugging.

        # First DebugSession
        self.issue_rpc_call(agent, 'disable_message_debugging')
        response = self.issue_rpc_call(agent, 'enable_message_debugging')
        assert 'started' in response
        self.list_sessions(agent)
        time.sleep(10)
        response = self.issue_rpc_call(agent, 'disable_message_debugging')
        assert 'stopped' in response

        # Second DebugSession
        self.issue_rpc_call(agent, 'enable_message_debugging')
        self.list_sessions(agent)
        time.sleep(10)
        self.issue_rpc_call(agent, 'disable_message_debugging')

        # The session should have a non-empty end time because it was just explicitly stopped
        last_session = self.list_sessions(agent)[-1]
        assert last_session['end_time']
        session_id = str(last_session['rowid'])

        filters = {}

        # Confirm that some DebugMessages are returned by a query
        response = self.issue_rpc_call(agent, 'execute_db_query', 'DebugMessage', filters=filters)
        assert type(response) is dict
        assert len(response['results']) > 0

        filters = {'session_id': session_id}

        # Confirm that all DebugMessages in a query response are for the session_id applied by the filter
        response = self.issue_rpc_call(agent, 'execute_db_query', 'DebugMessage', filters=filters)
        assert type(response) is dict
        assert len(response['results']) > 0
        for msg in response['results']:
            assert str(msg['session_id']) == session_id

        # Confirm that all DebugMessages in a message_exchange_details query response share a common request_id
        # Select a message that has a non-empty request ID
        one_msg = next((msg for msg in response['results'] if msg['request_id']), None)
        assert one_msg is not None
        request_id = one_msg['request_id']
        response = self.issue_rpc_call(agent, 'message_exchange_details', request_id)
        for msg in response['results']:
            assert str(msg['request_id']) == request_id

        # Confirm that high verbosity responses have long-form timestamp strings
        self.issue_rpc_call(agent, 'set_verbosity', 'high')
        response = self.issue_rpc_call(agent, 'message_exchange_details', request_id)
        timestamp_string = response['results'][0]['timestamp']
        assert str(dateutil.parser.parse(timestamp_string)) == timestamp_string

        # Confirm that low verbosity responses have short-form timestamp strings
        self.issue_rpc_call(agent, 'set_verbosity', 'low')
        response = self.issue_rpc_call(agent, 'message_exchange_details', request_id)
        timestamp_string = response['results'][0]['timestamp']
        valid_timestamp = datetime.datetime.strptime(timestamp_string, '%X')

        # Confirm that all DebugMessageExchanges in a query response are for the session_id applied by the filter
        response = self.issue_rpc_call(agent, 'execute_db_query', 'DebugMessageExchange', filters=filters)
        assert type(response) is dict
        assert len(response['results']) > 0
        for msg in response['results']:
            assert str(msg['session_id']) == session_id

        # Confirm that the response to session_details_by_agent contains stats for a messagedebugger receiver
        response = self.issue_rpc_call(agent, 'session_details_by_agent', session_id)
        assert response['message_count'] > 0
        assert 'messagedebugger' in response['stats']

        # Confirm that the response to session_details_by_topic contains stats for a messagedebugger sender
        response = self.issue_rpc_call(agent, 'session_details_by_topic', session_id)
        assert response['message_count'] > 0
        assert 'messagedebugger' in response['stats']['']

        # Confirm that a deleted DebugSession is absent in a subsequent list_sessions call
        self.issue_rpc_call(agent, 'delete_debugging_session', session_id)
        session_list = self.list_sessions(agent)
        session_for_id = next((session for session in session_list if session['rowid'] == session_id), None)
        assert session_for_id is None

        # Finally, confirm that delete_debugging_db results in no DebugSessions
        self.issue_rpc_call(agent, 'delete_debugging_db')
        response = self.issue_rpc_call(agent, 'execute_db_query', 'DebugSession', filters={})
        assert response == 'No query results'

    def xx_test_message_streaming(self, agent):
        """Test enabling/disabling message streaming, and receiving streamed messages from the Agent."""

        # @todo This test is temporarily disabled.
        # @todo An environment issue was preventing it from passing: no messages were received on the socket.

        def seconds_elapsed(start, elapsed_seconds):
            return datetime.datetime.now() > start + datetime.timedelta(seconds=elapsed_seconds)

        # Confirm that a message is received on the stream
        self.issue_rpc_call(agent, 'enable_message_streaming')
        monitor_socket = self.subscribe_to_monitor_socket()
        assert monitor_socket.recv()

        self.issue_rpc_call(agent, 'disable_message_streaming')
        # There may be some residual messages on the socket after streaming is disabled. Flush them.
        # Confirm that no more messages arrive after the first 5 seconds.
        time_disabled = datetime.datetime.now()
        while True:
            try:
                monitor_socket.recv(zmq.NOBLOCK)
                assert not seconds_elapsed(time_disabled, 5)
            except zmq.Again:
                if seconds_elapsed(time_disabled, 10):
                    break

    def list_sessions(self, agt):
        response = self.issue_rpc_call(agt, 'execute_db_query', 'DebugSession', filters={})
        assert type(response) is dict
        assert len(response['results']) > 0
        return response['results']

    @staticmethod
    def issue_rpc_call(agt, rpc_name, *args, **kwargs):
        return agt.vip.rpc.call('messagedebugger', rpc_name, *args, **kwargs).get(timeout=30)

    @staticmethod
    def subscribe_to_monitor_socket():
        monitor_path = os.path.expandvars('$VOLTTRON_HOME/run/messageviewer')
        monitor_socket = zmq.Context().socket(zmq.SUB)
        monitor_socket_address = 'ipc://{}'.format('@' if sys.platform.startswith('linux') else '') + monitor_path
        monitor_socket.bind(monitor_socket_address)
        monitor_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        return monitor_socket
