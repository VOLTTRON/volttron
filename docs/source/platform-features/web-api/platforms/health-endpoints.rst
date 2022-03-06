.. _Platforms-Health-Endpoints:

==========================
Platforms Health Endpoints
==========================

Platforms Health endpoints expose functionality associated with getting health information for
all agents running on a VOLTTRON platform.

.. attention::
    All Platforms Agents Health endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/health
==============================================

Retrieve health information for all agents on the platform.

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
            "<vip_identity>": {
                "peer": "<peer_name>",
                "service_agent": true|false,
                "connected": "<date_time>",
                "last_heartbeat": "<date_time>",
                "message": "<message>"
            },
            ...
        }
* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``
