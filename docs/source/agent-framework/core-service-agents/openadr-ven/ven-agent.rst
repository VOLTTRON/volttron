.. _OpenADR-VEN-Agent:

===============================================
VEN Agent: OpenADR 2.0b Interface Specification
===============================================

OpenADR (Automated Demand Response) is a standard for alerting and responding to the need to adjust electric power
consumption in response to fluctuations in grid demand.

OpenADR communications are conducted between Virtual Top Nodes (VTNs) and Virtual End Nodes (VENs).  In this
implementation a VOLTTRON agent, the VEN agent, acts as a VEN, communicating with its VTN by means of EIEvent and
EIReport services in conformance with a subset of the OpenADR 2.0b specification.  This document's
`VOLTTRON Interface <VEN Agent VOLTTRON Interface>`_ section defines how the VEN agent relays information to,
and receives data from, other VOLTTRON agents.

The OpenADR 2.0b specification (http://www.openadr.org/specification) is available from the OpenADR Alliance.  This
implementation also generally follows the DR program characteristics of the Capacity Program described in Section 9.2
of the OpenADR Program Guide (http://www.openadr.org/assets/openadr_drprogramguide_v1.0.pdf).


DR Capacity Bidding and Events
==============================

The OpenADR Capacity Bidding program relies on a pre-committed agreement about the VEN’s load shed capacity.  This
agreement is reached in a bidding process transacted outside of the OpenADR interaction, typically with a long-term
scope, perhaps a month or longer.  The VTN can “call an event,” indicating that a load-shed event should occur
in conformance with this agreement.  The VTN indicates the level of load shedding desired, when the event should occur,
and for how long. The VEN responds with an `optIn` acknowledgment. (It can also `optOut`, but since it has been
pre-committed, an `optOut` may incur penalties.)


Reporting
---------

The VEN agent reports device status and usage telemetry to the VTN, relying on information received periodically from
other VOLTTRON agents.


General Approach
================

Events:

-  The VEN agent maintains a persistent record of DR events.
-  Event updates (including creation) trigger publication of event JSON on the VOLTTRON message bus.
-  Other VOLTTRON agents can also call a get_events() RPC to retrieve the current status of
   particular events, or of all active events.

Reporting:

-  The VEN agent configuration defines telemetry values (data points) that can be reported to the VTN.
-  The VEN agent maintains a persistent record of telemetry values over time.
-  Other VOLTTRON agents are expected to call report_telemetry() to supply the VEN agent
   with a regular stream of telemetry values for reporting.
-  Other VOLTTRON agents can receive notification of changes in telemetry reporting
   requirements by subscribing to publication of telemetry parameters.


VEN Agent VOLTTRON Interface
============================

The VEN agent implements the following VOLTTRON PubSub and RPC calls.

PubSub: event update

.. code-block:: python

    def publish_event(self, an_event):
        """
            Publish an event.

            When an event is created/updated, it is published to the VOLTTRON bus
            with a topic that includes 'openadr/event_update'.

            Event JSON structure:
                {
                    "event_id"      : String,
                    "creation_time" : DateTime,
                    "start_time"    : DateTime,
                    "end_time"      : DateTime or None,
                    "signals"       : String,     # Values: json string describing one or more signals.
                    "status"        : String,     # Values: unresponded, far, near, active,
                                                  #         completed, canceled.
                    "opt_type"      : String      # Values: optIn, optOut, none.
                }

            If an event status is 'unresponded', the VEN agent is awaiting a decision on
            whether to optIn or optOut. The downstream agent that subscribes to this PubSub
            message should communicate that choice to the VEN agent by calling respond_to_event()
            (see below). The VEN agent then relays the choice to the VTN.

        @param an_event: an EiEvent.
        """

PubSub: telemetry parameters update

.. code-block:: python

    def publish_telemetry_parameters_for_report(self, report):
        """
            Publish telemetry parameters.

            When the VEN agent telemetry reporting parameters have been updated (by the VTN),
            they are published with a topic that includes 'openadr/telemetry_parameters'.
            If a particular report has been updated, the reported parameters are for that report.

            Telemetry parameters JSON example:
            {
                "telemetry": {
                    "baseline_power_kw": {
                        "r_id": "baseline_power",
                        "frequency": "30",
                        "report_type": "baseline",
                        "reading_type": "Mean",
                        "method_name": "get_baseline_power"
                    }
                    "current_power_kw": {
                        "r_id": "actual_power",
                        "frequency": "30",
                        "report_type": "reading",
                        "reading_type": "Mean",
                        "method_name": "get_current_power"
                    }
                    "manual_override": "False",
                    "report_status": "active",
                    "online": "False",
                }
            }

            The above example indicates that, for reporting purposes, telemetry values
            for baseline_power and actual_power should be updated -- via report_telemetry() -- at
            least once every 30 seconds.

            Telemetry value definitions such as baseline_power and actual_power come from the
            agent configuration.

        @param report: (EiReport) The report whose parameters should be published.
        """

RPC calls:

.. code-block:: python

    @RPC.export
    def respond_to_event(self, event_id, opt_in_choice=None):
        """
            Respond to an event, opting in or opting out.

            If an event's status=unresponded, it is awaiting this call.
            When this RPC is received, the VENAgent sends an eventResponse to
            the VTN, indicating whether optIn or optOut has been chosen.
            If an event remains unresponded for a set period of time,
            it times out and automatically optsIn to the event.

            Since this call causes a change in the event's status, it triggers
            a PubSub call for the event update, as described above.

        @param event_id: (String) ID of an event.
        @param opt_in_choice: (String) 'OptIn' to opt into the event, anything else is treated as 'OptOut'.
        """

.. code-block:: python

    @RPC.export
    def get_events(self, event_id=None, in_progress_only=True, started_after=None, end_time_before=None):
        """
            Return a list of events as a JSON string.

            Sample request:
                self.get_events(started_after=utils.get_aware_utc_now() - timedelta(hours=1),
                                end_time_before=utils.get_aware_utc_now())

            Return a list of events.

            By default, return only event requests with status=active or status=unresponded.

            If an event's status=active, a DR event is currently in progress.

        @param event_id: (String) Default None.
        @param in_progress_only: (Boolean) Default True.
        @param started_after: (DateTime) Default None.
        @param end_time_before: (DateTime) Default None.
        @return: (JSON) A list of events -- see 'PubSub: event update'.
        """

.. code-block:: python

    @RPC.export
    def get_telemetry_parameters(self):
        """
            Return the VEN agent's current set of telemetry parameters.

        @return: (JSON) Current telemetry parameters -- see 'PubSub: telemetry parameters update'.
        """

.. code-block:: python

    @RPC.export
    def set_telemetry_status(self, online, manual_override):
        """
            Update the VEN agent's reporting status.

            Set these properties to either 'TRUE' or 'FALSE'.

        @param online: (Boolean) Whether the VEN agent's resource is online.
        @param manual_override: (Boolean) Whether resource control has been overridden.
        """

.. code-block:: python

    @RPC.export
    def report_telemetry(self, telemetry):
        """
            Receive an update of the VENAgent's report metrics, and store them in the agent's database.

            Examples of telemetry are:
            {
                'baseline_power_kw': '15.2',
                'current_power_kw': '371.1',
                'start_time': '2017-11-21T23:41:46.051405',
                'end_time': '2017-11-21T23:42:45.951405'
            }

        @param telemetry_values: (JSON) Current value of each report metric, with reporting-interval start/end.
        """


PubSub: Event Update
--------------------

When an event is created/updated, the event is published with a topic that includes `openadr/event/{ven_id}`.

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

If an event status is 'unresponded', the VEN is awaiting a decision on whether to `optIn` or `optOut`.  The downstream
agent that subscribes to this `PubSub` message should communicate that choice to the VEN by calling respond_to_event()
(see below).  The VEN then relays the choice to the VTN.


PubSub: Telemetry Parameters Update
-----------------------------------

When the VEN telemetry reporting parameters have been updated (by the VTN), they are published with a topic that
includes `openadr/status/{ven_id}`.

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

Telemetry value definitions such as `baseline_power_kw` and `current_power_kw` come from the VEN agent config.


.. toctree::
   :hidden:

   ven-agent-guide
   ven-agent-config


.. _OpenADR-VEN-Agent-Config:

OpenADR VEN Agent: Installation and Configuration
=================================================

The VEN agent can be configured, built and launched using the VOLTTRON agent installation process described in
http://volttron.readthedocs.io/en/develop/devguides/agent_development/Agent-Development.html#agent-development.

The VEN agent depends on some third-party libraries that are not in the standard VOLTTRON installation.  They should be
installed in the VOLTTRON virtual environment prior to building the agent:

.. code-block:: bash

    (volttron) $ cd $VOLTTRON_ROOT/services/core/OpenADRVenAgent
    (volttron) $ pip install -r requirements.txt

where ``$VOLTTRON_ROOT`` is the base directory of the cloned VOLTTRON code repository.

The VEN agent is designed to work in tandem with a “control agent,” another VOLTTRON agent that uses VOLTTRON RPC calls
to manage events and supply report data.  A sample control agent has been provided in the `test/ControlAgentSim`
subdirectory under OpenADRVenAgent.

The VEN agent maintains a persistent store of event and report data in ``$VOLTTRON_HOME/data/openadr.sqlite``.  Some
care should be taken in managing the disk consumption of this data store.  If no events or reports are active, it is
safe to take down the VEN agent and delete the file; the persistent store will be reinitialized automatically on agent
startup.


Configuration Parameters
------------------------

The VEN agent’s configuration file contains JSON that includes several parameters for configuring VTN server
communications and other behavior. A sample configuration file, `openadrven.config`, has been provided in the agent
directory.

The VEN agent supports the following configuration parameters:

========================= ======================== ====================================================
Parameter                 Example                  Description
========================= ======================== ====================================================
db_path                   “$VOLTTRON_HOME/data/    Pathname of the agent's sqlite database. Shell
                          openadr.sqlite”          variables will be expanded if they are present
                                                   in the pathname.
ven_id                    “0”                      The OpenADR ID of this virtual end node. Identifies
                                                   this VEN to the VTN. If automated VEN registration
                                                   is used, the ID is assigned by the VTN at that
                                                   time. If the VEN is registered manually with the
                                                   VTN (i.e., via configuration file settings), then
                                                   a common VEN ID should be entered in this config
                                                   file and in the VTN's site definition.
ven_name                  "ven01"                  Name of this virtual end node. This name is used
                                                   during automated registration only, identiying
                                                   the VEN before its VEN ID is known.
vtn_id                    “vtn01”                  OpenADR ID of the VTN with which this VEN
                                                   communicates.
vtn_address               “http://openadr-vtn.     URL and port number of the VTN.
                          ki-evi.com:8000”
send_registration         “False”                  (“True” or ”False”) If “True”, the VEN sends
                                                   a one-time automated registration request to
                                                   the VTN to obtain the VEN ID. If automated
                                                   registration will be used, the VEN should be run
                                                   in this mode initially, then shut down and run
                                                   with this parameter set to “False” thereafter.
security_level            “standard”               If 'high', the VTN and VEN use a third-party
                                                   signing authority to sign and authenticate each
                                                   request. The default setting is “standard”: the
                                                   XML payloads do not contain Signature elements.
poll_interval_secs        30                       (integer) How often the VEN should send an OadrPoll
                                                   request to the VTN. The poll interval cannot be
                                                   more frequent than the VEN’s 5-second process
                                                   loop frequency.
log_xml                   “False”                  (“True” or “False”) Whether to write each
                                                   inbound/outbound request’s XML data to the
                                                   agent's log.
opt_in_timeout_secs       1800                     (integer) How long to wait before making a
                                                   default optIn/optOut decision.
opt_in_default_decision   “optOut”                 (“True” or “False”) Which optIn/optOut choice
                                                   to make by default.
request_events_on_startup "False"                  ("True" or "False") Whether to ask the VTN for a
                                                   list of current events during VEN startup.
report_parameters         (see below)              A dictionary of definitions of reporting/telemetry
                                                   parameters.
========================= ======================== ====================================================


Reporting Configuration
-----------------------

The VEN’s reporting configuration, specified as a dictionary in the agent configuration, defines each telemetry element
(metric) that the VEN can report to the VTN, if requested.  By default, it defines reports named “telemetry” and
"telemetry_status", with a report configuration dictionary containing the following parameters:

======================================================= =========================== ====================================================
"telemetry" report: parameters                          Example                     Description
======================================================= =========================== ====================================================
report_name                                             "TELEMETRY_USAGE"           Friendly name of the report.
report_name_metadata                                    "METADATA_TELEMETRY_USAGE"  Friendly name of the report’s metadata, when sent
                                                                                    by the VEN’s oadrRegisterReport request.
report_specifier_id                                     "telemetry"                 Uniquely identifies the report’s data set.
report_interval_secs_default                            "300"                       How often to send a reporting update to the VTN.
telemetry_parameters (baseline_power_kw): r_id          "baseline_power"            (baseline_power) Unique ID of the metric.
telemetry_parameters (baseline_power_kw): report_type   "baseline"                  (baseline_power) The type of metric being reported.
telemetry_parameters (baseline_power_kw): reading_type  "Direct Read"               (baseline_power) How the metric was calculated.
telemetry_parameters (baseline_power_kw): units         "powerReal"                 (baseline_power) The reading's data type.
telemetry_parameters (baseline_power_kw): method_name   "get_baseline_power"        (baseline_power) The VEN method to use when
                                                                                    extracting the data for reporting.
telemetry_parameters (baseline_power_kw): min_frequency 30                          (baseline_power) The metric’s minimum sampling
                                                                                    frequency.
telemetry_parameters (baseline_power_kw): max_frequency 60                          (baseline_power) The metric’s maximum sampling
                                                                                    frequency.
telemetry_parameters (current_power_kw): r_id           "actual_power"              (current_power) Unique ID of the metric.
telemetry_parameters (current_power_kw): report_type    "reading"                   (current_power) The type of metric being reported.
telemetry_parameters (current_power_kw): reading_type   "Direct Read"               (current_power) How the metric was calculated.
telemetry_parameters (current_power_kw): units          "powerReal"                 (baseline_power) The reading's data type.
telemetry_parameters (current_power_kw): method_name    "get_current_power"         (current_power) The VEN method to use when
                                                                                    extracting the data for reporting.
telemetry_parameters (current_power_kw): min_frequency  30                          (current_power) The metric’s minimum sampling
                                                                                    frequency.
telemetry_parameters (current_power_kw): max_frequency  60                          (current_power) The metric’s maximum sampling
                                                                                    frequency.
======================================================= =========================== ====================================================

======================================================= =========================== ====================================================
"telemetry_status" report: parameters                   Example                     Description
======================================================= =========================== ====================================================
report_name                                             "TELEMETRY_STATUS"          Friendly name of the report.
report_name_metadata                                    "METADATA_TELEMETRY_STATUS" Friendly name of the report’s metadata, when sent
                                                                                    by the VEN’s oadrRegisterReport request.
report_specifier_id                                     "telemetry_status"          Uniquely identifies the report’s data set.
report_interval_secs_default                            "300"                       How often to send a reporting update to the VTN.
telemetry_parameters (Status): r_id                     "Status"                    Unique ID of the metric.
telemetry_parameters (Status): report_type              "x-resourceStatus"          The type of metric being reported.
telemetry_parameters (Status): reading_type             "x-notApplicable"           How the metric was calculated.
telemetry_parameters (Status): units                    ""                          The reading's data type.
telemetry_parameters (Status): method_name              ""                          The VEN method to use when extracting the data
                                                                                    for reporting.
telemetry_parameters (Status): min_frequency            60                          The metric’s minimum sampling frequency.
telemetry_parameters (Status): max_frequency            120                         The metric’s maximum sampling frequency.
======================================================= =========================== ====================================================
