.. _Platforms-Agents-Running-Endpoints:

==================================
Platforms Agents Running Endpoints
==================================

Platforms Agents Running endpoints expose functionality associated with the running status of agents on the platform.
This includes determining whether an agent is running as well as starting and stopping the agent.

.. attention::
    All Platforms Agents Running endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:agent/running
==============================================

Retrieve the running status of the specified agent.

Request:
--------

    -  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

    *  **With valid BEARER token on success:** ``200 OK``
        - Content Type: application/json
        - Body:

          .. code-block:: json

                {
                    "status": true|false
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

PUT /platforms/:platform/agents/:agent/running
==============================================

Start the specified agent.

Accepts the ``restart`` query parameter to restart an agent. If the agent is already running, an error will be returned
if the restart parameter is not "true".

Request:
--------

    -  Authorization: ``BEARER <jwt_access_token>``


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

--------------

DELETE /platforms/:platform/agents/:agent/running
=================================================

Stop the specified agent.

Request:
--------

    -  Authorization: ``BEARER <jwt_access_token>``


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
