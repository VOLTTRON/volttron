Platforms
=========

Platforms endpoints expose functionality associated with specific
VOLTTRON platforms.

As all functionality of VOLTTRON is the purview of one or another
platform, the /platforms tree forms the core of the VOLTTRON User
Interface API. Other top level partitions of the API consist of
convenience methods which refer to endpoints within /platforms.

-  All endpoints in this tree require authentication using a JWT bearer
   token provided by the ``POST /authenticate`` or ``PUT /authenticate``
   endpoints.

--------------

.. container::
   :name: get-platforms

   .. rubric:: GET /platforms
      :name: get-platforms

Get routes for connected platforms.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<platform>": "/platforms/:platform",
             "<platform>": "/platforms/:platform",
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

