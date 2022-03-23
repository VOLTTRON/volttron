.. _Authentication-Endpoints:

========================
Authentication EndPoints
========================

The VOLTTRON Web API requires the use of bearer tokens to access resources.  These tokens
are JSON Web Tokens (JWT) and are provided by the two ``/authenticate`` endpoints (``POST``
and ``PUT``).  Two classes of token are provided to the user:

- Refresh Tokens:
    Refresh tokens are long-lived, and used can be used to obtain a new short-lived access
    token. Refresh tokens are obtained by providing a valid username and password to the
    ``POST /authenticate`` endpoint. The refresh token SHOULD be kept secure on the
    client side, and SHOULD NOT be provided to API call other than to
    ``PUT /authenticate``.

- Access Tokens:
    An access token are short-lived tokens required to obtain resources or services provided
    by other API endpoints. The access token is obtained using the ``PUT /authenticate``
    endpoint. For convenience, an inital access token is provided by the
    ``POST /authenticate`` endpoint as well, but as use the ``POST`` method requires
    sending credentials to the server, this should only be used on the first call, with
    ``PUT`` being used thereafter to obtain new access tokens until the refresh token has
    also expired.

.. note:: Authentication begins by obtaining a JWT bearer refresh token from the
    ``POST /authenticate`` endpoint. An initial access token is provided by this endpoint
    as well. Subsequent access tokens are then obtained by providing the refresh token to the
    ``PUT /authenticate`` endpoint without resending of credentials.

----------------------------------------------------------------------------

POST /authenticate
==================

Provide authentication credentials to receive refresh token.

The user provides a username and password in the request body. If authentication succeeds,
the endpoint will returna a JWT bearer refresh token with user’s claims. An initial access
token is also returned. The refresh token can then be provided to ``PUT /authenticate``
to obtain new short-lived access tokens, as needed, without sending the username and
password again until the refresh token expires.

Request:
--------
- Content Type: ``application/json``
- Body:

  .. code-block:: JSON

        {
            "username": "<username>",
            "password": "<password>"
        }

Response:
---------

* **With valid username and password:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "refresh_token": "<jwt_refresh_token>",
                "access_token": "<jwt_access_token>"
            }

* **With invalid username and password:** ``401 Unauthorized``

--------------

PUT /authenticate
=================

Renew access token.

The user provides a valid refresh token (provided by ``POST /authenticate``) in the
Authorization header to obtain a fresh access token. A current access token MAY also
be provided, as needed, in the request body to keep open any existing subscriptions.
All subsequent requests to any endpoint should include the new token, and the old
access token should be discarded.

Request:
--------

- Content Type: ``application/json``
- Authorization: ``BEARER <jwt_refresh_token>``
- Body (optional):

  .. code-block:: JSON

        {
          "current_access_token": "<jwt_access_token>"
        }

Response:
---------

* **With valid refresh token:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "access_token": "<new_jwt_access_token>"
            }

* **With invalid or mismatched username, password, or token:**
   ``401 Unauthorized``
