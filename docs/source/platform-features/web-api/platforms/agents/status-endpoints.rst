.. _Platforms-Agents-Status-Endpoints:

=================================
Platforms Agents Status Endpoints
=================================

Platforms Agents Status endpoints expose functionality associated with getting status for
a single agent running on a VOLTTRON platform. Only a GET method is currently implemented.

.. attention::
    All Platforms Agents Status endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:agent/status
===============================

Get status for a specific agent on the platform.

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
                 "name": "<wheel_name>",
                 "uuid": "<uuid>",
                 "tag": "<tag>",
                 "priority": "<int>",
                 "running": <true|false>,
                 "enabled": <true|false>,
                 "pid": <int>,
                 "exit_code": <null|int>
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
