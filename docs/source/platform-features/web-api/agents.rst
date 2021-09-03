.. container::
   :name: platforms-agents

   .. rubric:: Platforms Agents
      :name: platforms-agents

Agents endpoints expose functionality associated with applications
running on a VOLTTRON platform.

-  All Agent endpoints require a JWT bearer token obtained through the
   ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

.. container::
   :name: get-platformsplatformagents

   .. rubric:: GET /platforms/:platform/agents
      :name: get-platformsplatformagents

Return routes for the agents installed on the platform.

Accepts a query parameter ``packaged``, which is false by default. If
true, this endpoint will instead return filenames of packaged agents on
the platform which can ben installed.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<vip_identity>": "/platforms/:platform/agents/:vip_identity",
             "<vip_identity>": "/platforms/:platform/agents/:vip_identity",
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
