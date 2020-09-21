.. _Message-Debugging-Specification:

Message Bus Visualization and Debugging - Specification
=======================================================

NOTE: This is a planning document, created prior to implementation of the
VOLTTRON Message Debugger. It describes the tool's general goals, but it's not
always accurate about specifics of the ultimate implementation. For a description
of Message Debugging as implemented, with advice on how to configure and
use it, please see :doc:`Message-Debugging <../devguides/agent_development/Message-Debugging>`.

Description
-----------

VOLTTRON agents send messages to each other on the VOLTTRON message bus.
It can be useful to examine the contents of this message stream
while debugging and troubleshooting agents and drivers.

In satisfaction of this specification, a new Message Monitor capability will be implemented
allowing VOLTTRON agent/driver developers to monitor the message stream,
filter it for an interesting set of messages, and display the
contents and characteristics of each message.

Some elements below are central to this effort (required),
while others are useful improvements (optional) that may be
implemented if time permits.

Feature: Capture Messages and Display a Message Summary
-------------------------------------------------------

When enabled, the Message Monitor will capture details about a stream of routed messages.
On demand, it will display a message summary, either in real time as the messages are routed,
or retrospectively.

A summary view will convey the high level interactions occurring between VOLTTRON agents
as conversations that may be expanded for more detail.  A simple RPC call that involves
4 message send/recv segments will be displayed as a single object that can be expanded.
In this way, the message viewer will provide a higher-level view of
message bus activity than might be gleaned from verbose logs using grep.

Pub/sub interactions will be summarized at the topic level with high-level statistics
such as the number of subscribers, # of messages published during the capture period, etc.
Drilling into the interaction might show the last message published with the ability to
drill deeper into individual messages. A diff display would show how the published
data is changing.


Summary view
::

    - 11:09:31.0831   RPC       set_point             charge.control  platform.driver
    | -  params: ('set_load', 10)   return: True
    - 11:09:31.5235   Pub/Sub   devices/my_device     platform.driver     2 subscribers
    | - Subscriber: charge.control
         | - Last message 11:09:31.1104:
              [
                    {
                        'Heartbeat': True,
                        'PowerState': 0,
                        'temperature': 50.0,
                        'ValveState': 0
                    },
                    ...
                ]
         | - Diff to 11:09:21.5431:
                    'temperature': 48.7,

The summary's contents and format will vary by message subsystem.

RPC request/response pairs will be displayed on a single line:
::

    (volttron) d1:volttron myname$ msmon —agent='(Agent1,Agent2)'

    Agent1                                                                      Agent2
    2016-11-22T11:09:31.083121+00:00 rpc: devices/my_topic; 2340972387; sent    2016-11-22T11:09:31.277933+00:00 responded: 0.194 sec
    2016-11-22T11:09:32.005938+00:00 rpc: devices/my_topic; 2340972388; sent    2016-11-22T11:09:32.282193+00:00 responded: 0.277 sec
    2016-11-22T11:09:33.081873+00:00 rpc: devices/my_topic; 2340972389; sent    2016-11-22T11:09:33.271199+00:00 responded: 0.190 sec
    2016-11-22T11:09:34.049139+00:00 rpc: devices/my_topic; 2340972390; sent    2016-11-22T11:09:34.285393+00:00 responded: 0.236 sec
    2016-11-22T11:09:35.053183+00:00 rpc: devices/my_topic; 2340972391; sent    2016-11-22T11:09:35.279317+00:00 responded: 0.226 sec
    2016-11-22T11:09:36.133948+00:00 rpc: devices/my_topic; 2340972392; sent    2016-11-22T11:09:36.133003+00:00 dequeued

When PubSub messages are displayed, each message's summary will include its count of subscribers:
::

    (volttron) d1:volttron myname$ msmon —agent=(Agent1)

    Agent1
    2016-11-22T11:09:31.083121+00:00 pubsub: devices/my_topic; 2340972487; sent; 2 subs
    2016-11-22T11:09:32.005938+00:00 pubsub: devices/my_topic; 2340972488; sent; 2 subs
    2016-11-22T11:09:33.081873+00:00 pubsub: devices/my_topic; 2340972489; sent; 2 subs
    2016-11-22T11:09:34.049139+00:00 pubsub: devices/my_topic; 2340972490; sent; 2 subs
    2016-11-22T11:09:35.053183+00:00 pubsub: devices/my_topic; 2340972491; sent; 2 subs

While streaming output of a message summary, a defined keystroke sequence will "pause" the output,
and another keystroke sequence will "resume" displaying the stream.

Feature: Capture and Display Message Details
--------------------------------------------

The Message Monitor will capture a variety of details about each message, including:

    1. Sending agent ID
    2. Receiving agent ID
    3. User ID
    4. Message ID
    5. Subsystem
    6. Topic
    7. Message data
    8. Message lifecycle timestamps, in UTC (when sent, dequeued, responded)
    9. Message status (sent, responded, error, timeout)
    10. Message size
    11. Other message properties TBD (e.g., queue depth?)

On demand, it will display these details for a single message ID:
::

    (volttron)d1:volttron myname$ msmon --id='2340972390'

    2016-11-22T11:09:31.053183+00:00 (Agent1)
    INFO:
        Subsystem: 'pubsub',
        Sender: 'Agent1',
        Topic: 'devices/my_topic',
        ID: '2340972390',
        Sent: '2016-11-22T11:09:31.004986+00:00',
        Message:
        [
            {
                'Heartbeat': True,
                'PowerState': 0,
                'temperature': 50.0,
                'ValveState': 0
            },
            {
                'Heartbeat':
                {
                    'units': 'On/Off',
                    'type': 'integer'
                },
                'PowerState':
                {
                    'units': '1/0',
                    'type': 'integer'
                },
                'temperature':
                {
                    'units': 'Fahrenheit',
                    'type': 'integer'
                },
                'ValveState':
                {
                    'units': '1/0',
                    'type': 'integer'
                }
            }
        ]

A VOLTTRON message ID is not unique to a single message. A group of messages in a "conversation"
may share a common ID, for instance during RPC request/response exchanges.
When detailed display of all messages for a single message ID is requested, they will be displayed
in chronological order.

Feature: Display Message Statistics
-----------------------------------

Statistics about the message stream will also be available on demand:

    1. Number of messages sent, by agent, subsystem, topic
    2. Number of messages received, by agent, subsystem, topic

Feature: Filter the Message Stream
----------------------------------

The Message Monitor will be able to filter the message stream display
to show only those messages that match a given set of criteria:

    1. Sending agent ID(s)
    2. Receiving agent ID(s)
    3. User ID(s)
    4. Subsystem(s)
    5. Topic - Specific topic(s)
    6. Topic - Prefix(es)
    7. Specific data value(s)
    8. Sampling start/stop time
    9. Other filters TBD

User Interface: Linux Command Line
----------------------------------

A Linux command-line interface will enable the following user actions:

    1. Enable message tracing
    2. Disable message tracing
    3. Define message filters
    4. Define verbosity of displayed-message output
    5. Display message stream
    6. Begin recording messages
    7. Stop recording messages
    8. Display recorded messages
    9. Play back (re-send) recorded messages

Feature (not implemented): Watch Most Recent
--------------------------------------------

Optionally, the Message Monitor can be asked to "watch" a specific data element.
In that case, it will display the value of that element in the most recent message
matching the filters currently in effect. As the data to be displayed changes,
the display will be updated in place without scrolling (similar to "top" output):

::

    (volttron) d1:volttron myname$ msmon —agent='(Agent1)' --watch='temperature'

    Agent1
    2016-11-22T11:09:31.053183+00:00 pubsub: my_topic; 2340972487; sent; 2 subs; temperature=50

Feature (not implemented): Regular Expression Support
-----------------------------------------------------

It could help for the Message Monitor's filtering logic to support regular expressions.
Regex support has also been requested (Issue #207) when identifying a subscribed pub/sub topic
during VOLTTRON message routing.

Optionally, regex support will be implemented in Message Monitor filtering criteria,
and also (configurably) during VOLTTRON topic matching.

Feature (not implemented): Message Stream Record and Playback
-------------------------------------------------------------

The Message Monitor will be able to "record" and "play back" a message sequence:

    1. Capture a set of messages as a single "recording"
    2. Inspect the contents of the "recording"
    3. "Play back" the recording -- re-send the recording's messsage sequence in VOLTTRON

Feature (not implemented): On-the-fly Message Inspection and Modification
-------------------------------------------------------------------------

VOLTTRON message inspection and modification, on-the-fly, may be supported from the command line.
The syntax and implementation would be similar to pdb (Python Debugger), and might
be written as an extension to pdb.

Capabilities:

    1. Drill-down inspection of message contents.
    2. Set a breakpoint based on message properties, halting upon routing a matching message.
    3. While halted on a breakpoint, alter a message's contents.

Feature (not implemented): PyCharm Debugging Plugin
---------------------------------------------------

VOLTTRON message debugging may also be published as a PyCharm plugin.
The plugin would form a more user-friendly interface for the same set of capabilities
described above -- on-the-fly message inspection and modification, with the ability to
set a breakpoint based on message properties.

User Interface (not implemented): PCAP/Wireshark
------------------------------------------------

Optionally, we may elect to render the message trace as a stream of PCAP data,
thereby exploiting Wireshark's filtering and display capabilities.
This would be in accord with the enhancement suggested in VOLTTRON Issue #260.

User Interface (not implemented): Volttron Central Dashboard Widget
-------------------------------------------------------------------

Optionally, the Message Monitor will be integrated as a new Volttron Central dashboard widget,
supporting each of the following:

    1. Enable/Disable the monitor
    2. Filter messages
    3. Configure message display details
    4. Record/playback messages

User Interface (not implemented): Graphical Display of Message Sequence
-----------------------------------------------------------------------

Optionally, the Volttron Central dashboard widget will provide graphical display
of message sequences, allowing enhanced visualization of request/response patterns.

Related Development: PyCharm Documentation
------------------------------------------

Also included in this effort will be a contribution to VOLTTRON documentation about installing
and configuring a PyCharm environment for developing, debugging and testing VOLTTRON
agents and drivers.

Engineering Design Notes
========================

Grabbing Messages Off the Bus
-----------------------------

This tool depends on reading and storing all messages that pass through the VIP router.  The Router class
already has hooks that allow for the capturing of messages at various points in the routing workflow.  The
BaseRouter abstract class defines ``issue(self, topic, frames, extra)``. This method is called from ``BaseRouter.route``
and ``BaseRouter._send`` during the routing of messasges.  The ``topic`` parameter (not to be confused with a
message topic found in ``frames``) identifies the point or state in the routing worflow at which the issue was called.

The defined ``topics`` are: INCOMING, OUTGOING, ERROR and UNROUTABLE.  Most messages will result in two calls, one
with the INCOMING topic as the message enters the router and one with the OUTGOING topic as the message is
sent on to its destination.  Messages without a recipient are intended for the router itself and do not result
in an OUTGOING call to ``issue``.

``Router.issue`` contains the concrete implementation of the method.  It does two things:

1. It writes the topic, frames and optional extra parameters to the logger using the FramesFormatter.
2. It invokes ``self._tracker.hit(topic, frames, extra)``.  The Tracker class collects statistics by topic and counts the messages within a topic by peer, user and subsystem.

The issue method can be modified to optionally publish the ``issue`` messages to an in-process ZMQ address
that the message-viewing tool will subscribe to.  This will minimize changes to core VOLTTRON code and minimize
the impact of processing these messages for debugging.

Message Processor
-----------------

The message processor will subscribe to messages coming out of the Router.issue() method and process these
messages based on the current message viewer configuration. Messages will be written to a SQLite db since this
is packaged with Python and currently used by other VOLTTRON agents.

Message Viewer
--------------

The message viewer will display messages from the SQLite db.  We need to consider whether it should also subscribe
to receiving messages in real-time.  The viewer will be responsible for displaying message statistics and will provide
a command line interface to filter and display messages.

Message Db Schema
-----------------

::

    message(id, created_on, issue_topic, extras, sender, recipient, user_id, msg_id, subsystem, data)

msg_id will be used to associate pairs of incoming/outgoing messages.

.. note:: data will be a jsonified list of frames, alternatively we could add a message_data table with one
    row per frame.

A session table will track the start and end of a debug session and, at the end of a session, record statistics
on the messages in the session.

::

    session(id, created_on, name, start_time,  end_time, num_messages)

The command line tool will allow users to delete old sessions and select a session for review/playback.
