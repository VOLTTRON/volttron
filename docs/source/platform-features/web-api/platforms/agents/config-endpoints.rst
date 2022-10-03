.. _Platforms-Agents-Configs-Endpoints:

==================================
Platforms Agents Configs Endpoints
==================================

Platforms Agents Configs endpoints expose functionality associated with agent configurations stored in the
VOLTTRON Configuration Store.

.. attention::
    All Platforms Configs endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:vip_identity/configs
=====================================================

Get routes to available configuration files for the specified agent.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response
--------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "route_options": {
                    ":config_file_name": "/platforms/:platform/agents/:vip_identity/configs/:config_file_name",
                    "<config_file_name>": "/platforms/:platform/agents/:vip_identity/configs/:config_file_name",
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

--------------------------------------------------------------------------------------------------

POST /platforms/:platform/agents/:vip_identity/configs/
=======================================================

Save a new configuration file to the config store.

The file name should be passed in the query parameter file-name.

The file should match the content type and contents which the VOLTTRON configuration store expects.
The configuration store currently accepts only JSON, CSV, or RAW files. The content type header should match the type
of file being sent (``application/json``, ``text/csv``, or ``text/plain`` respectively). This endpoint
will return 409 Conflict if the configuration file already exists. In this case, the user should use
``PUT /platforms/:platform/agents/:vip_identity/configs/:file_name`` if modification of the existing file is truly
intended.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``
* Content Type: ``application/json``, ``text/csv``, or ``text/plain``
* Body: Contents of configuration file.

Response
--------

* **With valid BEARER token on success:** ``201 Created``
    - Location: /platforms/:platform/agents/:vip_identity/configs/:file_name
    - Content Type: ``application/json``, ``text/csv``, or ``text/plain``
    - Body: Contents of the configuration file.

* **With valid BEARER token on failure:** ``400 Bad Request`` or ``409 Conflict``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

-----------------------------------------------------------------------------------------

DELETE /platforms/:platform/agents/:vip_identity/configs/
=====================================================================

Remove the configuration store for an agent. This endpoint will return ``409 Conflict`` if
the store for this agent is not empty. To remove all existing configurations for an agent from the config store
and delete the store, ``true`` must be passed to the ``all`` query parameter.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``
* Query Parameters:
    * ``all``: Boolean (default ``false``)

Response
--------

* **With valid BEARER token on success:** ``204 No Content``

* **With valid BEARER token on failure:** ``400 Bad Request`` or ``409 Conflict``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

------------------------------------------------------------------------------------------------

GET /platforms/:platform/agents/:vip_identity/configs/:config_name
==================================================================

Get a configuration file for the agent from the config store.

The configuration store can currently return JSON, CSV, or RAW files. If the Accept header is not set,
the configuration store will return JSON by default. If the client wishes to restrict the type of file received,
it should set the Accept header to the correct MIME type(s) (``application/json``, ``text/csv``, or ``text/plain``
respectively).

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response
--------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``, ``text/csv``, or ``text/plain``
    - Body: Contents of the configuration file.

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

-----------------------------------------------------------------------------------------

PUT /platforms/:platform/agents/:vip_identity/configs/:config_name
==================================================================

Overwrite a configuration file already in the config store.

The file should match the content type and contents which the VOLTTRON configuration store expects.
The configuration store currently accepts only JSON, CSV, or RAW files. The content type header should match the type
of file being sent (``application/json``, ``text/csv``, or ``text/plain`` respectively).

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``
* Content Type: ``application/json``, ``text/csv``, or ``text/plain``
* Body: Contents of configuration file.

Response
--------

* **With valid BEARER token on success:** ``204 No Content``

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

-----------------------------------------------------------------------------------------

DELETE /platforms/:platform/agents/:vip_identity/configs/:config_name
=====================================================================

Remove an existing configuration file for the agent from the config store.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response
--------

* **With valid BEARER token on success:** ``204 No Content``

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
