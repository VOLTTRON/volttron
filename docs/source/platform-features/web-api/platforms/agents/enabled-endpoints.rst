.. _Platforms-Agents-Enabled-Endpoints:

==================================
Platforms Agents Enabled Endpoints
==================================

Platforms Agents Enabled endpoints expose functionality associated with the enabled status of agents on the platform.
This includes determining whether an agent is enabled (and with what start priority), as well as enabling and disabling
the agent.

.. attention::
    All Platforms Agents Enabled endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:agent/enabled
==============================================

Retrieve the enabled status and priority of the specified agent.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

*  **With valid BEARER token on success:** ``200 OK``
    - Content Type: application/json
    - Body:

      .. code-block:: json

            {
                "status": true|false,
                "priority": int
            }
* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``


--------------

PUT /platforms/:platform/agents/:agent/enabled
==============================================

Enable the specified agent.

Accepts the ``priority`` query parameter to set the start priority of the agent. Allowable prioirties range from 0 to
99. If the priority is not given, the agent will be enabled with a priority of 50.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``


Response:
---------

* **With valid BEARER token on success:** ``204 No Content``

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

--------------

DELETE /platforms/:platform/agents/:agent/enabled
=================================================

Disable the specified agent.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``


Response:
---------

*  **With valid BEARER token on success:** ``204 No Content``

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

    self
