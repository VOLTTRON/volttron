.. _openadr:

========
Open ADR
========

OpenADR (Automated Demand Response) is a standard for alerting and responding to the
need to adjust electric power consumption in response to fluctuations in grid demand.
OpenADR communications are conducted between Virtual Top Nodes (VTNs) and Virtual End Nodes (VENs).

In this implementation, a VOLTTRON agent, OpenADRVenAgent, is made available as a
VOLTTRON service. It acts as a VEN, communicating with its VTN via EiEvent
and EiReport services in conformance with a subset of the OpenADR 2.0b specification.

A VTN server has also been implemented, with source code in the kisensum/openadr
folder of the volttron-applications git repository. As has been described below,
it communicates with the VEN and provides a web user interface for defining and reporting on Open ADR events.

The OpenADR 2.0b specification (http://www.openadr.org/specification) is available
from the OpenADR Alliance. This implementation also generally follows the DR program
characteristics of the Capacity Program described in Section 9.2 of the OpenADR
Program Guide (http://www.openadr.org/assets/openadr_drprogramguide_v1.0.pdf).

The OpenADR Capacity Bidding program relies on a pre-committed agreement about the
VEN’s load shed capacity. This agreement is reached in a bidding process transacted
outside of the OpenADR interaction, typically with a long-term scope, perhaps a month or longer.
The VTN can “call an event,” indicating that a load-shed event should occur in
conformance with this agreement. The VTN indicates the level of load shedding
desired, when the event should occur, and for how long. The VEN responds with
an “optIn” acknowledgment. (It can also “optOut,” but since it has been
pre-committed, an “optOut” may incur penalties.)


.. toctree::
    :glob:
    :maxdepth: 2

    *
