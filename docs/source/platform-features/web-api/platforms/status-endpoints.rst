.. _Platforms-Status-Endpoints:

==========================
Platforms Status Endpoints
==========================

Platforms Status endpoints expose functionality associated with getting and resetting the status
of all agents running on a VOLTTRON platform.

.. attention::
    All Platforms Status endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/status
===============================

Get status for all agents on the platform.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: json

            {
                "<vip_identity>": {
                    "name": "<wheel_name>",
                    "uuid": "<uuid>",
                    "tag": "<tag>",
                    "priority": "<int>",
                    "running": <true|false>,
                    "enabled": <true|false>,
                    "pid": <int>,
                    "exit_code": <null|int>
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

--------------

DELETE /platforms/:platform/status
==================================

Clear status for all agents on the platform.  This will not affect the status of running agents,
but will clear exit codes and process ids for agents which have been previously running and are now stopped.

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
