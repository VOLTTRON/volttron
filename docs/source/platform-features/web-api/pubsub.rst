.. container::
   :name: platforms-pubsub

   .. rubric:: Platforms PubSub
      :name: platforms-pubsub

PubSub endpoints expose functionality associated with publication and
subscription to topics on the VOLTTRON message bus.

-  All PubSub endpoints require a JWT bearer token obtained through the
   ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

.. container::
   :name: get-platforms/platform/pubsub

   .. rubric:: GET /platforms/:platform/pubsub
      :name: get-platformsplatformpubsub

Retrieve routes for message bus topics being monitored by this user of
the VUI API.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Body:

      ::

             [
                 "/platform/:platform/pubsub/:topic",
                 "/platform/:platform/pubsub/:topic",
                 ...
             ]

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

--------------

.. container::
   :name: get-platformsplatformpubsubtopic

   .. rubric:: GET /platforms/:platform/pubsub/:topic
      :name: get-platformsplatformpubsubtopic

Return the subscription to the topic.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token if subscription exists: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
         "topic": "<topic">,
         "push_bind": <bind_object> or null,
         "last_value": <last_value>,
         "number_of_subscribers": <number_of_open_subscriptions_to_topic>
         }

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

   ::

          {
              "error": "<Error Message>"
          }

-  With invalid BEARER token: ``401 Unauthorized``

--------------

.. container::
   :name: post-platformsplatformpubsubtopic

   .. rubric:: POST /platforms/:platform/pubsub/:topic
      :name: post-platformsplatformpubsubtopic

Create the specified subscription. Returns details. For publishing to
the topic, see the ``PUT /platforms/:platform/pubsub/:topic`` endpoint.

**Request:**

-  Content Type: ``application/json``

-  Authorization: ``BEARER <jwt_access_token>``

-  Body:

   ::

      {
          "push_bind": <bind_object> or null
      }

**Response:**

-  With valid BEARER token on success: ``201 Created``

   -  Content Type: ``application/json``

   -  Location: ``<resource_location>``

   -  Body:

      ::

         {
         "topic": "<topic>",
             "push_bind": <bind_object> or null,
             "last_value": "<last_value>",
             "access_token": <JWT_access_token_for_resource>
         }

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

--------------

.. container::
   :name: delete-platformsplatformpubsubtopic

   .. rubric:: DELETE /platforms/:platform/pubsub/:topic
      :name: delete-platformsplatformpubsubtopic

Unsubscribe to the topic.

NOTE: If multiple subscriptions are open to the same topic, the server
should remove this subscriber but keep the subscription resource open.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``204 No Content``

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

--------------

.. container::
   :name: put-platformsplatformpubsubtopic

   .. rubric:: PUT /platforms/:platform/pubsub/:topic
      :name: put-platformsplatformpubsubtopic

Publish to the specified topic on the specified platform and return
confirmation details.

The value given in the request body must contain the intended publish
body. This may be a single value or dictionary as expected by
subscribers to the topic. The publish_type will be used in formatting
the publish before it reaches the message bus. If a dictionary is
provided for the value and no publish_type is given, the publish will be
treated as a record type.

**Request:**

-  Content Type: ``application/json``

-  Authorization: ``BEARER <jwt_access_token>``

-  Body:

   ::

      {
          "headers": {<message_bus_headers>},
          "publish_type": "<datalogger|device|analysis|record>"
          "value": <value>
      }

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "number_of_subscribers": <number_of_subscribers>
         }

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

