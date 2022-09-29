.. _Platforms-Agents-Tag-Endpoints:

==============================
Platforms Agents Tag Endpoints
==============================

Platforms Agents Tag endpoints expose functionality associated with tags given to agents on the platform.
Agent tags provide a short name which can be used to identify an agent.

.. attention::
    All Platforms Agents Tag endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:agent/tag
==========================================

Retrieve the tag of the specified agent.

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
                "tag": "<tag>"
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

PUT /platforms/:platform/agents/:agent/tag
==========================================

Set the tag to an agent installed on the platform.

Request:
--------

* Authorization:  ``BEARER <jwt_token>``
* Content Type: ``application/json``
* Body:

  .. code-block:: json

        {
            "tag": "<tag>"
        }


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

DELETE /platforms/:platform/agents/:agent/tag
=============================================

Remove the tag from an agent installed on a VOLTTRON platform.

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
