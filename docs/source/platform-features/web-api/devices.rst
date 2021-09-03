.. container::
   :name: platforms-devices

   .. rubric:: Platforms Devices
      :name: platforms-devices

Platform Devices endpoints expose functionality associated with devices
managed by a VOLTTRON platform.

-  All Platform Devices endpoints require a JWT bearer token obtained
   through the ``POST /authenticate`` or ``PUT /authenticate``
   endpoints.

**Note on the use of topics in Device and Platform Device Requests**

There is no special meaning to most segments of a topic in the VOLTTRON
platform. Topics typically, however do follow some convention, for
instance ``:campus/:building/:device/:point``. In the context of
devices, however, the final segment in a full topic denotes a point
which can be read or actuated. Partial topics (not including the last
segment) denote some collection of these point resources. A topic, for
instance which is complete up to the ``:device`` level in the campus
example would yield a single device containing one or more points. A
topic complete to the ``:building`` level would include a set of
devices, each containing some set of points. The response to any request
containing a full topic may differ, therefore, from a partial topic
because it contains a complete path to a resource which can be
individually queried or acted upon. The exact difference may vary by
endpoint, and as dictated by query parameters as described below.

The ``-`` character may be used alone to represent any value for a
segment: ``/:campus/-/:device`` will match all devices with the name
:device on the :campus in any building. It is not possible to use ``-``
as a wildcard within a segment containing other characters:
``/campus/foo-bar/:device`` will only match a building called “foo-bar”,
not one called “foobazbar”.

   It is possible that more than one device on several connected systems
   may share the same topic. In this case, as with the ``GET /devices``
   endpoint, the duplicates will be contained within a list. Users
   should always check the type of the value to determine if a given
   value in the dictionary is a string, list, or dict.

**Device and Platform Devices endpoints can accept the following query
parameters to refine their output:**

-  tag (default=null): Filter the result by the provided tag.

-  regex (default=null): Filter the result by the provided regular
   expression (follows python re syntax).

GET requests additionally accept:

-  include-points (default=false):

   -  If true, the response will return entries for every point. These
      will be a dictionary of dictionaries with route, writability, and
      value unless the result is further filtered by the corresponding
      parameters. If only one of ``route``, ``writable``, or ``value``
      are additionally provided, the result will be a dictionary of the
      corresponding item. If none of these are set to true (the
      default), all will be returned:

      ::

                 {
                     "route": <route\_to\_point>,
                     "writable": true|false,
                     "value": <value>
                 }

   -  If false, the response will consist of a dictionary of routes to
      devices (the most complete topic without points). ``route``,
      ``writable``, and ``value`` will be ignored.

-  route (default=false): IF true, the result will include the route to
   the points.

-  writable (default=false): IF true, the result will include the
   writability of the points.

-  value (default=false): IF true, the result will include the value of
   the points.

--------------

.. container::
   :name: get-platformsplatformdevices

   .. rubric:: GET /platforms/:platform/devices
      :name: get-platformsplatformdevices

Get routes to all devices for a platform.

   **Note:** Platform Device endpoints accept query parameters to refine
   their output, as described in the introduction to the Devices
   section.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<topic>": "/platforms/:platform/devices/:topic",
             "<topic>": "/platforms/:platform/devices/:topic",
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
   :name: get-platformsplatformdevicestopic

   .. rubric:: GET /platforms/:platform/devices/:topic/
      :name: get-platformsplatformdevicestopic

Returns a collection of points and values for a device topic.

   **Note:** Platform Device endpoints accept query parameters to refine
   their output, as described in the introduction to the Devices
   section.

..

   **Note:** See the introduction to the Platform Devices section for
   information on the use of topics.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<topic>": "/platform/:platform/devices/:topic",
             "<topic>": [
                         "/platform/:platform/devices/:topic",
                         "/platform/:platform/devices/:topic",
                        ]
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
   :name: put-platformsplatformdevicestopic

   .. rubric:: PUT /platforms/:platform/devices/:topic/
      :name: put-platformsplatformdevicestopic

Sets the value of the specified point and returns its new value and
meta-data.

   **Note:** Platform Device endpoints accept query parameters to refine
   their output, as described in the introduction to the Devices
   section.

..

   **Note:** See the introduction to the Platform Devices section for
   information on the use of topics.

If an attempt is made to set a point which is not writable, the response
will be ``405 Method Not Allowed``.

If the request uses partial topics and/or query parameters to select
more than one point to set, the query parameter ``write-all`` must be
set. If ``write-all`` is not set, the request will fail with
``405 Method Not Allowed``. The request will also fail unless all writes
are successful, and any points which would otherwise be set will be
reverted to their previous value.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

-  Content Type: ``application/json``

-  Body:

   ::

      {
          "value": <value>
      }

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "value": <new_value>,
             "meta": <meta_data>
         }

-  With valid BEARER token if any point is not writable:
   ``405 Method Not Allowed``:

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message indicating unwritable points>"
         }

-  With valid BEARER token on any other failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

--------------

.. container::
   :name: delete-platformsplatformdevicestopic

   .. rubric:: DELETE /platforms/:platform/devices/:topic/
      :name: delete-platformsplatformdevicestopic

resets the value of the specified point and returns its new value and
meta-data.

   **Note:** Platform Device endpoints accept query parameters to refine
   their output, as described in the introduction to the Devices
   section.

..

   **Note:** See the introduction to the Platform Devices section for
   information on the use of topics.

If an attempt is made to set a point which is not writable, the response
will be ``405 Method Not Allowed``.

If the request uses partial topics and/or query parameters to select
more than one point to set, the query parameter ``write-all`` must be
set. If ``write-all`` is not set, the request will fail with
``405 Method Not Allowed``. The request will also fail unless all writes
are successful, and any points which would otherwise be set will be
reverted to their previous value.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "value": <new_value>,
             "meta": <meta_data>
         }

-  With valid BEARER token if any point is not writable:
   ``405 Method Not Allowed``:

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message indicating unwritable points>"
         }

-  With valid BEARER token on any other failure: ``400 Bad Request``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "error": "<Error Message>"
         }

-  With invalid BEARER token: ``401 Unauthorized``

