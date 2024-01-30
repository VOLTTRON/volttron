.. _Platforms-Endpoints:

===================
Platforms Endpoints
===================


Platforms endpoints expose functionality associated with specific
VOLTTRON platforms.

As all functionality of VOLTTRON is the purview of one or another
platform, the /platforms tree forms the core of the VOLTTRON User
Interface API. Other top level partitions of the API consist of
convenience methods which refer to endpoints within /platforms.

The platforms tree currently provides access to four major categories of endpoint, each of which are described in detail
through the following links:

* :ref:`Agents <Platforms-Agents-Endpoints>`: Endpoints pertaining to a specific agent (e.g. RPC)
* :ref:`Devices <Platforms-Devices-Endpoints>`: Endpoints for discovering, getting, and setting data about the current
  state of devices on the platform.
* :ref:`Historians <Platforms-Historians-Endpoints>`: Endpoints for querying data from historians.
* :ref:`PubSub <Platforms-Pubsub-Endpoints>`: Endpoints for subscription and publication to message bus topics.
* :ref:`Status <Platforms-Status-Endpoints>`: Endpoints for retrieving and clearing status of all agents on the
  platform.

.. attention::
    All endpoints in this tree require authorization using a JWT bearer
    token provided by the ``POST /authenticate`` or ``PUT /authenticate``
    endpoints.
--------------------------------------------------------------------------------

GET /platforms
==============

Obtain routes for connected platforms.

A ``GET`` request to the ``/platforms`` endpoint will return a JSON object containing routes to available platforms.
Available routes are included in a "route_options" object. The keys of the "route_options" object are the name of each
platform which is currently reachable through the API, and the values contain a route to an endpoint for the platform.

Request:
--------

- Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "route_options": {
                    "<platform1>": "/platforms/<platform1>",
                    "<platform2>": "/platforms/<platform2>"
                }
            }

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
             "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``
---------------------------------------------------------------------------------------------------------------------

GET /platforms/:platform
========================

Obtain routes available for a specific platform.

A ``GET`` request to the ``/platforms/:platform`` endpoint (where ``:platform`` is the instance name of a specific
platform) will return a JSON object containing routes to endpoints which are available for the requested platform.
Available routes are included in a "route_options" object. The keys of the "route_options" object are the name of each
endpoint which the platform supports, and the values contain a route to that endpoint for this platform. The currently
implemented possibilities include: :ref:`agents <Platforms-Agents-Endpoints>`,
:ref:`devices <Platforms-Devices-Endpoints>`, :ref:`historians <Platforms-Historians-Endpoints>`,
:ref:`pubsub <Platforms-Pubsub-Endpoints>` and :ref:`status <Platforms-Status-Endpoints>`.

Request:
--------

- Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "route_options": {
                    "<endpoint1_name>": "/platforms/:platform/<endpoint1_name>",
                    "<endpoint2_name>": "/platforms/:platform/<endpoint2_name>"
                }
            }

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
             "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

.. toctree::
    :hidden:

    Agents <platforms/agent-endpoints>
    Configs <platforms/config-endpoints>
    Devices <platforms/device-endpoints>
    Health <platforms/health-endpoints>
    Historians <platforms/historian-endpoints>
    Pubsub <platforms/pubsub-endpoints>
    Status <platforms/status-endpoints>
