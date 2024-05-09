.. _Platforms-Agents-Endpoints:

==========================
Platforms Agents Endpoints
==========================

Platforms Agents endpoints expose functionality associated with applications
running on a VOLTTRON platform.

Platforms Agents endpoints currently include:
    * :ref:`Configs <Platforms-Agents-Configs-Endpoints>`: Endpoints for managing the configuration store for agents
      on the platform.
    * :ref:`Enabled <Platforms-Agents-Enabled-Endpoints>`: Endpoints for enabling, disabling, and setting the start
      priority of agents on the platform.
    * :ref:`Running <Platforms-Agents-Running-Endpoints>`: Endpoints for starting and stopping agents on the platform.
    * :ref:`RPC <Platforms-Agents-Rpc-Endpoints>`: Endpoints allowing, discovery, inspection, and calling of remote
      procedure calls to agents running on the platform.
    * :ref:`Status <Platforms-Agents-Status-Endpoints>`: Endpoints for determining the status information for an agent
      running on the platform.
    * :ref:`Tag <Platforms-Agents-Tag-Endpoints>`: Endpoints for getting, setting, and deleting the tag of agents.

.. attention::
    All Platforms Agents endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents
===============================

Return routes for the agents installed on the platform.

Accepts a two query parameters:

* ``agent-state`` accepts one of three string values:
    - *"running"* (default): Returns only those agents which are currently running.
    - *"installed"*: Returns all installed agents.
    - *"packaged"*: Returns filenames of packaged agents on the platform which can be installed.
* ``include-hidden`` (default=False): When True, includes system agents which would not normally be displayed by vctl status.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "route_options": {
                    "<vip_identity>": "/platforms/:platform/agents/:vip_identity",
                    "<vip_identity>": "/platforms/:platform/agents/:vip_identity"
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

------------------------------------------------------------------------------------------

GET /platforms/:platform/agents/:vip-identity
=============================================

Return routes for the supported endpoints for an agent installed on the platform.
Currently implemented endpoints include :ref:`RPC <Platforms-Agents-Rpc-Endpoints>`.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "route_options": {
                    "<vip_identity>": "/platforms/:platform/agents/:vip_identity/<endpoint1_name>",
                    "<vip_identity>": "/platforms/:platform/agents/:vip_identity/<endpoint2_name>"
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

    ConfigStore <agents/config-endpoints>
    Enabled <agents/enabled-endpoints>
    Health <agents/health-endpoints>
    RPC <agents/rpc-endpoints>
    Running <agents/running-endpoints>
    Status <agents/status-endpoints>
    Tag <agents/tag-endpoints>
