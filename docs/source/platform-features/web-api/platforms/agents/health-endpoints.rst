.. _Platforms-Agents-Health-Endpoints:

==================================
Platforms Agents Health Endpoints
==================================

Platforms Agents Health endpoints expose functionality associated with getting health information for
a single agent running on a VOLTTRON platform.

.. attention::
    All Platforms Agents Health endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:agent/health
==============================================

Retrieve health information for the specified agent.

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
                "status": "<status_message>",
                "context": {"<agent_specific_keys>": "agent_specific_values>"},
                "last_updated": "<date_time>"
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

    self
