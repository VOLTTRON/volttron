.. _Platforms-Devices-Endpoints:

============================
Platforms Devices Endpoints
============================


Platform Devices endpoints expose functionality associated with devices managed by a VOLTTRON
platform. An optional topic portion of the route path may be used to select specific devices within
the platform. The selection of devices may then be further refined through the use of query parameters,
as described in *Use of Topics*.

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

GET /platforms/:platform/devices/:topic
=======================================
Returns a collection of device points and values for a given device topic.

If no topic, or a parital topic is provided, the output will be a JSON object containing routes to
additional sub-topics matching the provided partial topic.  If a full topic is provided, or if the
``read-all`` query parameter is passed, the response will contain data and/or metadata about any
points indicated by the topic. In addition to the ``tag`` and ``regex`` query parameters described
in the *Use of Topics* section above, the following query parameters are accepted:

* ``read-all`` (default=false):
    If true, the response will return entries for every point. These will be a set of JSON objects
    with `route`, `writability`, and `value` unless the result is further filtered by the
    corresponding query parameters.
* ``routes`` (default=true):
    If true, the result will include the route to the points.
* ``writability`` (default=true):
    If true, the result will include the writability of the points.
* ``values`` (default=true):
    If true, the result will include the value of the points.
* ``config`` (default=false):
    If true, the result will include information about the configuration of the point.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    -  Content Type: ``application/json``
    -  Body:

        + For partial topics, where the ``read-all`` query parameter is false:
            This example shows a partial topic, structured as `campus/building/device/point`,
            where two segments were provided (the topic provided was `MyCampus/Building1`.
            Devices within the building are returned:

            .. code-block:: JSON

                {
                    "route_options": {
                        "<device1>": "/platforms/:platform/devices/MyCampus/Building1/<device1>",
                        "<device2>": "/platforms/:platform/devices/MyCampus/Building1/<device2>"
                    }
                }

        + For full topics, or where a partial topic is provided and the ``read-all`` query parameter is true:
            This example shows the result of a topic: `MyCampus/Building1/-/Point4`. Note that
            the wildcard selects all devices in `Building1` with a point called `Point4`.
            ``read-all`` does not need to be ``true`` for this case to get data, as a point segment was provided.
            Other query parameters were not provided or were set to their default values.

            .. code-block:: JSON

                {
                    "MyCampus/Building1/Device1/Point4": {
                        "route": "/platform/:platform/devices/MyCampus/Building1/Device1/Point4",
                        "writable": true,
                        "value": 42
                    },
                    {
                    "MyCampus/Building1/Device2/Point4": {
                        "route": "/platform/:platform/devices/MyCampus/Building1/Device2/Point4",
                        "writable": false,
                        "value": 23
                    }
                }

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``


PUT /platforms/:platform/devices/:topic/
========================================

Sets the value of the specified point and returns its new value and meta-data. In addition to the tag and regex query
parameters described in the Use of Topics section above, the following query parameters are accepted:

* ``write-all`` (default=false):
    If true, the response will write the given value to all points matching the topic. It is *always* necessary to
    set write-all=true if more than one point is intended to be written in response to the request.
* ``confirm-values`` (default=false):
    If true, the current value of any written points will be read and returned after the write.

.. warning::
    If an attempt is made to set a point which is not writable, or if multiple points are selected
    using a partial topic and/or query parameters and the ``write-all`` query parameter is not set
    to ``true``, the response will be ``405 Method Not Allowed``.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

* Content Type: ``application/json``

* Body:

  .. code-block:: JSON

        {
            "value": <value>
        }

Response:
---------

-  **With valid BEARER token on success (confirm-values=false):** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
            "<topic>": {
                "route": "/vui/platforms/:platform/devices/:topic",
                "set_error": <null or error message>,
                "writable": <bool>
            }
         }

-  **With valid BEARER token on success (confirm-values=true):** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
            "<topic>": {
                "route": "/vui/platforms/:platform/devices/:topic",
                "set_error": <null or error message>,
                "writable": <bool>,
                "value": <value>,
                "value_check_error": <null or error message>
            }
         }

-  **With valid BEARER token if any point is not writable:**
   ``405 Method Not Allowed``:

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message indicating unwritable points>"
         }

-  **With valid BEARER token on any other failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``

--------------

DELETE /platforms/:platform/devices/:topic/
===========================================

Resets the value of the specified point and returns its new value andmeta-data.In addition to the tag and regex query
parameters described in the Use of Topics section above, the following query parameters are accepted:

    * ``write-all`` (default=false):
        If true, the response will write the given value to all points matching the topic. It is *always* necessary to
        set write-all=true if more than one point is intended to be written in response to the request.
    * ``confirm-values`` (default=false):
        If true, the current value of any written points will be read and returned after the write.

.. warning::
    If an attempt is made to set a point which is not writable, or if multiple points are selected
    using a partial topic and/or query parameters and the ``write-all`` query parameter is not set
    to ``true``, the response will be ``405 Method Not Allowed``.

.. warning::
    The request will also fail unless all writes are successful, and any points which would otherwise be set will be
    reverted to their previous value.

Request:
--------

-  Authorization: ``BEARER <jwt_access_token>``

Response:
---------

-  **With valid BEARER token on success (confirm-values=false):** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
            "<topic>": {
                "route": "/vui/platforms/:platform/devices/:topic",
                "writable": <bool>
            }
        }

-  **With valid BEARER token on success (confirm-values=true):** ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
            "<topic>": {
                "route": "/vui/platforms/:platform/devices/:topic",
                "writable": <bool>,
                "value": <value>,
                "value_check_error": <null or error message>
            }
        }

-  **With valid BEARER token if any point is not writable:**
   ``405 Method Not Allowed``:

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message indicating unwritable points>"
         }

-  **With valid BEARER token on any other failure:** ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      .. code-block:: JSON

         {
             "error": "<Error Message>"
         }

-  **With invalid BEARER token:** ``401 Unauthorized``
