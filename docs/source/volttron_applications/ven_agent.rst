.. _styleguide: ven_agent

VEN Agent: OpenADR 2.0b Interface Specification
===============================================

OpenADR (Automated Demand Response) is a standard for alerting and responding
to the need to adjust electric power consumption in response to fluctuations in
grid demand.

OpenADR communications are conducted between Virtual Top Nodes (VTNs) and
Virtual End Nodes (VENs). In this implementation a VOLTTRON agent, VEN agent,
acts as a VEN, communicating with its VTN by means of EIEvent and EIReport services
in conformance with a subset of the OpenADR 2.0b specification. This document's
"VOLTTRON Interface" section defines how the VEN agent relays information to,
and receives data from, other VOLTTRON agents.

The OpenADR 2.0b specification (http://www.openadr.org/specification) is available
from the OpenADR Alliance. This implementation also generally follows the DR program
characteristics of the Capacity Program described in Section 9.2 of the OpenADR Program Guide
(http://www.openadr.org/assets/openadr_drprogramguide_v1.0.pdf).

DR Capacity Bidding and Events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The OpenADR Capacity Bidding program relies on a pre-committed agreement about the
VEN’s load shed capacity. This agreement is reached in a bidding process
transacted outside of the OpenADR interaction, typically with a long-term scope,
perhaps a month or longer. The VTN can “call an event,” indicating that a load-shed event should occur
in conformance with this agreement. The VTN indicates the level of load shedding
desired, when the event should occur, and for how long. The VEN responds with an
"optIn” acknowledgment. (It can also “optOut,” but since it has been pre-committed,
an “optOut” may incur penalties.)

Reporting
~~~~~~~~~

The VEN agent reports device status and usage telemetry to the VTN, relying on
information received periodically from other VOLTTRON agents.

General Approach
~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The VEN agent implements the following VOLTTRON PubSub and RPC calls.

PubSub: event update
::

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
::

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

For Further Information
~~~~~~~~~~~~~~~~~~~~~~~

Please contact Rob Calvert at Kisensum, rob@kisensum.com
