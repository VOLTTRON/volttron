.. _Authentication-Endpoints:

========================
Authentication EndPoints
========================

The VOLTTRON Web API requires the use of bearer tokens to access resources.  These tokens
are JSON Web Tokens (JWT) and are provided by the ``/authenticate`` endpoints: ``POST`` to log
in, ``PUT`` to renew, and ``DELETE`` to log out.  Two classes of token are provided to the user:

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

Both tokens of a login, and every access token later renewed from its refresh token, belong to
one login session. ``DELETE /authenticate`` ends that session: every one of its tokens is refused
from then on, whichever of them was presented.

.. note:: Authentication begins by obtaining a JWT bearer refresh token from the
    ``POST /authenticate`` endpoint. An initial access token is provided by this endpoint
    as well. Subsequent access tokens are then obtained by providing the refresh token to the
    ``PUT /authenticate`` endpoint without resending of credentials. When the client is
    finished, or a token may have been exposed, ``DELETE /authenticate`` revokes the session.

----------------------------------------------------------------------------

POST /authenticate
==================

Provide authentication credentials to receive refresh token.

The user provides a username and password in the request body. If authentication succeeds,
the endpoint will return a JWT bearer refresh token with the user's claims. An initial access
token is also returned. Both tokens carry the user's ``groups``, the username as ``sub``, the
login session identifier ``sid``, the issue and expiry times (``iat``, ``nbf``, ``exp``) and a
``grant_type`` of ``refresh_token`` or ``access_token``. The refresh token can then be provided to ``PUT /authenticate``
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

--------------

DELETE /authenticate
====================

Revoke the login session (log out).

The user provides either token of the session (the refresh token, or any access token obtained
from it) in the Authorization header. The session is revoked: the refresh token can no longer
be used with ``PUT /authenticate``, every access token of the session is refused by every
other endpoint, and any websocket subscriptions opened with them are closed (a subscription that
was renewed over the socket with a token of a later login belongs to that later session instead). Revocation
persists across a restart of the web service and lasts until the last token of the session
would have expired anyway.

If the file that records revoked sessions cannot be read at startup, it is moved aside with a
``.corrupt-<time>`` suffix and every token issued before that moment is refused, so a revoked
session cannot return through a damaged file. Users who were logged in simply log in again;
tokens issued afterwards are unaffected. The web service logs the event and the name of the
kept file.

The token is read from the Authorization header only. A ``Bearer`` cookie is not accepted
for this request, so a page served by another site cannot log the user out.

Request:
--------

- Authorization: ``BEARER <jwt_refresh_token or jwt_access_token>``
- Body: none

Response:
---------

* **With a valid token of this server:** ``204 No Content``
    - Returned also when the session was already revoked.

* **With no token, or an invalid or expired token:** ``401 Unauthorized``

.. note:: Tokens issued before the server supported revocation carry no session identifier
    and are refused everywhere; clients holding one must log in again with
    ``POST /authenticate``.
