.. _Platforms-Historians-Endpoints:

==============================
Platforms Historians Endpoints
==============================

Platform Historian endpoints expose functionality related to historians
running on a VOLTTRON platform.

.. admonition:: Use of Topics

    There is no special meaning to most segments of a topic in the VOLTTRON platform. In the context of
    devices, however, the final segment in a full topic denotes a point which can be read or actuated.
    Partial topics denote some collection of these point resources. For instance, in the caes of a topic hierarchy
    organized as ``:campus/:building/:device/:point``, a topic which is complete up to the ``:device`` level would
    yield a single device containing one or more points. A topic complete to the ``:building`` level would include a
    set of devices, each containing some set of points. The response to any request containing a full topic will
    therefore perform a get or set operation, while a partial topic will typically return a list of routes to
    further sub-topics (unless it is explicitly requested that an operation be performed on multiple
    points).

    Several methods are available to refine the list of topics:

    Topic Wildcards:
        The ``-`` character may be used alone to represent any value for a segment: ``/:campus/-/:device``
        will match all devices with the name :device on the :campus in any building. It is not possible to
        use ``-`` as a wildcard within a segment containing other characters: ``/campus/foo-bar/:device``
        will only match a building called “foo-bar”, not one called “foobazbar”.

    Topic-Filtering Query Parameters:
        -  ``tag`` (default=null):
            Filter the result by the provided tag. (This requires that the tagging service be
            running and configured.)
        -  ``regex`` (default=null):
                Filter the result by the provided regular expression. The raw regular expression
                should follow python re syntax, but must be url-encoded within the query-string.

.. attention::
    All endpoints in this tree require authorization using a JWT bearer access token provided by the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.
--------------

GET /platforms/:platform/historians
===================================

Retrieve routes to historians on the platform, where each historian is listed by its VIP identity.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

-  **With valid BEARER token on success:** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "<historian>": "/vui/platforms/:platform/historians/:historian",
             "<historian>": "/vui/platforms/:platform/historians/:historian"
         }

-  **With valid BEARER token on failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``

--------------

GET /platforms/:platform/historians/:historian
==============================================

Retrieve routes for an historian. The only currently supported result is the "topics" endpoint.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

-  **With valid BEARER token on success:** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "topics": "/vui/platforms/:platform/historians/:historian/topics"
         }

-  **With valid BEARER token on failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``

--------------

GET /platforms/:platform/historians/:historian/topics/:topic
============================================================

Query data for a topic. If no topic, or a parital topic is provided, the output will be a JSON object containing routes
to additional sub-topics matching the provided partial topic. If a full topic is provided, or if the read-all query
parameter is passed, the response will contain data and/or metadata about any points indicated by the topic.
In addition to the tag and regex query parameters described in the Use of Topics section above, the following query
parameters are accepted:

- ``read-all`` (default=false):
        If true, the response will return entries for every point. These will be a set of JSON objects
        with `route`, `writability`, and `value` unless the result is further filtered by the
        corresponding query parameters.

- ``routes`` (default=true):
        If true, the result will include the route to the query.

- ``values`` (default=true):
        If true, the result will include the value of the query.

Several query parameters may also be used to refine the results:

-  start (default=null):
    Datetime of the start of the query.

-  end (default=null):
    Datetime of the end of of the query.

-  skip (default=null):
    Skip this number of results (for pagination).

-  count (default=null):
    Return at maximum this number of results (for pagination).

-  order (default=null):
    “FIRST_TO_LAST” for ascending time stamps, “LAST_TO_FIRST” for
    descending time stamps.

.. attention::
    Due to current limitations of the VOLTTRON historian, meta-data about the queried data is only returned when a
    single topic has been queried. Where multiple topics are selected, the meta-data field will not be present in the
    result.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

-  **With valid BEARER token on success (single topic):** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
            "Campus/Building1/Fake2/SampleWritableFloat1": {
                "value": [
                    ["<datetime>", <value>],
                    ["<datetime>", <value>],
                    ["<datetime>", <value>]
                ],
                "metadata": {
                    "units": "<unit>",
                    "type": "<data type>",
                    "tz": "<time zone>"
                },
                "route": "/vui/platforms/:platform/historians/:historian/historians/Campus/Building1/Fake2/SampleWritableFloat1"
            }
         }

-  **With valid BEARER token on success (multiple topics):** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
            "Campus/Building1/Fake2/SampleWritableFloat1": {
                "value": [
                    ["<datetime>", <value>],
                    ["<datetime>", <value>],
                    ["<datetime>", <value>]
                ],
                "route": "/vui/platforms/:platform/historians/:historian/historians/Campus/Building1/Fake2/SampleWritableFloat1"
            },
            "Campus/Building1/Fake2/SampleWritableFloat2": {
                "value": [
                    ["<datetime>", <value>],
                    ["<datetime>", <value>],
                    ["<datetime>", <value>]
                ],
                "route": "/vui/platforms/:platform/historians/:historian/historians/Campus/Building1/Fake2/SampleWritableFloat2"
            }
         }

-  **With valid BEARER token on failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``
