===============================================
VOLTTRON Central Web Services Api Documentation
===============================================

VOLTTRON Central is meant to be the hub of communcation within a cluster of
VOLTTRON instances.  Through it's api one can control platforms at different
locations throughout an organization.  This document describes the json api
exposed via the VOLTTRON web service module.

Expectation of API
==================
* All communication with the api will be done through a post request.
* All messages sent to the api will be according to `jsonrpc-2.0 protocol <http://www.jsonrpc.org/specification>`_.

Messages
========

Retrieve Authorization Token
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
{
    "jsonrpc": "2.0",
    "method": "list_platforms",
    "authorization": "someAuthorizationToken",
    "id": #
}

Failure
Http Response Code 401

Retrieve Managed Instances
POST /jsonrpc
{
    "jsonrpc": "2.0",
    "method": "list_platforms",
    "authorization": "someAuthorizationToken",
    "id": #
}

Response Success
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
