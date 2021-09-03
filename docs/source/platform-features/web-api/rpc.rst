.. container::
   :name: platforms-agents-rpc

   .. rubric:: Platforms Agents RPC
      :name: platforms-agents-rpc

RPC endpoints expose functionality associated with remote procedure calls
to agents running on a VOLTTRON platform.

-  All RPC endpoints require a JWT bearer token obtained through the
   ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

.. container::
   :name: get-platformsplatformagentsvip_identityrpc

   .. rubric:: GET /platforms/:platform/agents/:vip_identity/rpc
      :name: get-platformsplatformagentsvip_identityrpc

Get available remote procedure call endpoints for the specified agent.

Success will yield a dictionary with available RPC methods as keys and
routes for these as values.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<function_name>": "/platforms/:platform/agents/:vip_identity"/rpc/:function_name",
             "<function_name>": "/platforms/:platform/agents/:vip_identity"/rpc/:function_name",
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
   :name: get-platformsplatformagentsvip_identityrpcfunction_name

   .. rubric:: GET
      /platforms/:platform/agents/:vip_identity/rpc/:function_name
      :name: get-platformsplatformagentsvip_identityrpcfunction_name

Get parameters for an remote procedure call method.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "param1": <type>,
             "param2": <type>
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
   :name: post-platformsplatformagentsvip_identityrpcfunction_name

   .. rubric:: POST
      /platforms/:platform/agents/:vip_identity/rpc/:function_name
      :name: post-platformsplatformagentsvip_identityrpcfunction_name

Send an remote procedure call to an agent running on a VOLTTRON
platform.

The return value of an RPC call is defined by the agent, so this may be
a scalar value or another JSON object, for instance a list, dictionary,
etc.

**Request:**

-  Content Type: ``application/json``

-  Authorization: ``BEARER <jwt_access_token>``

-  Body:

   ::

      {
          "<param_name": <value>,
          "<param_name": <value>,
           ...
      }

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "return": <value>
         }

-  With valid BEARER token on failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

