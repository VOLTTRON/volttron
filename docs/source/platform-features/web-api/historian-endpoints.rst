===================
Historian Endpoints
===================

.. container::
   :name: platforms-historians

   .. rubric:: Platforms Historians
      :name: platforms-historians

Platform Historian endpoints expose functionality related to historians
running on a VOLTTRON platform.

-  All Agent Control endpoints require a JWT bearer token obtained
   through the ``POST /authenticate`` or ``PUT /authenticate``
   endpoints.

-  Endpoints in the
   ``/platforms/:platform/historians/:historian/topics`` tree utilize
   the existing per-topic interface provided by the VOLTTRON historian
   query() method.

The ``POST /platforms/:platform/historians/:historian/history`` endpoint
will require further definition. This is intended to provide a richer
query API utilizing GraphQL for the system as a whole. GraphQL
recommends providing both ``GET`` and ``POST`` methods for queries. As
the utility of ``GET`` is frequently limited by the allowed size of
querystrings, a ``GET`` endpoints has not, however, been defined at this
time.

--------------

.. container::
   :name: get-historians

   .. rubric:: GET /platforms/:platform/historians
      :name: get-historians

Retrieve routes to historians on the platform.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<vip_identity>": "/platform/historians/:historian",
             "<vip_identity>": "/platform/historians/:historian",
             ...
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
   :name: get-platformsplatformhistorianshistorian

   .. rubric:: GET /platforms/:platform/historians/:historian
      :name: get-platformsplatformhistorianshistorian

Retrieve routes for an historian.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "topics": "/platforms/:platform/historians/:historian/topics",
             "metatdata": "/platforms/:platform/historians/:historian/metadata",
             "records": "/platforms/:platform/historians/:historian/records"
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
   :name: get-platformsplatformhistorianshistoriantopics

   .. rubric:: GET /platforms/:platform/historians/:historian/topics
      :name: get-platformsplatformhistorianshistoriantopics

Query topics from the historian.

By default, the response will contain all topics in the historian. The
``pattern`` query parameter may be used to filter the results. The
``aggregate`` query parameter may be used to retrieve aggregate topics.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<topic>": {
                         "id": <id>,
                         "route": "/platforms/:platform/historians/:historian/topics/:topic"
                        },
             "<topic>": {
                         "id": <id>,
                         "route": "/platforms/:platform/historians/:historian/topics/:topic"
                        },
             ...
         }

   -  Body (with ``aggregate``):

      ::

             [
                 {
                     "topic_name":<topic>,
                     "aggregation_type": <aggregation_type>,
                     "aggregation_time_period": <aggregation_time_period>,
                     "metadata": <metadata>
                 },
                 {
                     "topic_name":<topic>,
                     "aggregation_type": <aggregation_type>,
                     "aggregation_time_period": <aggregation_time_period>,
                     "metadata": <metadata>
                 },
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
   :name: get-platformsplatformhistorianshistoriantopicstopic

   .. rubric:: GET
      /platforms/:platform/historians/:historian/topics/:topic
      :name: get-platformsplatformhistorianshistoriantopicstopic

Query data for a topic.

Several query parameters may be used to refine the results:

-  start: datetime of the start of the query. None for the beginning of
   time.

-  end: datetime of the end of of the query. None for the end of time.

-  skip: skip this number of results (for pagination)

-  count: return at maximum this number of results (for pagination)

-  order: “FIRST_TO_LAST” for ascending time stamps, “LAST_TO_FIRST” for
   descending time stamps.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "values": [
                 {"datetime": <datetime>: "value: <value>},
                 {"datetime": <datetime>: "value: <value>},
         '       ...
             ],
         '   "metadata": {
                 "key1": value1,
         '       "key2": value2,
         '        ...
             }
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
   :name: post-platformsplatformhistorianshistoriantopicstopic

   .. rubric:: POST
      /platforms/:platform/historians/:historian/topics/:topic
      :name: post-platformsplatformhistorianshistoriantopicstopic

Insert records into the historian.

The request body should contain a list of JSON objects matching the
format of the record type being inserted (e.g.: record, analysis,
datalogger, devices).

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

-  Content Type: ``application/json``

-  Body:

   ::

      [
          {
          <record>
          }
      ]

**Response:**

-  With valid BEARER token on success: ``201 Created``

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
   :name: post-platformsplatformhistorianshistoriantopicstopic

   .. rubric:: POST /platforms/:platform/historians/:historian/history
      :name: post-platformsplatformhistorianshistorianhistory

A GraphQL interface to history on this historian. The request body
should contain a JSON object following GraphQL semantics.

This API requires further definition.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

-  Content Type: ``application/json``

-  Body:

   ::

          <graphql_query>

**Response:**

-  With valid BEARER token on success: ``200 OK``

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

