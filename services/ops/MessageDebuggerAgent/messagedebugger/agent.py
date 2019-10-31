# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
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
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
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
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

import datetime
from dateutil.parser import parse
import gevent
import logging
import os
import sys
import time
import zmq
from zmq.green import Again

from sqlalchemy import create_engine, desc
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from volttron.platform.agent import utils
from volttron.platform import jsonapi
from volttron.platform.control import ControlConnection, KnownHostsStore, KeyStore
from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.vip.router import ERROR, UNROUTABLE, INCOMING, OUTGOING

ORMBase = declarative_base()

utils.setup_logging()
_log = logging.getLogger(os.path.basename(sys.argv[0]) if __name__ == '__main__' else __name__)
__version__ = '1.0'

VERBOSITY_LOW = 'low'
VERBOSITY_MEDIUM = 'medium'
VERBOSITY_HIGH = 'high'
_verbosity = VERBOSITY_LOW

MAX_MESSAGES_AT_LOW_VERBOSITY = 1000


class MessageDebuggerAgent(Agent):
    """
        The `pyclass:MessageDebuggerAgent` monitors all routed messages.

        When message debugging is enabled, Router publishes all messages to a (zmq) socket.
        This agent:
            . Subscribes to that queue
            . Transfers each message's contents to an instance of DebugMessage
            . Writes each DebugMessage to a SQLite database
            . Re-publishes each DebugMessage on another socket
            . Aggregates information for messages with the same ID into a single DebugMessageExchange

        A consumer (MessageViewer) can track the DebugMessages in real time by subscribing
        to the second socket, or it can analyze message history by querying the database.

        This agent is also responsible for executing SQLite database queries on behalf of the MessageViewer
        (or any other interested consumer of the data).
    """

    _debug_session = None
    _db_session = None
    _router_socket = None
    _monitor_socket = None
    _streaming_messages = False
    _filters = {}

    def __init__(self, config_path, **kwargs):
        super(self.__class__, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.default_config = dict(router_path=config.get('router_path', '$VOLTTRON_HOME/run/messagedebug'),
                                   monitor_path=config.get('monitor_path', '$VOLTTRON_HOME/run/messageviewer'),
                                   db_path=config.get('db_path', '$VOLTTRON_HOME/data/volttron_messages.sqlite'),
                                   agentid=config.get('agentid', 'messagedebugger'))
        self.current_config = None
        _log.debug('Initializing agent config, default config = {}'.format(self.default_config))
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")

    def configure_main(self, config_name, action, contents):
        self.current_config = self.default_config.copy()
        self.current_config.update(contents)

    @Core.receiver("onstart")
    def start_agent(self, sender, **kwargs):
        self.core.spawn(self.listen_for_messages)

    def listen_for_messages(self):
        """
            Subscribe to a zmq socket that publishes messages as they are routed.

            Re-publish each DebugMessage for optional MessageViewer consumption.
            Write each message to a SQLite db.
        """
        self.enable_message_debugging()             # Always enable message debugging when the agent starts.
        router_socket = self.router_socket()
        start_time = datetime.datetime.now()
        waiting_for_test_msg = True
        test_message_sent = False

        _log.debug('Listening for messages on router socket')
        while True:
            # Receive routed messages on the subscribed socket and process them.
            try:
                gevent.sleep(0)         # Sleep between messages so that other gevents can gain control of the process

                routed_message = router_socket.recv_pyobj(zmq.NOBLOCK)
                debug_message = DebugMessage(routed_message, self._debug_session.rowid if self._debug_session else 0)

                if not test_message_sent:
                    # First time in. Send a test RPC to validate that routed messages are arriving on the socket.
                    _log.debug('Sending a test RPC call')
                    self.vip.rpc.call(self.agent_id(), 'test_message')
                    test_message_sent = True

                if waiting_for_test_msg:
                    waiting_for_test_msg = self.check_for_test_msg(debug_message, start_time)

                # Un-comment the following line to watch the message stream flow by in the log...
                # _log.debug('{}'.format(debug_message))

                if self._debug_session:
                    self.store_debug_message(debug_message)

                if self._streaming_messages and self.allowed_by_filters(debug_message, ignore_session_id=True):
                    # Re-publish the DebugMessage (as json) for MessageViewer real-time consumption
                    self.monitor_socket().send(jsonapi.dumps(debug_message.as_json_compatible_object()))

            except Again:
                if waiting_for_test_msg:
                    waiting_for_test_msg = self.check_for_test_msg(None, start_time)
                continue

    def store_debug_message(self, debug_message):
        """
            A DebugMessage has arrived. Store it in the SQLite database.

        @param debug_message: A DebugMessage instance.
        """
        self.db_session().add(debug_message)
        if self._debug_session:
            self._debug_session.num_messages += 1
        if debug_message.request_id:
            # Update the DebugMessageExchange with this request ID; create one if necessary
            query = self.db_session().query(DebugMessageExchange).filter_by(request_id=debug_message.request_id)
            try:
                exch = query.one_or_none()
                exch.update_for_message(debug_message)
            except:
                exch = DebugMessageExchange(debug_message, self._debug_session.rowid if self._debug_session else 0)
                self.db_session().add(exch)
        try:
            self.db_session().commit()
        except Exception as err:
            pass

    def allowed_by_filters(self, msg, ignore_session_id=False):
        """
            Return whether debug_message is allowed (i.e., not excluded) by the current filters.

            This is called while streaming messages to the monitor socket.

        @param msg: The current DebugMessage.
        @param ignore_session_id: If this is True, don't exclude the message solely because of its session ID.
        @return: A Boolean
        """
        for prop in self._filters:
            if prop == 'freq':
                pass        # This filter has a different meaning entirely
            elif prop == 'starttime':
                parsed_starttime = parse(self._filters[prop], ignoretz=True, fuzzy=True)
                parsed_timestamp = parse(str(msg.timestamp), ignoretz=True, fuzzy=True)
                if parsed_timestamp < parsed_starttime:
                    # Special-case filter: Filter out messages timestamped before the filter value
                    return False
            elif prop == 'endtime':
                parsed_endtime = parse(self._filters[prop], ignoretz=True, fuzzy=True)
                parsed_timestamp = parse(str(msg.timestamp), ignoretz=True, fuzzy=True)
                if parsed_timestamp > parsed_endtime:
                    # Special-case filter: Filter out messages timestamped after the filter value
                    return False
            elif prop == 'topic' and not str(getattr(msg, prop)).startswith(self._filters[prop]):
                # Special-case filter: The filter value can be just the prefix portion of the message's topic
                return False
            elif prop == 'results_only' and msg.result in ['', 'None']:
                # Special-case filter: Filter out messages that lack a 'result' value
                return False
            elif prop in msg.filtered_properties():
                # Main case: Do a string comparison between the filter value and a DebugMessage property
                if str(getattr(msg, prop)) != self._filters[prop]:
                    if not (ignore_session_id and prop == 'session_id'):
                        return False
        return True

    @RPC.export
    def test_message(self):
        """Receive a test RPC while validating that routed messages are arriving on the monitor_socket."""
        _log.debug('Test message received')

    def check_for_test_msg(self, msg, test_msg_send_time):
        """
            Verify that a response to the agent's test RPC message arrives on monitor_socket within 15 seconds.

            This is also called periodically with msg=None to detect whether no messages arriving on the socket.

        @param msg: The current DebugMessage.
        @param test_msg_send_time: The time that the test RPC message was sent.
        @return: A Boolean indicating whether to keep watching for the test RPC to arrive on monitor_socket.
        """
        if msg and msg.sender == self.agent_id() and msg.recipient == self.agent_id() and msg.direction == 'outgoing':
            _log.debug('Test RPC response appeared on monitor socket.')
            return False
        elif datetime.datetime.now() > test_msg_send_time + datetime.timedelta(seconds=15):
            _log.warning('No test RPC response on monitor socket. Was volttron started with --msgdebug?')
            return False
        else:
            return True

    # TODO check out the id here
    @RPC.export
    def execute_db_query(self, db_object_name, filters=None):
        """
            Execute a query and return the results.

        @param db_object_name: The name of a database object: 'DebugMessage', etc.
        @param filters: Filters that should be applied during the database query.
        @return: Results of the query, in json-serializable format.
        """
        global _verbosity
        _log.debug('Issuing {} query, filters={}'.format(db_object_name, filters))
        self._filters = filters if filters else {}  # This also affects filtering while streaming to the monitor socket
        if _verbosity == VERBOSITY_LOW:
            count = self._filtered_query(db_object_name).count()
            if count > MAX_MESSAGES_AT_LOW_VERBOSITY:
                return '{} results returned. Tighten filtering or raise verbosity to see message details.'.format(count)

        query_results = self._filtered_query(db_object_name).all()

        _log.error([obj.as_json_compatible_object() for obj in query_results])

        if len(query_results) == 0:
            return 'No query results'
        else:
            return {'results': [obj.as_json_compatible_object() for obj in query_results]}

    def _filtered_query(self, db_object_name):
        """Set up a filtered database query."""
        db_object = globals()[db_object_name]
        query_results = self.db_session().query(db_object)
        for key, value in self._filters.items():
            if key == 'starttime' and hasattr(db_object, 'timestamp'):      # for DebugMessage
                query_results = query_results.filter(getattr(db_object, 'timestamp') >= value)
            if key == 'starttime' and hasattr(db_object, 'sender_time'):    # for DebugMessageExchange
                query_results = query_results.filter(getattr(db_object, 'sender_time') >= value)
            elif key == 'endtime' and hasattr(db_object, 'timestamp'):      # for DebugMessage
                query_results = query_results.filter(getattr(db_object, 'timestamp') <= value)
            elif key == 'endtime' and hasattr(db_object, 'sender_time'):    # for DebugMessageExchange
                query_results = query_results.filter(getattr(db_object, 'sender_time') <= value)
            elif hasattr(db_object, key):
                if key == 'topic':
                    # Match topic prefixes, too
                    query_results = query_results.filter(getattr(db_object, key).startswith(value))
                else:
                    query_results = query_results.filter(getattr(db_object, key) == value)

        if 'results_only' in self._filters:
            query_results = query_results.filter(db_object.result != '')
            query_results = query_results.filter(db_object.result != 'None')
        if 'freq' in self._filters and db_object_name != 'DebugSession':
            query_results = query_results.order_by(desc(db_object.rowid)).limit(1)
        return query_results

    @RPC.export
    def session_details_by_agent(self, session_id):
        """
            Report details by agent for a single DebugSession (multiple DebugMessages).

        @param session_id: The id of a DebugSession
        @return: Resulting details/statistics.
        """
        _log.debug('Reporting details by agent for DebugSession {}'.format(session_id))
        msg_db_object = globals()['DebugMessage']
        query_results = self.db_session().query(msg_db_object).filter(msg_db_object.session_id == session_id).all()
        stats = {}              # A matrix of message counts by sender and recipient agent
        for msg in query_results:
            if self.allowed_by_filters(msg):
                stats[msg.recipient] = stats[msg.recipient] if msg.recipient in stats else {}
                stats[msg.recipient][msg.sender] = stats[msg.recipient][msg.sender] + 1 \
                    if msg.sender in stats[msg.recipient] \
                    else 1
        return {
            'message_count': len(query_results),
            'stats': stats
        }

    @RPC.export
    def session_details_by_topic(self, session_id):
        """
            Report details by topic for a single DebugSession (multiple DebugMessages).

        @param session_id: The id of a DebugSession
        @return: Resulting details/statistics.
        """
        _log.debug('Reporting details by topic for DebugSession {}'.format(session_id))
        msg_db_object = globals()['DebugMessage']
        query_results = self.db_session().query(msg_db_object).filter(msg_db_object.session_id == session_id).all()
        stats = {}              # A matrix of message counts by sending agent and topic
        for msg in query_results:
            if self.allowed_by_filters(msg):
                stats[msg.topic] = stats[msg.topic] if msg.topic in stats else {}
                stats[msg.topic][msg.sender] = stats[msg.topic][msg.sender] + 1 \
                    if msg.sender in stats[msg.topic] \
                    else 1
        return {
            'message_count': len(query_results),
            'stats': stats
        }

    @RPC.export
    def message_exchange_details(self, request_id):
        """
            Report details for a single DebugMessageExchange (multiple DebugMessages).

            Why isn't there also a 'message_details()' RPC call? Because a DebugMessage can't
            easily be identified uniquely; multiple DebugMessages share a common ID.
            The JSON data structure returned by message_exchange_details() provides the most
            detailed information about individual DebugMessages.

        @param request_id: The request ID shared by messages in the DebugMessageExchange.
        @return: A JSON data structure of information about a list of DebugMessages.
        """
        _log.debug('Reporting details for DebugMessageExchange {}'.format(request_id))
        msg_db_object = globals()['DebugMessage']
        query_results = self.db_session().query(msg_db_object).filter(msg_db_object.request_id == request_id).all()
        _log.error(query_results)
        if len(query_results) == 0:
            return 'No messages found for request ID {}'.format(request_id)
        else:
            return {'results': [msg.as_json_compatible_object() for msg in query_results]}

    @RPC.export
    def enable_message_debugging(self):
        """Start a DebugSession. Return a string indicating command success."""
        _log.debug('Starting debug session')
        if self._debug_session:
            self._debug_session.end_time = datetime.datetime.now()      # A session is already active. End it.
        sess = DebugSession()
        self.db_session().add(sess)
        self.db_session().commit()
        self._debug_session = sess
        _log.debug('{0}'.format(sess))
        return 'Message debugger session {} started'.format(self._debug_session.rowid)

    @RPC.export
    def disable_message_debugging(self):
        """End the current DebugSession. Return a string indicating command success or failure."""
        _log.debug('Stopping debug session')
        if self._debug_session:
            session_id = self._debug_session.rowid
            # Set the session's end time and remove it from memory.
            self._debug_session.end_time = datetime.datetime.now()
            self.db_session().commit()
            self._debug_session = None
            result = 'Message debugger session {} stopped'.format(session_id)
        else:
            result = 'Unable to stop debug session: No session active'
        return result

    @RPC.export
    def enable_message_streaming(self, filters=None):
        """
            Start publishing a stream of DebugMessages on monitor_socket.

        @param filters: Filters that should be applied when publishing messages to the socket.
        @return: A string indicating command success.
        """
        _log.debug('Starting message streaming')
        self._filters = filters if filters else {}
        self._streaming_messages = True
        return 'Streaming debug messages'

    @RPC.export
    def disable_message_streaming(self):
        """Stop publishing a stream of DebugMessages on monitor_socket. Return a string indicating command success."""
        _log.debug('Stop message streaming')
        self._streaming_messages = False
        return 'Stopped streaming debug messages'

    @RPC.export
    def delete_debugging_db(self):
        """Delete the SQLite database. Return a string indicating command success or failure."""
        _log.debug('Deleting debug database')
        if os.path.exists(self.vip_config_get('db_path')):
            self._debug_session = None                  # End the current debug session
            self._db_session = None
            os.remove(self.vip_config_get('db_path'))
            result = 'Database deleted'
        else:
            result = 'Unable to delete: No database file found'
        return result

    @RPC.export
    def delete_debugging_session(self, session_id):
        """
            Delete the DebugSession with session_id, along with all of its database objects.

        @param session_id: The ID of the DebugSession to be deleted (an ordinal number, in string format).
        @return: A string indicating command success.
        """

        def delete_rows_with_value(table_name, column_name, value):
            db_object = globals()[table_name]
            query_object = self.db_session().query(db_object).filter(getattr(db_object, column_name) == value)
            query_object.delete(synchronize_session=False)

        _log.debug('Deleting debug session {0} from database'.format(session_id))
        if self._debug_session and self._debug_session.rowid == session_id:
            self._debug_session = None          # The session to be deleted is active. End it.
        delete_rows_with_value('DebugSession', 'rowid', session_id)
        delete_rows_with_value('DebugMessage', 'session_id', session_id)
        delete_rows_with_value('DebugMessageExchange', 'session_id', session_id)
        self.db_session().commit()
        return 'Deleted debug session {}'.format(session_id)

    @RPC.export
    def set_verbosity(self, verbosity_level):
        """Set the verbosity to use in responses to RPC calls and while streaming to the socket."""
        _log.debug('Setting verbosity to {0}'.format(verbosity_level))
        global _verbosity
        if verbosity_level in (VERBOSITY_LOW, VERBOSITY_MEDIUM, VERBOSITY_HIGH):
            _verbosity = verbosity_level
            return 'Set verbosity to {}'.format(verbosity_level)
        else:
            return 'Invalid verbosity choice {}; valid choices are {}'.format(verbosity_level, [VERBOSITY_LOW,
                                                                                                VERBOSITY_MEDIUM,
                                                                                                VERBOSITY_HIGH])
    @RPC.export
    def set_filters(self, filters):
        """Set the filters to use in responses to RPC calls and while streaming to the socket."""
        # This gets set as a side effect of other RPC calls; it is not itself an exported RPC call.
        _log.debug('Setting filters to {}'.format(filters))
        self._filters = filters
        return 'Set filters to {}'.format(filters)

    def router_socket(self):
        """Return the zmq socket that subscribes to router messages. Initialize the connection if first time in."""
        if not self._router_socket:
            ipc = 'ipc://{}'.format('@' if sys.platform.startswith('linux') else '')
            router_socket_address = ipc + self.vip_config_get('router_path')
            self._router_socket = zmq.Context().socket(zmq.SUB)
            self._router_socket.setsockopt_string(zmq.SUBSCRIBE, "")
            self._router_socket.set_hwm(100)            # Start dropping messages if queue backlog exceeds 100
            self._router_socket.bind(router_socket_address)
            _log.debug('Subscribing to router socket {}'.format(router_socket_address))
        return self._router_socket

    def monitor_socket(self):
        """Return the zmq socket that re-publishes DebugMessages. Initialize the connection if first time in."""
        if not self._monitor_socket:
            ipc = 'ipc://{}'.format('@' if sys.platform.startswith('linux') else '')
            monitor_socket_address = ipc + self.vip_config_get('monitor_path')
            self._monitor_socket = zmq.Context().socket(zmq.PUB)
            self._monitor_socket.set_hwm(100)           # Start dropping messages if queue backlog exceeds 100
            self._monitor_socket.connect(monitor_socket_address)
            _log.debug('Publishing to monitor socket {}'.format(monitor_socket_address))
        return self._monitor_socket

    def db_session(self):
        """Return the SQLite database session. Initialize the session if first time in."""
        if not self._db_session:
            # First time: create a SQLAlchemy engine and session.
            database_path = self.vip_config_get('db_path')
            database_dir = os.path.dirname(database_path)
            if not os.path.exists(database_dir):
                _log.debug('Creating sqlite database directory {}'.format(database_dir))
                os.makedirs(database_dir)
            engine_path = 'sqlite:///' + database_path
            _log.debug('Connecting to sqlite database {}'.format(engine_path))
            engine = create_engine(engine_path).connect()
            ORMBase.metadata.create_all(engine)
            self._db_session = sessionmaker(bind=engine)()
            # @todo Detect and report a data model structure change; allow db deletion if needed
        return self._db_session

    def agent_id(self):
        """Return the ID of this agent, including the 'platform' prefix."""
        return self.vip_config_get('agentid')

    def loopback(self):
        """Return the ID of the transient connection used by this agent to send an RPC to itself."""
        return self.agent_id() + '.loopback_rpc'

    def vip_config_get(self, var_name):
        """
            Fetch a parameter from this process's vip config.

        @param var_name: The parameter's name.
        @return: The parameter's value.
        """
        config_var = os.path.expanduser(self.vip.config.get('config')[var_name])
        config_var = os.path.expandvars(config_var)
        return config_var


def format_attribute(att, label=None):
    """
        Return a string representation of an attribute, with a preceding label, if it is non-null.

    @param att: The attribute to be returned in a string format.
    @param label: A string to prefix as a label. If None, return the attribute string with no other formatting.
    @return: The resulting string.
    """
    global _verbosity
    if label is None:
        attribute_string = str(att) if att else ''
    else:
        fmt_label = '{}:'.format(label) if label else ''
        if _verbosity == VERBOSITY_HIGH:
            attribute_string = '{}{}; '.format(fmt_label, att) if att else '{}; '.format(fmt_label)
        else:
            attribute_string = '{}{}; '.format(fmt_label, att) if att else ''
    return attribute_string


def format_time(date_time, label=None, verbosity=None):
    """
        Return a string representation of a DateTime attribute, with a preceding label, if it is non-null.

    @param date_time: The DateTime to be returned in a string format.
    @param label: A string to prefix as a label. If None, return the attribute string with no other formatting.
    @param verbosity: Override the global verbosity with this setting while formatting this string.
    @return: The resulting string.
    """
    global _verbosity
    vbsty = verbosity or _verbosity
    if date_time:
        fmt_date_time = str(date_time) if vbsty == VERBOSITY_HIGH else time.strftime('%X', date_time.timetuple())
    else:
        fmt_date_time = ''
    if label is None:
        date_time_string = fmt_date_time if fmt_date_time else ''
    else:
        fmt_label = '{}:'.format(label) if label else ''
        if fmt_date_time:
            date_time_string = '{}{}; '.format(fmt_label, fmt_date_time)
        else:
            date_time_string = '{}; '.format(fmt_label) if (fmt_label and vbsty == VERBOSITY_HIGH) else ''
    return date_time_string


class DebugMessage(ORMBase):
    """
        Model a VOLTTRON message, captured during routing, as a SQL Alchemy / SQLite object.
    """

    __tablename__ = 'DebugMessage'

    rowid = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('DebugMessageExchange.rowid'))
    parent = relationship("DebugMessageExchange", back_populates="children")
    session_id = Column(Integer)

    timestamp = Column(DateTime)
    framecount = Column(Integer)
    direction = Column(String)
    sender = Column(String)             # Frame 0
    recipient = Column(String)          # Frame 1
    vip_signature = Column(String)      # Frame 2
    user_id = Column(String)            # Frame 3
    request_id = Column(String)         # Frame 4
    subsystem = Column(String)          # Frame 5
    data = Column(String)               # Frame 6
    frame7 = Column(String)
    frame8 = Column(String)
    frame9 = Column(String)
    method = Column(String)
    params = Column(String)
    topic = Column(String)
    headers = Column(String)
    message = Column(String)
    message_value = Column(String)
    device = Column(String)
    point = Column(String)
    point_value = Column(String)
    result = Column(String)
    message_size = Column(Integer)

    attribute_names = [
        'timestamp',
        'session_id',
        'sender', 'recipient',
        'subsystem', 'direction',
        'request_id',
        'vip_signature',
        'user_id',
        'method',
        'topic',
        'message', 'message_value', 'message_size',
        'headers',
        'device',
        'point', 'point_value',
        'result',
        'params', 'data',
        'frame7', 'frame8', 'frame9']

    attribute_names_short_list = [
        'timestamp',
        'session_id',
        'sender', 'recipient',
        'subsystem', 'direction',
        'request_id',
        'method',
        'topic',
        'message_value', 'message_size',
        'device',
        'point', 'point_value',
        'frame7', 'frame8', 'frame9']

    # These are values of the message's "issue topic" in main.py
    status_names = {
        ERROR: 'error',
        UNROUTABLE: 'unroutable',
        INCOMING: 'incoming',
        OUTGOING: 'outgoing'}

    def __init__(self, msg_elements, session_id):
        """Transform a routed message string into a DebugMessage instance."""
        self.session_id = session_id
        self.timestamp = datetime.datetime.now()
        self.framecount = len(msg_elements)
        self.direction = self.status_names[msg_elements[0]]
        self.sender = bytes(msg_elements[1])
        self.recipient = bytes(msg_elements[2])
        self.vip_signature = bytes(msg_elements[3])
        self.user_id = bytes(msg_elements[4])
        self.request_id = bytes(msg_elements[5])
        self.subsystem = bytes(msg_elements[6])
        self.data = bytes(msg_elements[7])
        self.frame7 = bytes(msg_elements[8]) if len(msg_elements) > 8 else ''
        self.frame8 = bytes(msg_elements[9]) if len(msg_elements) > 9 else ''
        self.frame9 = bytes(msg_elements[10]) if len(msg_elements) > 10 else ''
        self.method = ''
        self.params = ''
        self.topic = self.frame7        # MasterDriverAgent device topics go in routed message's frame 7
        self.headers = ''
        self.message = ''
        self.message_value = ''
        self.device = ''
        self.point = ''
        self.point_value = ''
        self.result = ''
        self.message_size = sum((len(frame) if type(frame) == str else 4) for frame in msg_elements)
        self.extract_data_fields()

    def extract_data_fields(self):
        try:
            data_dict = jsonapi.loads(str(self.data))
        except ValueError:
            data_dict = None
        if type(data_dict) == dict:
            if 'method' in data_dict:
                self.method = str(data_dict.get('method'))
            if 'result' in data_dict:
                self.result = str(data_dict.get('result'))
            if 'params' in data_dict:
                self.params = str(data_dict.get('params'))
                params = data_dict.get('params')
                if type(params) == dict:
                    if 'topic' in params:
                        self.topic = str(params.get('topic'))
                    if 'headers' in params:
                        self.headers = str(params.get('headers'))
                    if 'message' in params:
                        self.message = str(params.get('message'))
                        message_list = params.get('message')
                        message_val = message_list[0] \
                            if (message_list and type(message_list) == list and len(message_list) > 0) \
                            else ''
                        if message_val:
                            self.message_value = str(message_val)
                elif type(params) == list and (self.sender == 'platform.driver' or self.recipient == 'platform.driver'):
                    if len(params) > 0 and params[0]:
                        self.device = str(params[0])
                    if len(params) > 1 and params[1]:
                        self.point = str(params[1])
                    if len(params) > 2 and params[2] != '':
                        self.point_value = str(params[2])

    def filtered_properties(self):
        """Return a list of the DebugMessage member variables that can be used when filtering output."""
        atts = list(self.attribute_names)
        atts.remove('topic')            # Filtering for this attribute is handled as a special case
        return atts

    def __str__(self):
        """Format the DebugMessage as a string suitable for trace display."""
        global _verbosity
        my_str = ''
        if _verbosity == VERBOSITY_HIGH:
            for attname in self.attribute_names:
                val = getattr(self, attname)
                my_str += format_time(val, label='') if attname == 'timestamp' else format_attribute(val, label=attname)
        else:
            for attname in self.attribute_names_short_list:
                val = getattr(self, attname)
                if attname == 'timestamp':
                    my_str += format_time(val, label='')
                elif attname == 'session_id' or attname == 'subsystem' or attname == 'direction':
                    my_str += format_attribute(val, label='')
                else:
                    my_str += format_attribute(val, label=attname)
        return my_str

    def as_json_compatible_object(self):
        """Format the DebugMessageExchange as a dictionary of strings to be returned in response to an RPC."""
        att_dict = {}
        for attname in self.attribute_names:
            val = getattr(self, attname)
            if attname == 'timestamp':
                att_dict[attname] = format_time(val)
            else:
                try:
                    val = str(val, 'utf-8')
                except TypeError:
                    pass
                finally:
                    att_dict[attname] = val
        return att_dict


class DebugMessageExchange(ORMBase):
    """
        Model an exchange of VOLTTRON messages, captured during routing, as a SQL Alchemy / SQLite object.

        All messages for a given request_id are modeled as a single database row.
    """

    __tablename__ = 'DebugMessageExchange'

    rowid = Column(Integer, primary_key=True)
    children = relationship("DebugMessage")

    request_id = Column(String, nullable=False, unique=True)
    session_id = Column(Integer)
    sender = Column(String)
    sender_time = Column(DateTime)
    recipient = Column(String)
    recipient_time = Column(DateTime)
    topic = Column(String)
    method = Column(String)
    device = Column(String)
    point = Column(String)
    assignment = Column(String)
    result = Column(String)

    attribute_names = [
        'request_id', 'session_id',
        'sender', 'sender_time',
        'recipient', 'recipient_time',
        'topic', 'method', 'device', 'point', 'assignment', 'result']

    def __init__(self, debug_msg, session_id):
        self.session_id = session_id
        self.request_id = debug_msg.request_id
        # The first message's sender is the exchange's sender.
        self.sender = debug_msg.sender
        self.sender_time = debug_msg.timestamp

    def update_for_message(self, debug_msg):
        """
            A DebugMessage is being recorded with the same ID as this DebugMessageExchange. Update it.

        @param debug_msg: A DebugMessage.
        """
        debug_msg.parent = self
        if debug_msg.direction == 'incoming':
            # The last incoming message's sender is the exchange's recipient.
            self.recipient = debug_msg.sender
            self.recipient_time = debug_msg.timestamp
        for prop in ['topic', 'result', 'method', 'device', 'point', 'point_value']:
            # Update these attributes with the most recent non-empty values that are available for the request ID.
            if getattr(debug_msg, prop):
                setattr(self, prop, getattr(debug_msg, prop))

    def __str__(self):
        """Format the DebugMessageExchange as a string suitable for trace display."""
        my_str = ''
        for attname in self.attribute_names:
            val = getattr(self, attname)
            if attname == 'sender_time' or attname == 'recipient_time':
                my_str += format_time(val, label='')
            elif attname == 'session_id' or attname == 'request_id':
                my_str += format_attribute(val, label='')
            else:
                my_str += format_attribute(val, label=attname)
        return my_str

    def as_json_compatible_object(self):
        """Format the DebugMessageExchange as a dictionary of strings to be returned in response to an RPC."""
        att_dict = {}
        for attname in self.attribute_names:
            val = getattr(self, attname)
            att_dict[attname] = format_time(val) if (attname == 'sender_time' or attname == 'recipient_time') else val
        return att_dict


class DebugSession(ORMBase):
    """Model a message debugging session as a SQL Alchemy / SQLite object."""

    __tablename__ = 'DebugSession'

    rowid = Column(Integer, primary_key=True)
    created_on = Column(DateTime)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    num_messages = Column(Integer)

    def __init__(self):
        self.created_on = datetime.datetime.now()
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.num_messages = 0

    def __str__(self):
        """Format the DebugSession as a string suitable for trace display."""
        my_str = 'Debug session id:{0}; '.format(self.rowid)
        my_str += format_time(self.start_time, label='start', verbosity='high')
        my_str += format_time(self.end_time, label='end', verbosity='high')
        my_str += format_attribute(self.num_messages, label='messages')
        return my_str

    def as_json_compatible_object(self):
        """Format the DebugSession as a dictionary of strings to be returned in response to an RPC."""
        return {
            'rowid': self.rowid,
            'created_on': format_time(self.created_on, verbosity='high'),
            'start_time': format_time(self.start_time, verbosity='high'),
            'end_time': format_time(self.end_time, verbosity='high'),
            'num_messages': self.num_messages,
        }


def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(MessageDebuggerAgent, identity="messagedebugger", version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')
