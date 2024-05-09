.. _Platforms-Agents-Rpc-Endpoints:

==============================
Platforms Agents RPC Endpoints
==============================


RPC endpoints expose functionality associated with remote procedure calls to agents running on a VOLTTRON platform.


.. attention::
    All RPC endpoints require a JWT bearer token obtained through the ``POST /authenticate``
    or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/agents/:vip_identity/rpc
=================================================

Get available remote procedure call endpoints for the specified agent.

Success will yield a JSON object with available RPC methods as keys and routes for these as values.

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
                    "<function_name>": "/platforms/:platform/agents/:vip_identity/rpc/:function_name",
                    "<function_name>": "/platforms/:platform/agents/:vip_identity/rpc/:function_name"
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

--------------

GET /platforms/:platform/agents/:vip_identity/rpc/:function_name
================================================================

Inspect a remote procedure call method.

.. note::

    The information for this endpoint is provided by the `inspect` module. Not all information is available for all
    RPC methods. If the data is not available, the key will be absent from the response.

    ``kind`` is an enumeration where the values may be `POSITIONAL_OR_KEYWORD`, `POSITIONAL_ONLY`, or
    `KEYWORD_ONLY`.

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
                "params": {
                    "param_name_1": {
                        "kind": "POSITIONAL_OR_KEYWORD",
                        "default": "<type>"
                    },
                    "param_name_2": {
                        "kind": "KEYWORD_ONLY",
                        "default": null
                    }
                },
                "doc": "Docstring from the method, if available.",
                "source": {
                    "file": "<path/to/source/file.py>",
                    "line_number": "<line_number>"
                }
                "return": "<return_type>"
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

POST /platforms/:platform/agents/:vip_identity/rpc/:function_name
=================================================================


Send an remote procedure call to an agent running on a VOLTTRON platform.

Parameters provided in the request body are passed as arguments to the RPC method. The return value of an RPC call is
defined by the agent, so this may be a scalar value or another JSON object, for instance a list, dictionary, etc.

Request:
--------

* Content Type: ``application/json``
* Authorization: ``BEARER <jwt_access_token>``
* Body:

  .. code-block:: JSON

        {
            "<param_name>": "<value>",
            "<param_name>": "<value>"
        }

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body: Any, as defined by the RPC method.

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
