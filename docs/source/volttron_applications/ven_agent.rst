.. _styleguide: ven_agent

VENAgent: OpenADR 2.0b Interface Specification
==============================================

OpenADR (Automated Demand Response) is a standard for alerting and responding
to the need to adjust electric power consumption in response to fluctuations in
grid demand. OpenADR alerts and responses are communicated via market signals.

OpenADR communications are conducted between Virtual Top Nodes (VTNs) and
Virtual End Nodes (VENs). In this implementation a VOLTTRON agent, VENAgent,
acts as an OpenADR VEN, communicating by means of EIEvent and EIReport services
in conformance with a subset of the OpenADR 2.0b specification.  This document's
"VOLTTRON Interface" section defines how the VENAgent relays information to,
and receives data from, other VOLTTRON agents.

This specification follows the DR program characteristics of the Capacity Program
described in Section 9.2 of the OpenADR Program Guide
(http://www.openadr.org/assets/openadr_drprogramguide_v1.0.pdf).
A specification for OpenADR 2.0b can be downloaded from the OpenADR Alliance
(http://www.openadr.org/specification) web site.

DR Capacity Bidding and Events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The OpenADR Capacity Bidding program relies on a pre-committed agreement about the
VEN’s load shed capacity. This agreement is reached in a bidding process
transacted outside of the OpenADR interaction, typically with a long-term scope,
perhaps a month or longer.

The VTN can “call an event,” indicating that a load-shed event should occur
in conformance with this agreement. The VTN indicates the level of load shedding
desired, when the event should occur, and for how long. The VEN responds with an
"opt in” acknowledgment. (It can also “opt out,” but since it has been pre-committed,
an “opt out” may incur penalties.)

Reporting
~~~~~~~~~

The VENAgent reports device status and usage telemetry to the VTN, relying on
information received periodically from other VOLTTRON agents.

General Approach
~~~~~~~~~~~~~~~~

Events:

-  The VENAgent maintains a persistent record of DR events.
-  Event updates (including creation) trigger publication of event JSON on the VOLTTRON message bus.
-  Another VOLTTRON agent can get notified immediately of event updates by subscribing
   to event publication. It can also call get_events() to retrieve the current status of
   each active DR event.

Reporting:

-  The VENAgent config defines telemetry values (data points) that can be reported to the VTN.
-  The VENAgent maintains a persistent record of telemetry values over time.
-  Other VOLTTRON agents are expected to call report_telemetry() to supply the VENAgent
   with a regular stream of telemetry values for reporting.
-  The VTN can identify which of the VENAgent's supported data points needs to be actively
   reported at a given time, including their reporting frequency.
-  Another VOLTTRON agent can get notified immediately of changes in telemetry reporting
   requirements by subscribing to publication of "telemetry parameters." It can also call
   get_telemetry_parameters() to retrieve the current set of reporting requirements.
-  The VENAgent persists these requirements so that they survive VOLTTRON restarts.

VENAgent VOLTTRON Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

VENAgent implements the following VOLTTRON PubSub and RPC calls.

PubSub: event update
::

    When an event is created/updated.
    the event is published with a topic that includes 'openadr/event_update'.

    Event JSON structure:
    {
        "id"            : String,
        "creation_time" : DateTime,
        "start_time"    : DateTime,
        "end_time"      : DateTime,
        "level"         : Integer,    # Values: 1, 2, 3. Expected to be 1.
        "status"        : String,     # Values: unresponded, far, near, active,
                                      #         completed, canceled.
        "opt_type"      : String      # Values: optIn, optOut, none.
    }

    If an event status is 'unresponded', the VENAgent is awaiting a decision on
    whether to optIn or optOut. The downstream agent that subscribes to this PubSub
    message should communicate that choice to the VENAgent by calling respond_to_event()
    (see below). The VENAgent then relays the choice to the VTN.

PubSub: telemetry parameters update
::

    When the VENAgent telemetry reporting parameters have been updated (by the VTN),
    the parameters are published with a topic that includes 'openadr/telemetry_parameters'.

    Telemetry parameters JSON example:
    {
        "power_kw"   : {"frequency": 300},
        "energy_kwh" : {"frequency": 300},
    }

    The above example would indicate that, for reporting purposes, telemetry values
    for power_kw and energy_kwh should be updated -- via report_telemetry() -- at
    least once every 300 seconds.

    Telemetry value definitions such as power_kw and energy_kwh come from the agent config.

RPC calls:

.. code-block:: python

    @RPC.export
    def respond_to_event(self, event_id, opt_in=True):
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
        @param opt_type: (Boolean) Whether to opt in to the event (default True).
        """

.. code-block:: python

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

.. code-block:: python

    @RPC.export
    def get_telemetry_parameters(self):
        """
            Return the VENAgent's current set of telemetry parameters.

        @return: (JSON) Current telemetry parameters -- see 'PubSub: telemetry parameters update'.
        """

.. code-block:: python

    @RPC.export
    def set_telemetry_status(self, online, manual_override):
        """
            Update the VENAgent's reporting status.

        @param online: (Boolean) Whether the VENAgent's resource is online.
        @param manual_override: (Boolean) Whether resource control has been overridden.
        """

.. code-block:: python

    @RPC.export
    def report_telemetry(self, telemetry_values):
        """
            Update the VENAgent's report metrics.

            Examples of telemetry_values are:
            {
                "power_kw"   : 15.2,
                "energy_kwh" : 371.1,
            }

        @param telemetry_values: (JSON) Current value of each report metric.
        """

For Further Information
~~~~~~~~~~~~~~~~~~~~~~~

Please contact Rob Calvert at Kisensum, rob@kisensum.com
