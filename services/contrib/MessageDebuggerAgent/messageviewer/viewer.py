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

from cmd import Cmd
import gevent

import logging.handlers
import os
import shlex
import sys
import time
import zmq

from volttron.platform import get_address
from volttron.platform.agent.utils import setup_logging
from volttron.platform.control import KnownHostsStore, KeyStore
from volttron.platform.vip.agent import Agent

setup_logging()
# Setting the root logger's level to WARNING so that it won't interfere with single-line message display
logging.getLogger().setLevel(logging.WARNING)
_log = logging.getLogger('messageviewer')
_log.level = logging.WARNING

debugger_connection = None

MAX_COL_WIDTH = 35
MIN_COL_WIDTH = 11

# Display these columns at high verbosity
ALL_COLUMNS = {
    'DebugMessage': [
        'session_id', 'timestamp', 'direction', 'sender', 'recipient',
        'vip_signature', 'user_id', 'request_id', 'subsystem', 'data', 'frame7', 'frame8', 'frame9',
        'method', 'params', 'topic', 'headers', 'message', 'message_value', 'device', 'point',
        'point_value', 'result', 'message_size'
    ],
    'DebugMessageExchange': [
        'sender', 'recipient', 'request_id', 'session_id', 'sender_time', 'recipient_time',
        'topic', 'method', 'device', 'point', 'assignment', 'result'
    ],
    'DebugSession': [
        'rowid', 'created_on', 'start_time', 'end_time', 'num_messages'
    ]
}

# Display these columns at medium/low verbosity
INTERESTING_COLUMNS = {
    'DebugMessage': [
        'timestamp', 'direction', 'sender', 'recipient',
        'request_id', 'subsystem', 'method', 'topic', 'device', 'point', 'result'
    ],
    'DebugMessageExchange': [
        'sender', 'recipient', 'sender_time', 'topic', 'device', 'point', 'result'
    ],
    'DebugSession': [
        'rowid', 'start_time', 'end_time', 'num_messages'
    ]
}

# When displaying messages, ignore messages sent to (or received by) these agents.
EXCLUDED_SENDERS = ['None', '', 'control', 'config.store', 'pubsub', 'control.connection', 'messageviewer.connection',
                    'messagedebugger', 'messagedebugger.loopback_rpc']
EXCLUDED_RECIPIENTS = ['None', '', 'control', 'config.store']


class MessageViewerCmd(Cmd):
    """
        Present a command-line user interface for issuing commands to view
        DebugMessages, DebugMessageExchanges and DebugSessions. View the results.
    """

    def __init__(self):
        Cmd.__init__(self)
        self.prompt = 'Viewer> '
        self._filters = {}
        self._verbosity = 'low'
        self._streaming = False

    def startup(self):
        print('Welcome to the MessageViewer command line. Supported commands include:')
        print('\t display_message_stream')
        print('\t display_messages')
        print('\t display_exchanges')
        print('\t display_exchange_details')
        print('\t display_session_details_by_agent <session_id>')
        print('\t display_session_details_by_topic <session_id>')
        print()
        print('\t list_sessions')
        print('\t set_verbosity <level>')
        print('\t list_filters')
        print('\t set_filter <filter_name> <value>')
        print('\t clear_filters')
        print('\t clear_filter <filter_name>')
        print()
        print('\t start_streaming')
        print('\t stop_streaming')
        print('\t start_session')
        print('\t stop_session')
        print('\t delete_session <session_id>')
        print('\t delete_database')
        print()
        print('\t help')
        print('\t quit')
        self.cmdloop('Please enter a command.')
        exit()

    def do_clear_filters(self, line):
        """Clear all database query filters."""
        self._filters = {}
        print(MessageViewer.set_filters(self._filters))

    def do_set_verbosity(self, line):
        """Set the verbosity level for MessageDebuggerAgent responses; syntax is: set_verbosity <level>"""
        level = self.first_parameter(line)
        if level:
            self._verbosity = level
            print(MessageViewer.set_verbosity(level))
        else:
            print('Please enter a verbosity level')

    def do_display_message_stream(self, line):
        """Display the DebugMessage stream in realtime (subject to filters) as messages are routed."""
        monitor_socket = self.initialize_monitor_socket()
        if not self._streaming:
            # If we weren't streaming already, start doing so now.
            self.start_streaming()
        column_labels = self.column_labels('DebugMessage')
        formatter = None
        received_messages = []
        try:
            while True:
                try:
                    # Gather a list of messages until interrupted by an 'Again', then flush them to the display
                    msg = monitor_socket.recv(zmq.NOBLOCK)
                    received_messages.append(msg)
                except zmq.Again:
                    if len(received_messages) > 0:
                        obj_list = [jsonapi.loads(obj_str) for obj_str in received_messages]
                        data_rows, col_widths = self.data_rows_for_obj_list(obj_list,
                                                                            column_labels,
                                                                            formatter=formatter)
                        if len(data_rows) > 0:
                            if not formatter:
                                formatter = self.left_aligned_formatter(column_labels, col_widths)
                            for row in data_rows:
                                sys.stdout.write(formatter.compose(row))
                    # Now go get some more messages
                    received_messages = []
                    continue
        except KeyboardInterrupt:
            _log.debug('Execution interrupted')

    def do_display_messages(self, line):
        """Display a list of DebugMessages: all messages routed by the VOLTTRON router (subject to filters)"""
        object_type = 'DebugMessage'
        if 'freq' in self._filters:
            self.display_single_line(object_type)
        else:
            self.print_response_dict(object_type, MessageViewer.display_db_objects(object_type, filters=self._filters))

    def do_display_exchanges(self, line):
        """Display a list of DebugMessageExchanges: messages sharing a common message ID (subject to filters)"""
        object_type = 'DebugMessageExchange'
        if 'freq' in self._filters:
            self.display_single_line(object_type)
        else:
            self.print_response_dict(object_type, MessageViewer.display_db_objects(object_type, filters=self._filters))

    def do_display_session_details_by_agent(self, line):
        """Display message counts by sender/recipient; syntax is: display_session_details_by_agent <session_id>"""
        session_id_str = self.first_parameter(line)
        if session_id_str:
            try:
                session_id = int(session_id_str)
            except ValueError:
                print('Please enter a session ID')
                session_id = None
            if session_id:
                self.print_stats('Receiving Agent', MessageViewer.session_details_by_agent(session_id))
        else:
            print('Please enter a session ID')

    def do_display_session_details_by_topic(self, line):
        """Display message counts by topic; syntax is: display_session_details_by_topic <session_id>"""
        session_id_str = self.first_parameter(line)
        if session_id_str:
            try:
                session_id = int(session_id_str)
            except ValueError:
                print('Please enter a session ID')
                session_id = None
            if session_id:
                self.print_stats('Topic', MessageViewer.session_details_by_topic(session_id))
        else:
            print('Please enter a session ID')

    def do_display_exchange_details(self, line):
        """Display details for a single DebugMessageExchange; syntax is: display_exchange_details <message_id>"""
        message_id = self.first_parameter(line)
        if message_id:
            response = MessageViewer.message_exchange_details(message_id)
            if type(response) == str:
                # Got back an error/status message, so just print it
                print(response)
            else:
                if self._verbosity == 'high':
                    # At high verbosity, print the details in spread-out fashion.
                    if len(response['results']) > 0:
                        for msg in response['results']:
                            print()
                            print(jsonapi.dumps(msg, indent=4, sort_keys=2))
                    else:
                        print('No data in filtered output, consider relaxing filters')
                else:
                    # At lower verbosity, print the details as a table.
                    self.print_response_dict('DebugMessage', response)
        else:
            print('Please enter a message ID')

    def do_list_filters(self, line):
        """Display the database query filters that are currently in effect"""
        print(self._filters)

    def do_list_sessions(self, line):
        """Display a list of DebugSessions"""
        object_type = 'DebugSession'
        self.print_response_dict(object_type, MessageViewer.display_db_objects(object_type, filters=self._filters))

    def do_quit(self, line):
        """Quit this command-line MessageViewer."""
        exit()

    def do_set_filter(self, line):
        """
            Set a filter to a value; syntax is: set_filter <filter_name> <value>

            Some recognized filters include:
            . freq <n>: Use a single-line display, refreshing every <n> seconds (<n> can be floating point)
            . session_id <n>: Display Messages and Exchanges for the indicated debugging session ID only
            . results_only <n>: Display Messages and Exchanges only if they have a result
            . sender <agent_name>
            . recipient <agent_name>
            . device <device_name>
            . point <point_name>
            . topic <topic_name>: Matches all topics that start with the supplied <topic_name>
            . starttime <YYYY-MM-DD HH:MM:SS>: Matches rows with timestamps after the supplied time
            . endtime <YYYY-MM-DD HH:MM:SS>: Matches rows with timestamps before the supplied time
            . (etc. -- see the structures of DebugMessage and DebugMessageExchange)
        """
        filter_name = self.first_parameter(line)
        filter_value = self.second_parameter(line)
        if filter_name and filter_value:
            self._filters[filter_name] = filter_value
            print(MessageViewer.set_filters(self._filters))
        else:
            print('Please enter a filter name and a filter value')

    def do_clear_filter(self, line):
        """Clear a single filter value; syntax is: clear_filter <filter_name>"""
        filter_name = self.first_parameter(line)
        if filter_name:
            self._filters.pop(filter_name, None)
            print(MessageViewer.set_filters(self._filters))
        else:
            print('Please enter a filter name')

    def do_start_session(self, line):
        """Start a DebugSession"""
        print(MessageViewer.enable_message_debugging())

    def do_stop_session(self, line):
        """Stop the current DebugSession"""
        print(MessageViewer.disable_message_debugging())

    def do_start_streaming(self, line):
        """Start publishing DebugMessage strings to the monitor socket"""
        self.start_streaming()

    def start_streaming(self):
        self._streaming = True
        print(MessageViewer.start_streaming(filters=self._filters))

    def do_stop_streaming(self, line):
        """Stop publishing DebugMessage strings to the monitor socket"""
        print(MessageViewer.stop_streaming())
        self._streaming = False

    def do_delete_session(self, line):
        """Delete all database objects for the DebugSession with the given ID; syntax is: delete_session <session_id>"""
        session_id_str = self.first_parameter(line)
        if session_id_str:
            try:
                print(MessageViewer.delete_debugging_session(int(session_id_str)))
            except ValueError:
                print('Please enter an integer session ID')
        else:
            print('Please enter a session ID')

    def do_delete_database(self, line):
        """Delete the message debugger SQLite database (it will be re-created during the next DebugSession)"""
        print(MessageViewer.delete_debugging_db())

    def first_parameter(self, line):
        split_line = self.split_line(line)
        return split_line[0] if len(split_line) > 0 else None

    def second_parameter(self, line):
        split_line = self.split_line(line)
        return split_line[1] if len(split_line) > 1 else None

    def split_line(self, line):
        """Return a list of parameters after splitting <line> at space boundaries."""
        return shlex.split(line)            # Use shlex so that quoted substrings are preserved intact

    def display_single_line(self, object_type):
        """
            Query for objects named object_type, and display the most recent one on a single, refreshed line.

            The query is reissued every N seconds, where N is the value of the 'freq' filter.
            This runs in an endless loop until it's interrupted with a KeyboardInterrupt (ctrl-C).

        @param object_name: The name of the object type to query, either DebugMessage or DebugMessageExchange.
        """
        column_labels = self.column_labels(object_type)
        formatter = None
        try:
            while True:
                response = MessageViewer.display_db_objects(object_type, filters=self._filters)
                if type(response) == dict and len(response['results']) > 0:
                    data_rows, col_widths = self.data_rows_for_obj_list(response['results'],
                                                                        column_labels,
                                                                        formatter=formatter)
                    for data_row in data_rows:
                        if not formatter:
                            formatter = self.left_aligned_formatter(column_labels, col_widths)
                        # Write with no line feed so that the next line will overwrite it.
                        sys.stdout.write('\r'.rjust(80))
                        sys.stdout.write('{0} \r'.format(formatter.compose(data_row,
                                                                           include_newline=False,
                                                                           wrap_text=False)))
                        sys.stdout.flush()
                        time.sleep(float(self._filters['freq']))
                elif type(response) == str:
                    sys.stdout.write(str)
        except KeyboardInterrupt:
            print('Execution interrupted')

    def print_stats(self, stat_type, response):
        """
            Fill out a stats table, format it and print it.

            'response' is either a status/error message or a dictionary containing the json-style RPC response.
            The response's 'stats' element contains statistics by agent -- a dictionary of dictionaries of numbers.

        @param stat_type: Either 'Topic' or 'Receiving Agent'.
        @param response: The RPC response.
        """
        if type(response) == str:
            # Got back an error/status message, so just print it
            print(response)
        elif response['message_count'] == 0:
            print('No messages found for session')
        else:
            response_items = response['stats']
            if len(response_items) > 0:
                # Gather the data into rows and columns.
                # Collect a set of all column titles (the original data may have been sparse).
                all_columns_set = set()
                for row, inner_dict in response_items.items():
                    for column in inner_dict.keys():
                        all_columns_set.add(column)
                # Alpha-sort row and column labels.
                row_labels = sorted(response_items.keys())
                column_labels = sorted(list(all_columns_set))

                header_row = [stat_type]                                            # Leftmost column
                header_row.extend([(c or '(No Sender Name)') for c in column_labels])

                col_widths = {c: len(c) for c in header_row}
                #  Write data rows
                data_rows = []
                for r in row_labels:
                    if not self.exclude_by_agent(r):
                        data_row = [r or '(No {})'.format(stat_type)]                # Leftmost column
                        col_widths[stat_type] = max(col_widths[stat_type], len(data_row[0]))
                        for label in column_labels:
                            c = label or '(No Sender Name)'
                            cell_text = str(response_items[r][c] if c in response_items[r] else '-')
                            data_row.append(cell_text)
                            col_widths[c] = max(col_widths[c], len(cell_text))
                        data_rows.append(data_row)

                column_formats = [{'width': self.col_width(col_widths[header_row[0]]), 'margin': 2, 'alignment': LEFT}]
                for label in column_labels:
                    header = label or '(No Sender Name)'
                    column_formats.append({'width': self.col_width(col_widths[header]), 'margin': 2, 'alignment': RIGHT})
                formatter = self.formatter(header_row, column_formats)
                for row in data_rows:
                    sys.stdout.write(formatter.compose(row))
            else:
                print('No stats in filtered output, consider relaxing filters')

    def print_response_dict(self, object_type, response):
        """
            Fill out a table with one row per response element, format it and print it.

        @param object_type: The name of the type of data to be displayed, which defines the column layout.
        @param response: An RPC response, usually a dictionary containing a list of json-formatted objects.
        """
        if type(response) == str:
            # Got back an error/status message, so just print it
            print(response)
        else:
            response_list = response['results']
            if len(response_list) > 0:
                column_labels = self.column_labels(object_type)
                data_rows, col_widths = self.data_rows_for_obj_list(response_list, column_labels)
                formatter = self.left_aligned_formatter(column_labels, col_widths)
                for row in data_rows:
                    sys.stdout.write(formatter.compose(row))
            else:
                print('No data in filtered output, consider relaxing filters')

    def data_rows_for_obj_list(self, obj_list, column_labels, formatter=None):
        """
            Given a list of dictionaries, format the data into a list of data rows.

        @param obj_list: A list of objects, each of which is a dictionary of strings.
        @param column_labels: Labels to print as column headers, and also to index into the obj_list dictionaries.
        @param formatter: A TextFormatter instance. If null, it's not too late to adjust column widths.
        @return: A tuple of two lists: the data rows and their column widths.
        """
        col_widths = {c: len(c) for c in column_labels}
        data_rows = []
        for obj_dict in obj_list:
            if not self.exclude_by_agent(obj_dict):
                data_row = []
                for c in column_labels:
                    cell_text = str(obj_dict[c] or '-')
                    data_row.append(cell_text)
                    if not formatter:
                        # Columns haven't been formatted yet, so we can still adjust their widths.
                        col_widths[c] = max(col_widths[c], len(cell_text))
                data_rows.append(data_row)
        return data_rows, col_widths

    def left_aligned_formatter(self, column_labels, col_widths):
        """
            Create and return a TextFormatter for the indicated columns. Print the header row.

        @param column_labels: A list of column labels/headers.
        @param col_widths: A dictionary of column widths, indexed by column label/header names.
        @return: The TextFormatter instance.
        """
        column_formats = []
        for label in column_labels:
            column_formats.append({'width': self.col_width(col_widths[label]), 'margin': 2, 'alignment': LEFT})
        return self.formatter(column_labels, column_formats)

    def column_labels(self, object_type):
        """Return a list of column labels to display based on the object type and verbosity."""
        if self._verbosity == 'high':
            return ALL_COLUMNS[object_type]
        else:
            return INTERESTING_COLUMNS[object_type]

    @staticmethod
    def col_width(cwidth):
        """Return an adjusted column width that's within MIN and MAX parameters."""
        return max(min(cwidth, MAX_COL_WIDTH), MIN_COL_WIDTH)

    @staticmethod
    def formatter(column_labels, column_formats):
        """
            Create and return a TextFormatter for the indicated columns. Print the header row.

        @param column_labels: A list of column labels/headers.
        @param column_formats: A list of column formats defining widths, alignments, etc.
        @return: The TextFormatter instance.
        """
        formatter = TextFormatter(column_formats)
        sys.stdout.write(formatter.compose(column_labels))
        return formatter

    def exclude_by_agent(self, response):
        """Return whether the dictionary contains a 'sender' or 'recipient' property that should be excluded."""
        if self._verbosity == 'high':
            return False                # At high verbosity, report 'em all
        if 'sender' in response and response['sender'] in EXCLUDED_SENDERS:
            return True
        if 'recipient' in response and response['recipient'] in EXCLUDED_RECIPIENTS:
            return True
        return False

    def initialize_monitor_socket(self):
        """Initialize and return the monitor socket used by the MessageDebuggerAgent to stream messages."""
        monitor_path = os.path.expandvars('$VOLTTRON_HOME/run/messageviewer')
        monitor_socket = zmq.Context().socket(zmq.SUB)
        monitor_socket_address = 'ipc://{}'.format('@' if sys.platform.startswith('linux') else '') + monitor_path
        monitor_socket.bind(monitor_socket_address)
        monitor_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        _log.debug('Subscribing to monitor socket {}'.format(monitor_socket_address))
        return monitor_socket


class MessageViewer(object):
    """
        View MessageDebugger messages by issuing RPC calls to MessageDebuggerAgent.

        MessageViewer is almost entirely stateless. It consists of a set of class methods,
        each of which issues a single RPC call. The only state is the connection to the
        MessageDebuggerAgent. Once it has been established, it's cached and re-used throughout
        the lifetime of the process.

        MessageViewer methods can be called directly if desired.
        MessageViewerCmd provides an interactive UI for them.

        Sample MessageViewer commands:

            MessageViewer.display_message_stream()
            MessageViewer.enable_message_streaming(filters={})
            MessageViewer.disable_message_streaming()

            MessageViewer.display_db_objects('DebugMessage', filters={'freq': '1'})
            MessageViewer.display_db_objects('DebugMessageExchange')
            MessageViewer.display_db_objects('DebugMessageExchange', filters={'freq': '1'})
            MessageViewer.display_db_objects('DebugMessageExchange', filters={'sender': 'test.agent',
                                                                              'recipient': 'platform.driver'})
            MessageViewer.display_db_objects('DebugMessageExchange', filters={'device': 'chargepoint1',
                                                                              'point': 'stationMacAddr'})
            MessageViewer.display_db_objects('DebugMessageExchange', filters={'freq': '1',
                                                                              'results_only': '1',
                                                                              'device': 'chargepoint1',
                                                                              'sender': 'test.agent'})
            MessageViewer.display_db_objects('DebugMessage', filters={'session_id': '1'})
            MessageViewer.display_db_objects('DebugMessage', filters={'topic': 'heartbeat'})
            MessageViewer.display_db_objects('DebugMessage', filters={'starttime': '2017-03-06 15:57:00',
                                                                      'endtime': '2017-03-06 15:57:50'})
            MessageViewer.display_db_objects('DebugMessageExchange', filters={'session_id': '1'})
            MessageViewer.display_db_objects('DebugSession')

            MessageViewer.session_details_by_agent(38)
            MessageViewer.session_details_by_topic(38)
            MessageViewer.message_exchange_details(8950737996372725552.272119477)

            MessageViewer.set_verbosity('high')
            MessageViewer.enable_message_debugging()
            MessageViewer.disable_message_debugging()
            MessageViewer.delete_debugging_session(22)
            MessageViewer.delete_debugging_db()
    """

    @classmethod
    def display_message_stream(cls):
        """Display the stream of DebugMessage strings as they arrive on the monitor socket."""
        monitor_path = os.path.expandvars('$VOLTTRON_HOME/run/messageviewer')
        monitor_socket = zmq.Context().socket(zmq.SUB)
        monitor_socket_address = 'ipc://{}'.format('@' if sys.platform.startswith('linux') else '') + monitor_path
        monitor_socket.bind(monitor_socket_address)
        monitor_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        _log.debug('Subscribing to monitor socket {}'.format(monitor_socket_address))
        try:
            while True:
                json_string = monitor_socket.recv()
                print(jsonapi.loads(json_string))
        except KeyboardInterrupt:
            _log.debug('Execution interrupted')

    @classmethod
    def start_streaming(cls, filters=None):
        """Start publishing DebugMessage strings to the monitor socket."""
        return cls.issue_debugger_request('enable_message_streaming', filters=filters)

    @classmethod
    def stop_streaming(cls):
        """Stop publishing DebugMessage strings to the monitor socket."""
        return cls.issue_debugger_request('disable_message_streaming')

    @classmethod
    def display_db_objects(cls, db_object_name, filters=None):
        return cls.issue_debugger_request('execute_db_query', db_object_name, filters=filters)

    @classmethod
    def session_details_by_agent(cls, session_id):
        return cls.issue_debugger_request('session_details_by_agent', session_id)

    @classmethod
    def session_details_by_topic(cls, session_id):
        return cls.issue_debugger_request('session_details_by_topic', session_id)

    @classmethod
    def message_exchange_details(cls, message_id):
        return cls.issue_debugger_request('message_exchange_details', message_id)

    @classmethod
    def set_verbosity(cls, verbosity_level):
        return cls.issue_debugger_request('set_verbosity', verbosity_level)

    @classmethod
    def set_filters(cls, filters):
        return cls.issue_debugger_request('set_filters', filters)

    @classmethod
    def enable_message_debugging(cls):
        return cls.issue_debugger_request('enable_message_debugging')

    @classmethod
    def disable_message_debugging(cls):
        return cls.issue_debugger_request('disable_message_debugging')

    @classmethod
    def delete_debugging_session(cls, session_id):
        return cls.issue_debugger_request('delete_debugging_session', session_id)

    @classmethod
    def delete_debugging_db(cls):
        return cls.issue_debugger_request('delete_debugging_db')

    @classmethod
    def issue_debugger_request(cls, method_name, *args, **kwargs):
        _log.debug('Sending {0} to message debugger'.format(method_name))
        global debugger_connection
        if not debugger_connection:
            debugger_connection = ViewerConnection()
        return debugger_connection.call(method_name, *args, **kwargs)


class ViewerConnection(object):
    """
        This is a copy of volttron.platform.control.ControlConnection.
        ControlConnection could not be used directly because it has a hard-coded
        identity that would conflict if it were re-used by MessageViewer.

        This connection/agent authenticates using the platform's credentials.
    """

    def __init__(self):
        self.address = get_address()
        self.peer = 'messagedebugger'
        self._server = Agent(identity='message.viewer',
                             address=self.address,
                             publickey=KeyStore().public,
                             secretkey=KeyStore().secret,
                             serverkey=KnownHostsStore().serverkey(self.address),
                             enable_store=False,
                             enable_channel=True)
        self._greenlet = None

    @property
    def server(self):
        if self._greenlet is None:
            event = gevent.event.Event()
            self._greenlet = gevent.spawn(self._server.core.run, event)
            event.wait()
        return self._server

    def call(self, method, *args, **kwargs):
        return self.server.vip.rpc.call(
            self.peer, method, *args, **kwargs).get()

    def call_no_get(self, method, *args, **kwargs):
        return self.server.vip.rpc.call(
            self.peer, method, *args, **kwargs)

    def notify(self, method, *args, **kwargs):
        return self.server.vip.rpc.notify(
            self.peer, method, *args, **kwargs)

    def kill(self, *args, **kwargs):
        if self._greenlet is not None:
            self._greenlet.kill(*args, **kwargs)


LEFT, CENTER, RIGHT = list(range(3))


class TextFormatter(object):
    """
        Formats text into columns.

        Constructor takes a list of dictionaries that each specify the
        properties for a column. Dictionary entries can be:

           'width'     : the width within which the text will be wrapped
           'alignment' : LEFT | CENTER | RIGHT
           'margin'    : number of space characters to prefix in front of column

        The compose() method takes a list of strings and returns a formatted
        string consisting of each string wrapped within its respective column.

        Example:
            import textformatter

            formatter = textformatter.TextFormatter(
                (
                    {'width': 10},
                    {'width': 12, 'margin': 4},
                    {'width': 20, 'margin': 8, 'alignment': textformatter.RIGHT},
                )
            )

            print formatter.compose(
                (
                    "A rather short paragraph",
                    "Here is a paragraph containing a veryveryverylongwordindeed.",
                    "And now for something on the right-hand side.",
                )
            )

        gives:

            A rather      Here is a                    And now for
            short         paragraph               something on the
            paragraph     containing a            right-hand side.
                          veryveryvery
                          longwordinde
                          ed.
    """

    class Column(object):

        def __init__(self, width=75, alignment=RIGHT, margin=1, fill=1, pad=1):
            self.width = width
            self.alignment = alignment
            self.margin = margin
            self.fill = fill
            self.pad = pad
            self.lines = []

        def align(self, line):
            if self.alignment == CENTER:
                return line.center(self.width)
            elif self.alignment == RIGHT:
                return line.rjust(self.width)
            else:
                return line.ljust(self.width) if self.pad else line

        def wrap(self, text):
            self.lines = []
            words = []
            if self.fill:
                for word in text.split():
                    wordlen = len(word)
                    if wordlen <= self.width:
                        words.append(word)
                    else:
                        for i in range(0, wordlen, self.width):
                            words.append(word[i: i + self.width])
            else:
                for line in text.split('\n'):
                    for word in line.split():
                        for i in range(0, len(word), self.width):
                            words.append(word[i: i + self.width])
                    words.append('\n')
                if words[-1] == '\n':
                    words.pop()             # remove trailing newline

            if words:
                current = words.pop(0)
                for word in words:
                    increment = 1 + len(word)
                    if word == '\n':
                        self.lines.append(self.align(current))
                        current = ''
                    elif len(current) + increment > self.width:
                        self.lines.append(self.align(current))
                        current = word
                    else:
                        current = current + ' ' + word if current else word
                if current:
                    self.lines.append(self.align(current))

        def truncate(self, text):
            self.lines = [self.align(text[:min(len(text), self.width)])] if text else []

        def getline(self, index):
            if index < len(self.lines):
                return ' ' * self.margin + self.lines[index]
            else:
                return ' ' * (self.margin + self.width) if self.pad else ''

        def numlines(self):
            return len(self.lines)

    def __init__(self, colspeclist):
        self.columns = [TextFormatter.Column(*(), **colspec) for colspec in colspeclist]

    def compose(self, textlist, include_newline=True, wrap_text=True):
        numlines = 0
        textlist = list(textlist)
        if len(textlist) != len(self.columns):
            raise IndexError("Number of text items {} does not match columns {}".format(len(textlist), len(self.columns)))
        for text, column in map(None, textlist, self.columns):
            column.wrap(text) if wrap_text else column.truncate(text)
            numlines = max(numlines, column.numlines())
        complines = [''] * numlines
        for ln in range(numlines):
            for column in self.columns:
                complines[ln] = complines[ln] + column.getline(ln)
        return '\n'.join(complines) + '\n' if include_newline else ''.join(complines)


def main(argv=sys.argv):
    # When the module is invoked directly by default, start the MessageViewerCmd command-line UI.
    # Alternatively, at startup we could have invoked MessageViewer class methods directly, e.g.
    #
    #   MessageViewer.startSession()
    #   MessageViewer.display_message_stream()
    #
    # or
    #
    #   MessageViewer.startSession()
    #   MessageViewer.display_db_objects('DebugMessage', filters={'topic': 'heartbeat'})

    MessageViewerCmd().startup()


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    # except KeyboardInterrupt:
    #     pass
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')
