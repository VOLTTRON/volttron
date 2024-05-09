.. _OpenADR-VEN-Agent:

======================
OpenADR 2.0b VEN Agent
======================

OpenADR (Automated Demand Response) is a standard for alerting and responding to the need to adjust electric power
consumption in response to fluctuations in grid demand.

OpenADR communications are conducted between Virtual Top Nodes (VTNs) and Virtual End Nodes (VENs).  In this
implementation, a VOLTTRON agent, the VEN agent, acts as a VEN, communicating with its VTN by means of EIEvent and
EIReport services in conformance with a subset of the OpenADR 2.0b specification.  This document's
VEN Agent VOLTTRON Interface section defines how the VEN agent relays information to,
and receives data from, other VOLTTRON agents.

The `OpenADR 2.0b specification <http://www.openadr.org/specification>`_ is available from the OpenADR Alliance.  This
implementation also generally follows the DR program characteristics of the Capacity Program described in Section 9.2
of the `OpenADR Program Guide <http://www.openadr.org/assets/openadr_drprogramguide_v1.0.pdf>`_.


DR Capacity Bidding and Events
==============================

The OpenADR Capacity Bidding program relies on a pre-committed agreement about the VEN’s load shed capacity.  This
agreement is reached in a bidding process transacted outside of the OpenADR interaction, typically with a long-term
scope, perhaps a month or longer.  The VTN can “call an event,” indicating that a load-shed event should occur
in conformance with this agreement.  The VTN indicates the level of load shedding desired, when the event should occur,
and for how long. The VEN responds with an `optIn` acknowledgment. It can also `optOut`, but since it has been
pre-committed, an `optOut` may incur penalties.

.. _my-reference-label:
Reporting
---------

The VEN agent reports device status and usage telemetry to the VTN, relying on information received periodically from
other VOLTTRON agents.


General Approach
================

Events:

-  The VEN agent maintains a persistent record of DR events.
-  Event updates (including creation) trigger publication of event JSON on the VOLTTRON message bus.

Reporting:

-  The VEN agent configuration defines telemetry values (data points) that can be reported to the VTN.
-  Other VOLTTRON agents are expected to call add_report_capability() to supply the VEN agent
   with a regular stream of telemetry values for reporting.
-  Other VOLTTRON agents can receive notification of changes in telemetry reporting
   requirements by subscribing to publication of telemetry parameters.


VEN Agent VOLTTRON Interface
============================

The VEN agent implements the following VOLTTRON PubSub and RPC calls.

PubSub: event update

.. code-block:: python

       def publish_event(self, event: Event) -> None:
        """
            Publish an event to the Volttron message bus. When an event is created/updated, it is published to the VOLTTRON bus with a topic that includes 'openadr/event_update'.

            :param event: The Event received from the VTN
        """

RPC calls:

.. code-block:: python

    @RPC.export
    def add_report_capability(
        self,
        callback: Callable,
        report_name: REPORT_NAME,
        resource_id: str,
        measurement: MEASUREMENTS,
    ) -> tuple:
        """
        Add a new reporting capability to the client.

        This method is remotely accessible by other agents through Volttron's feature Remote Procedure Call (RPC);
        for reference on RPC, see https://volttron.readthedocs.io/en/develop/platform-features/message-bus/vip/vip-json-rpc.html?highlight=remote%20procedure%20call

        :param callback: A callback or coroutine that will fetch the value for a specific report. This callback will be passed the report_id and the r_id of the requested value.
        :param report_name: An OpenADR name for this report
        :param resource_id: A specific name for this resource within this report.
        :param measurement: The quantity that is being measured
        :return: Returns a tuple consisting of a report_specifier_id (str) and an r_id (str) an identifier for OpenADR messages
        """


PubSub: Event Update
--------------------

When an event is created/updated, the event is published with a topic that includes `openadr/event/{ven_name}`.

Event JSON structure:

::

    {'active_period': {'dtstart': DateTime - UTC,
                       'duration': TimeDelta - seconds,
                       'notification': TimeDelta - seconds,
                       'ramp_up': TimeDelta - seconds,
                       'recovery': TimeDelta - seconds,
                       'tolerance': {'tolerate': {'startafter': TimeDelta - seconds}}},
     'event_descriptor': {'created_date_time': DateTime - UTC,
                          'event_id': String,
                          'event_status': String,
                          'market_context': String,
                          'modification_date_time': DateTime - UTC,
                          'modification_number': Integer,
                          'modification_reason': Any,
                          'priority': Integer,
                          'test_event': Boolean,
                          'vtn_comment': Any},
     'event_signals': [{'current_value': Double,
                        'intervals': [{'duration': TimeDelta - seconds,
                                       'signal_payload': Double,
                                       'uid': Integer}],
                        'signal_id': String,
                        'signal_name': String,
                        'signal_type': String}],
     'response_required': String,
     'targets': [{'ven_id': String}],
     'targets_by_type': {'ven_id': [String]}}


.. _OpenADR-VEN-Agent-Config:

OpenADR VEN Agent: Installation and Configuration
=================================================

The VEN agent can be configured, built and launched using the VOLTTRON agent installation process described in
https://volttron.readthedocs.io/en/releases-8.2/developing-volttron/developing-agents/agent-development.html#packaging-and-installation.

The VEN agent depends on some third-party libraries that are not in the standard VOLTTRON installation.  They should be
installed in the VOLTTRON virtual environment prior to building the agent:

.. code-block:: bash

    (volttron) $ cd $VOLTTRON_ROOT/services/core/OpenADRVenAgent
    (volttron) $ pip install -r requirements.txt

where :term:`$VOLTTRON_ROOT <VOLTTRON_ROOT>` is the base directory of the cloned VOLTTRON code repository.

The VEN agent is designed to work in tandem with a “control agent,” another VOLTTRON agent that uses VOLTTRON RPC calls
to manage events and supply report data.


Configuration Parameters
------------------------

The VEN agent’s configuration file contains JSON that includes several parameters for configuring VTN server
communications and other behavior. A sample configuration file, `config_example1.json`, has been provided in the agent
directory.

The VEN agent supports the following configuration parameters. Note: Some configurations will be noted as required; otherwise, they are optional:

========================= ======================== ====================================================
Parameter                 Example                  Description
========================= ======================== ====================================================
ven_name                  "ven01"                  (Required) Name of this virtual end node. This name is used
                                                   during automated registration only, identifying
                                                   the VEN before its VEN ID is known.
vtn_url                   “http://openadr-vtn.     (Required) URL and port number of the VTN.
                          ki-evi.com:8000”
debug                     true                     Whether or not to print debugging messages
cert                      "/path/to/my/cert"       The path to a PEM-formatted Certificate file to use for signing messages.
key                       "/path/to/my/priv-key"   The path to a PEM-formatted Private Key file to use for signing messages.
passphrase                "somepassword12345"      The passphrase for the Private Key
vtn_fingerprint           "fdfdfdfdfdgfsge"        The fingerprint for the VTN’s certificate to verify incoming messages
show_fingerprint          false                    Whether to print your own fingerprint on startup. Defaults to True.
ca_file                   "/path/to/my/ca-file"    The path to the PEM-formatted CA file for validating the VTN server’s certificate.
ven_id                    "someid"                 The ID for this VEN. If you leave this blank, a VEN_ID will be assigned by the VTN.
disable_signature         true                     Whether or not to sign outgoing messages using a public-private key pair in PEM format.
========================= ======================== ====================================================

