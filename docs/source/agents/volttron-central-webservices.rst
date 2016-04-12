===============================================
VOLTTRON Central Web Services Api Documentation
===============================================

VOLTTRON Central (VC) is meant to be the hub of communcation within a cluster of
VOLTTRON instances. VC exposes a
`JSON-RPC 2.0 <http://www.jsonrpc.org/specification>`_ based api that allows
a user to control multple instances of VOLTTRON.


Why JSON-RPC
============

SOAP messaging is unfriendly to many developers, especially those wanting to
make calls in a browser from AJAX environment. We have therefore have
implemented a JSON-RPC API capability to VC, as a more JSON/JavaScript
friendly mechanism.


How the API is Implemented
==========================

* All calls are made through a POST.
* All calls (not including the call to authenticate) will
  include an authorization token (a json-rpc extension).

JSON-RPC Request Payload
========================

All posted JSON payloads will look like the following block:

.. code-block:: JSON

    {
        "jsonrpc": "2.0",
        "method": "method_to_invoke",
        "params": {
            "param1name": "param1value",
            "param2name": "param2value"
        },
        "id": "unique_message_id",
        "authorization": "server_authorization_token"
    }

As an alternative, the params can be an array as illistrated by the following:

.. code-block:: JSON

    {
        "jsonrpc": "2.0",
        "method": "method_to_invoke",
        "params": [
            "param1value",
            "param2value"
        ],
        "id": "unique_message_id",
        "authorization": "server_authorization_token"
    }

For full documentation of the Request object please see section 4 of the
`JSON-RPC 2.0 <http://www.jsonrpc.org/specification>`_ specification.

JSON-RPC Response Payload
=========================

All responses shall have either an either an error response or a result
response.  The result key shown below can be a single instance of a json
type, an array or a JSON object.

A result response will have the following format:

.. code-block:: JSON

    {
        "jsonrpc": "2.0",
        "result": "method_results",
        "id": "sent_in_unique_message_id"
    }

An error response will have the following format:

.. code-block:: JSON

    {
        "jsonrpc": "2.0",
        "error": {
            "code": "standard_code_or_extended_code",
            "message": "error message"
        }
        "id": "sent_in_unique_message_id_or_null"
    }

For full documenation of the Response object please see section 5 of the
`JSON-RPC 2.0 <http://www.jsonrpc.org/specification>`_ specification.

JSON-RPC Data Objects
=====================

.. csv-table:: Platform
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."

.. csv-table:: PlatformDetails
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."
#    "agents",
#    "devices"

.. csv-table:: Agent
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the agent."
    "name", "string", "Defaults to the agentid of the installed agent"
    "tag", "string", "A shortcut that can be used for referencing the agent"
    "priority", "int", "If this is set the agent will autostart on the instance."
    "process_id", "int", "The process id or null if not running."
    "status", "string", "A status string made by the status rpc call, on an agent."


.. csv-table:: DiscoveryRegistratyEntry
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "name",
    "discovery_address":

.. csv-table:: AdvancedRegistratyEntry
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "name",
    "vip_address":
# separate fields???

    "
    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."
    "agents",
    "devices",

.. csv-table:: Agent
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."
    "agents",
    "devices"

.. csv-table:: Building
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."
    "agents",
    "devices"

.. csv-table:: Device
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."
    "agents",
    "devices"

.. csv-table:: PlatformDetails
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "uuid", "string", "A unique identifier for the platform."
    "name", "string", "A user defined string for the platform."
    "status", "Status", "A status object for the platform."
    "agents",
    "devices",

.. csv-table:: Status
    :header: "Key", "Type", "Value"
    :widths: 10, 10, 40

    "status", "string", "A value of GOOD, BAD, UNKNOWN, SUCCESS, FAIL"
    "context", "string", "Provides context about what the status means (optional)"


JSON-RPC API Methods
====================

.. csv-table:: Methods
    :header: "method", "parameters", "returns"
    :widths: 10, 10, 40

    "get_authentication", "(username, password)", "authentication token"



Messages
========

Register A Volttron Platform Instance (Using Discovery)
    .. code-block:: Python

        # POST /api/jsonrpc
        {
            "jsonrpc": "2.0",
            "method": "register_instance",
            "params": {
                "uri": "127.0.0.2:8080",
                "display_name": "foo" # Optional
            }
            "authorization": "someAuthorizationToken",
            "id": #

        }

    Success
        .. code-block:: Python

            200 OK
            {
                "jsonrpc": "2.0",
                "result": {
                    "status": {
                        "code": "SUCCESS"
                        "context": "Registered instance foo" # or the uri if not specified.
                    }
                },
                "id": #
            }

    Failure Unavailable
        .. code-block:: Python

            200 OK
            {
                "jsonrpc": "2.0",
                "result": {
                    "status": {
                        "code": "ERROR"
                        "context": "Could not connect to 127.0.0.2:8080"
                    }
                },
                "id": #
            }

    Failure No Platform Agent
        .. code-block:: Python

            200 OK
            {
                "jsonrpc": "2.0",
                "result": {
                    "status": {
                        "code": "ERROR"
                        "context": "Could not connect to 127.0.0.2:8080"
                    }
                },
                "id": #
            }




Request Registration of an External Platform (Using Discovery)
    .. code-block:: Python

        # POST /api/jsonrpc
        {
            "jsonrpc": "2.0",
            "method": "register_platform",
            "params": {
                "uri": "127.0.0.2:8080"
            }
            "authorization": "someAuthorizationToken",
            "id": #
        }



Retrieve Authorization Token
    .. code-block:: Python

        {
            "jsonrpc": "2.0",
            "method": "get_authorization",
            "params": {
                "username": "dorothy",
                "password": "toto123"
            },
            "id": #
        }

    Response Success
        .. code-block:: Python

            {
                "jsonrpc": "2.0",
                "method": "list_platforms",
                "authorization": "someAuthorizationToken",
                "id": #
            }

    Failure
        Http Status Code 401

Retrieve Managed Instances
    .. code-block:: Python

        #POST /jsonrpc
        {
            "jsonrpc": "2.0",
            "method": "list_platforms",
            "authorization": "someAuthorizationToken",
            "id": #
        }

    Response Success
        .. code-block:: Python

            200 OK
            {
                "jsonrpc": "2.0",
                "result": [
                    {
                        "name": "platform1",
                        "uuid": "abcd1234-ef56-ab78-cd90-efabcd123456"
                    },
                    {
                        "name": "platform2",
                        "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc"
                    },
                    {
                        "name": "platform3",
                        "uuid": "0000aaaa-1111-bbbb-2222-cccc3333dddd"
                    }
                ],
                "id": #
            }

Retrieve Installed Agents From platform1
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.abcd1234-ef56-ab78-cd90-efabcd123456.list_agents",
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
200 OK
{
    "jsonrpc": "2.0",
    "result": [
        {
            "name": "HelloAgent",
            "uuid": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
        },
        {
            "name": "RunningAgent",
            "uuid": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
        },
        {
            "name": "StoppedAgent",
            "uuid": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
        }
    ],
    "id": #
}

Start An Agent
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.start_agent",
    "params": ["a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"],
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
200 OK
{
    "jsonrpc": "2.0",
    "result": {
        "process_id": 1000,
        "return_code": null
    },
    "id": #
}

Stop An Agent
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.stop_agent",
    "params": ["a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"],
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
200 OK
{
    "jsonrpc": "2.0",
    "result": {
        "process_id": 1000,
        "return_code": 0
    },
    "id": #
}

Remove An Agent
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.remove_agent",
    "params": ["a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"],
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
200 OK
{
    "jsonrpc": "2.0",
    "result": {
        "process_id": 1000,
        "return_code": 0
    },
    "id": #
}

Retrieve Running Agents
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.status_agents",
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
200 OK
{
    "jsonrpc": "2.0",
    "result": [
        {
            "name": "RunningAgent",
            "uuid": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
            "process_id": 1234,
            "return_code": null
        },
        {
            "name": "StoppedAgent",
            "uuid": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
            "process_id": 1000,
            "return_code": 0
        }
    ],
    "id": #
}

Retrieve An Agent's RPC Methods
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.agents.uuid.a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6.inspect",
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
200 OK
{
    "jsonrpc": "2.0",
    "result": [
        {
            "method": "sayHello",
            "params": {
                "name": "string"
            }
        }
    ],
    "id": #
}

Perform Agent Action
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.agents.uuid.a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6.methods.say_hello",
    "params": {
        "name": "Dorothy"
    },
    "authorization": "someAuthorizationToken",
    "id": #
}

Success Response
200 OK
{
    "jsonrpc": "2.0",
    "result": "Hello, Dorothy!",
    "id": #
}

Install Agent
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "platforms.uuid.0987fedc-65ba-43fe-21dc-098765bafedc.install",
    "params": {
        files: [
            {
                "file_name": "helloagent-0.1-py2-none-any.whl",
                "file": "data:application/octet-stream;base64,..."
            },
            {
                "file_name": "some-non-wheel-file.txt",
                "file": "data:application/octet-stream;base64,..."
            },
            ...
        ],
    }
    "authorization": "someAuthorizationToken",
    "id": #
}

Success Response
200 OK
{
    "jsonrpc": "2.0",
    "result": {
        [
            {
                "uuid": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6"
            },
            {
                "error": "Some error message"
            },
            ...
        ]
    },
    "id": #
}
