.. _Platforms-Pubsub-Endpoints:

==========================
Platforms PubSub Endpoints
==========================

PubSub endpoints expose functionality associated with publication and
subscription to topics on the VOLTTRON message bus.

.. attention::
    All endpoints in this tree require authorization using a JWT bearer access token provided by the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

GET /platforms/:platform/pubsub
===============================

Retrieve routes for message bus topics being monitored by this user of
the VUI API.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

-  **With valid BEARER token on success:** ``200 OK``
    -  Body:

       .. code-block:: JSON

            [
                "/vui/platform/:platform/pubsub/:topic",
                "/vui/platform/:platform/pubsub/:topic"
            ]

-  **With valid BEARER token on failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``

--------------

GET /platforms/:platform/pubsub/:topic
======================================

Return a subscription to the topic.

.. attention::

    Unique to the API, this endpoint is used to open a websocket which allows the
    subscription data to be pushed to the client as it arrives on the message bus. As such, several additional headers are
    required in the request, and the client will need to appropriately process the response in accordance with the
    websocket protocol to keep the websocket open and process incoming push data.

Request:
--------

- Authorization: ``BEARER <jwt_access_token>``
- Connection: ``Upgrade``
- Upgrade: ``websocket``
- Sec-WebSocket-Key: ``<calculated at runtime>``
- Sec-WebSocket-Version: ``13``
- Sec-WebSocket-Extensions: ``permessage-deflate; client_max_window_bits``

Response:
---------

-  **With valid BEARER token on success:** ``101 Switching Protocols``

   - Upgrade: ``websocket``
   - Connection: ``Upgrade``
   - Sec-WebSocket-Version: ``13``
   - Sec-WebSocket-Accept: ``<calculated at runtime>``

-  **With valid BEARER token on failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

          {
              "error": "<Error Message>"
          }

-  **With invalid BEARER token:** ``401 Unauthorized``

-------------

PUT /platforms/:platform/pubsub/:topic
======================================

Publish to the specified topic on the specified platform and return
confirmation details.

The value given in the request body must contain the intended publish
body. The request body should be a JSON object where the ``headers`` key contains headers for the VOLTTRON message bus
and the ``message`` key contains the message body. The message body may be a single value, JSON object, or other value
as expected by subscribers to the topic.

Request:
--------

-  Content Type: ``application/json``

-  Authorization: ``BEARER <jwt_access_token>``

-  Body:

   .. code-block:: JSON

      {
          "headers": {<message_bus_headers>},
          "message": <message body>
      }

Response:
---------

-  **With valid BEARER token on success:** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "number_of_subscribers": <number_of_subscribers>
         }

-  **With valid BEARER token on failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``

---------------

DELETE /platforms/:platform/pubsub/:topic
=========================================

Unsubscribe to the topic.

.. attention::
    If multiple subscriptions are open to the same topic, the server
    will remove this subscriber but keep the subscription resource open.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

*  **With valid BEARER token on success:** ``204 No Content``

*  **With valid BEARER token on failure:** ``400 Bad Request``
    -  Content Type: ``application/json``

    -  Body:

       .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

-  **With invalid BEARER token:** ``401 Unauthorized``
