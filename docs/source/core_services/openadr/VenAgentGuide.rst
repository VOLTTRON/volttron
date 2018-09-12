.. _VenAgentGuide:

OpenADR VEN Agent: Operation
============================

Events:

- The VEN maintains a persistent record of DR events.
- Event updates (including creation) trigger publication of event JSON on the VOLTTRON message bus.
- Another VOLTTRON agent (a “control agent”) can get notified immediately of event updates by subscribing to event publication. It can also call get_events() to retrieve the current status of each active DR event.

Reporting:

- The VEN reports device status and usage telemetry to the VTN, relying on information received periodically from other VOLTTRON agents.
- The VEN config defines telemetry values (data points) that can be reported to the VTN.
- The VEN maintains a persistent record of telemetry values over time.
- Other VOLTTRON agents are expected to call report_telemetry() to supply the VEN with a regular stream of telemetry values for reporting.
- The VTN can identify which of the VEN’s supported data points needs to be actively reported at a given time, including their reporting frequency.
- Another VOLTTRON agent (a “control agent”) can get notified immediately of changes in telemetry reporting requirements by subscribing to publication of “telemetry parameters.” It can also call get_telemetry_parameters() to retrieve the current set of reporting requirements.
- The VEN persists these reporting requirements so that they survive VOLTTRON restarts.

VOLTTRON Agent Interface
------------------------

The VEN implements the following VOLTTRON PubSub and RPC calls.

PubSub: Event Update
--------------------

When an event is created/updated, the event is published with a topic that includes 'openadr/event/{ven_id}'.

Event JSON structure:
::

    {
        "event_id"      : String,
        "creation_time" : DateTime - UTC,
        "start_time"    : DateTime - UTC,
        "end_time"      : DateTime - UTC,
        "priority"      : Integer,    # Values: 0, 1, 2, 3. Usually expected to be 1.
        "signals"       : String,     # Values: json string describing one or more signals.
        "status"        : String,     # Values: unresponded, far, near, active, completed, canceled.
        "opt_type"      : String      # Values: optIn, optOut, none.
    }

If an event status is 'unresponded', the VEN is awaiting a decision on whether to optIn or optOut.
The downstream agent that subscribes to this PubSub message should communicate that choice
to the VEN by calling respond_to_event() (see below). The VEN then relays the choice to the VTN.


PubSub: Telemetry Parameters Update
-----------------------------------

When the VEN telemetry reporting parameters have been updated (by the VTN), they
are published with a topic that includes 'openadr/status/{ven_id}'.

These parameters include state information about the current report.

Telemetry parameters structure:
::

    {
        'telemetry': '{
            "baseline_power_kw": {
                "r_id"            : "baseline_power",       # ID of the reporting metric
                "report_type"     : "baseline",             # Type of reporting metric, e.g. baseline or reading
                "reading_type"    : "Direct Read",          # (per OpenADR telemetry_usage report requirements)
                "units"           : "powerReal",            # (per OpenADR telemetry_usage reoprt requirements)
                "method_name"     : "get_baseline_power",   # Name of the VEN agent method that gets the metric
                "min_frequency"   : (Integer),              # Data capture frequency in seconds (minimum)
                "max_frequency"   : (Integer)               # Data capture frequency in seconds (maximum)
            },
            "current_power_kw": {
                "r_id"            : "actual_power",         # ID of the reporting metric
                "report_type"     : "reading",              # Type of reporting metric, e.g. baseline or reading
                "reading_type"    : "Direct Read",          # (per OpenADR telemetry_usage report requirements)
                "units"           : "powerReal",            # (per OpenADR telemetry_usage report requirements)
                "method_name"     : "get_current_power",    # Name of the VEN agent method that gets the metric
                "min_frequency"   : (Integer),              # Data capture frequency in seconds (minimum)
                "max_frequency"   : (Integer)               # Data capture frequency in seconds (maximum)
            }
        }'
        'report parameters': '{
            "status"              : (String),               # active, inactive, completed, or cancelled
            "report_specifier_id" : "telemetry",            # ID of the report definition
            "report_request_id"   : (String),               # ID of the report request; supplied by the VTN
            "request_id"          : (String),               # Request ID of the most recent VTN report modification
            "interval_secs"       : (Integer),              # How often a report update is sent to the VTN
            "granularity_secs"    : (Integer),              # How often a report update is sent to the VTN
            "start_time"          : (DateTime - UTC),       # When the report started
            "end_time"            : (DateTime - UTC),       # When the report is scheduled to end
            "last_report"         : (DateTime - UTC),       # When a report update was last sent
            "created_on"          : (DateTime - UTC)        # When this set of information was recorded in the VEN db
        }',
        'manual_override'         : (Boolean)               # VEN manual override status, as supplied by Control Agent
        'online'                  : (Boolean)               # VEN online status, as supplied by Control Agent
    }

Telemetry value definitions such as baseline_power_kw and current_power_kw come from the VEN agent config.

RPC Calls
---------

respond_to_event()
::

    @RPC.export
    def respond_to_event(self, event_id, opt_in=True):
        """
            Respond to an event, opting in or opting out.

            If an event's status=unresponded, it is awaiting this call.
            When this RPC is received, the VEN sends an eventResponse to
            the VTN, indicating whether optIn or optOut has been chosen.
            If an event remains unresponded for a set period of time,
            it times out and automatically opts in to the event.

            Since this call causes a change in the event's status, it triggers
            a PubSub call for the event update, as described above.

        @param event_id: (String) ID of an event.
        @param opt_type: (Boolean) Whether to opt in to the event (default True).
        """

get_events()
::

    @RPC.export
    def get_events(self, active_only=True, started_after=None, end_time_before=None):
        """
            Return a list of events.

            By default, return only event requests with status=active or status=unresponded.

            If an event's status=active, a DR event is currently in progress.

        @param active_only: (Boolean) Default True.
        @param started_after: (DateTime) Default None.
        @param end_time_before: (DateTime) Default None.
        @return: (JSON) A list of events -- see 'PubSub: event update'.
        """

get_telemetry_parameters()
::

    @RPC.export
    def get_telemetry_parameters(self):
        """
            Return the VEN's current set of telemetry parameters.

        @return: (JSON) Current telemetry parameters -- see 'PubSub: telemetry parameters update'.
        """

set_telemetry_status()
::

    @RPC.export
    def set_telemetry_status(self, online, manual_override):
        """
            Update the VEN's reporting status.

        @param online: (Boolean) Whether the VEN's resource is online.
        @param manual_override: (Boolean) Whether resource control has been overridden.
        """

report_telemetry()
::

    @RPC.export
    def report_telemetry(self, telemetry_values):
        """
            Update the VEN's report metrics.

            Examples of telemetry_values are:
            {
                'baseline_power_kw': '6.2',
                'current_power_kw': '6.145',
                'start_time': '2017-12-05 16:11:42.977298+00:00',
                'end_time': '2017-12-05 16:12:12.977298+00:00'
            }

        @param telemetry_values: (JSON) Current value of each report metric.
        """
