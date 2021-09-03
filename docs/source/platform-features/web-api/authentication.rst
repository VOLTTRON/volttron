Authentication EndPoints
========================

The authentication endpoints are provided by the VOLTTRON platform web
service.

-  Authentication begins by obtaining a JWT bearer refresh token from
   the ``POST /authenticate`` endpoint. An access token is then obtained
   by providing the refresh token to the ``PUT /authenticate`` endpoint.
   The refresh token SHOULD be kept secure on the client side, and
   SHOULD NOT be provided to API call other than to
   ``PUT /authenticate``.

-  A JWT bearer access token is required to obtain resources or services
   provided by other API endpoints. The access token is obtained using
   the ``PUT /authenticate`` endpoint.

-  The refresh and access tokens will expire after some time and must be
   renewed using the ``POST /authenticate`` and ``PUT /authenticate``
   endpoints, respectively. Refresh tokens are longer lived than access
   tokens.

-  Any existing subscriptions may be cancelled by calling the
   ``DEL /authenticate`` endpoint.

----------------------------------------------------------------------------

.. container::
   :name: post-authenticate

   .. rubric:: POST /authenticate
      :name: post-authenticate

Built-in authorization endpoint for VOLTTRON web subsystem. Returns JWT
bearer refresh token with user’s claims. The refresh token will expire,
but will have a longer life than access tokens used for non-authenticate
APIs. The refresh token can then be provided to ``PUT /authenticate`` to
obtain a short-lived access token.

**Request:**

-  Content Type: ``application/json``

-  Body:

   ::

      {
          "username": "<username>",
          "password": "<password>"
      }

**Response:**

-  With valid username and password: ``200 OK``

   -  Content Type: ``text/plain``

   -  Body:

      ::

         <jwt_refresh_token>

-  With invalid username and password: ``401 Unauthorized``

--------------

.. container::
   :name: put-authenticate

   .. rubric:: PUT /authenticate
      :name: put-authenticate

Renew authorization token.

-  User provides refresh token (from ``POST /authenticate`` to obtain or
   renew an access token. A current access token MAY also be provided,
   as needed, to keep open any existing subscriptions.

-  Returns new JWT bearer access token. All subsequent requests should
   include the new token. The old bearer token is no longer considered
   valid.

**Request:**

-  Content Type: ``application/json``

-  Authorization: ``BEARER <jwt_refresh_token>``

-  Body (optional):

   ::

      {
          "current_access_token": "<jwt_access_token>"
      }

**Response:**

-  With valid refresh token: ``200 OK``

   -  Content Type: ``text/plain``

   -  Body:

      ::

         <new_jwt_access_token>

-  With invalid or mismatched username, password, or token:
   ``401 Unauthorized``

--------------

.. container::
   :name: delete-authenticate

   .. rubric:: DELETE /authenticate
      :name: delete-authenticate

Log out of API. Bearer token will be invalidated, and any subscriptions
will be cancelled.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid username and password: ``200 OK``

-  With invalid token: ``401 Unauthorized``

--------------
