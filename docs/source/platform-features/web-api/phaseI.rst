.. container::
   :name: convenience

   .. rubric:: Convenience Methods
      :name: convenience-methods

These endpoints are convenience APIs which provide functionality similar
to the corresponding sections of the Platforms section, but across all
platforms within the system. Individual routes returned by these will be
the same as those returned by queries to a single platform.

--------------

.. container::
   :name: devices

   .. rubric:: Devices
      :name: devices

Devices endpoints expose functionality associated with devices managed by
all connected VOLTTRON platforms.

--------------

.. container::
   :name: get-devices

   .. rubric:: GET /devices
      :name: get-devices

Get routes to all devices for all connected platforms.

In the case where a device with the same topic appears on multiple
platforms, the value for that topic in the result will be a list of
routes where each element is the route to the device topic on on of the
platforms where it appears.

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
   :name: get-devicestopic

   .. rubric:: GET /devices/:topic
      :name: get-devicestopic

Get routes matching a topic for devices for all connected platforms.
Notes in the Platforms/Devices section regarding to topics and query
parameters apply here the same as for that section.

   **Note:** Platform Device endpoints accept query parameters to refine
   their output, as described in the introduction to the Devices
   section.

..

   **Note:** See the introduction to the Devices section for information
   on the use of topics.

Providing a partial topic returns all devices which share the given
segements of the provided topic. Using a partial topic:
``/:campus/:building`` will produce the same dictionary as the response
of ``GET /devices/`` but with only the topics beginning with the
segments ``:campus`` and ``:building``.

Providing a full topic will usually produce a single result, except
where more than one connected platform has the same topic, in which case
the result will be the list of routes to that topic on each containing
platform.

In the case where a device with the same topic appears on multiple
platforms, the value for that topic in the result will be a list of
routes where each element is the route to the device topic on on of the
platforms where it appears.

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
   :name: put-devicestopic

   .. rubric:: PUT /devices/:topic
      :name: put-devicestopic

Sets the value of the specified point(s) and returns its new value(s)
and meta-data.

   **Note:** Device endpoints accept query parameters to refine their
   output, as described in the introduction to the Devices section.

..

   **Note:** See the introduction to the Devices section for information
   on the use of topics.

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
   :name: delete-devicestopic

   .. rubric:: DELETE /devices/:topic
      :name: delete-devicestopic

Resets the value of the specified point(s) and returns its new value(s)
and meta-data.

   **Note:** Device endpoints accept query parameters to refine their
   output, as described in the introduction to the Devices section.

..

   **Note:** See the introduction to the Devices section for information
   on the use of topics.

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

--------------

.. container::
   :name: get-devicestopic-1

   .. rubric:: GET /devices/:topic
      :name: get-devicestopic-1

Get routes matching a topic for devices for all connected platforms.

   **Note:** Platform Device endpoints accept query parameters to refine
   their output, as described in the introduction to the Devices
   section.

..

   **Note:** See the introduction to the Platform Devices section for
   information on the use of topics.

Providing a partial topic returns all devices which share the given
segments of the provided topic. Using a partial topic:
``/:campus/:building`` will produce the same dictionary as the response
of ``GET /devices/`` but with only the topics beginning with the
segments ``:campus`` and ``:building``.

Providing a full topic will usually produce a single result, except
where more than one connected platform has the same topic, in which case
the result will be the list of routes to that topic on each containing
platform.

In the case where a device with the same topic appears on multiple
platforms, the value for that topic in the result will be a list of
routes where each element is the route to the device topic on on of the
platforms where it appears.

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
   :name: get-deviceshierarchy

   .. rubric:: GET /devices/hierarchy
      :name: get-deviceshierarchy

Retrieve a topical hierarchy of all devices on all platforms.

The response provides a dictionary organized hierarchically by segments
within the device topic. There is no special meaning to the segments of
device topics, but the example response shown here assumes that devices
are organized in a pattern common for a campus of buildings:
``/:campus/:building/:device/:point``.

   It is not necessary that topics all have the same number of segments,
   therefore some parts of the tree may be deeper than others. Users
   should not assume a uniform depth to all branches of the tree. It is
   also possible that a given level of the tree is not uniformly either
   a dict or a string. For example, in the third building shown in the
   example, zone level devices have an extra segment to indicate they
   are served by a particular air handling unit, however the air
   handling unit device itself has the normal number of segments.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK`` ``201 Created``
   ``204 No Content``

   -  Content Type: ``application/json``

   -  Body:

      ::

         {
             "<campus>": {
                 "<building>": {
                     "<device>": "/platforms/:platform/devices/:topic/",
                     "<device>": "/platforms/:platform/devices/:topic/",
                     ...
                 },
                 "<building>"" {
                     "<device>": "/platforms/:platform/devices/:topic/",
                     "<device>": [
                         "/platforms/:platform1/devices/:topic/",
                         "/platforms/:platform2/devices/:topic/",
                         ...
                     ],
                     ...
                 },
                 "<building>": {
                     <ahu_device>: "/platforms/:platform/devices/:topic/",
                     <ahu>: {
                         "<zone_device>": "/platforms/:platform/devices/:topic/",
                         "<zone_device>": "/platforms/:platform/devices/:topic/",
                         ...
                     },
                     ...
                 },
                 ...
             },
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
   :name: get-deviceshierarchytopic

   .. rubric:: GET /devices/hierarchy/:topic
      :name: get-deviceshierarchytopic

Retrieve a partial topical hierarchy of all devices on all platforms.

   **Note:** Device endpoints accept query parameters to refine their
   output, as described in the introduction to the Devices section.

..

   **Note:** See the introduction to the Devices section for information
   on the use of topics.

As with the ``GET /devices/hierarchy`` endpoint, the response provides a
dictionary organized hierarchically by segments within the device topic.
Providing a partial topic produces a clade of the device tree with its
root at the provided topic.

As elaborated on in the introduction to the Devices section, there is no
special meaning to the segments of device topics, but the example
response shown here assumes that devices are organized in a pattern
common for a campus of buildings: ``/:campus/:building/:device/:point``.
Using a partial topic: ``/:campus/:building`` will produce a the same
object which could be obtained by indexing the response of
``GET /devices/hierarchy`` first with ``<campus>`` and then
n\ ``<device>``, e.g.:

::

   ```
       responseObject['<campus>']['<building>']
   ```

The example shown in the response section below is produced by
``GET /devices/hierarchy/:campus/:building``, where ``:building`` has the
same value as the second building in the example shown for
``GET /devices/hierarchy``.

Providing a full topic will usually produce a single leaf node, except
where more than one connected platform has the same topic, in which case
the result will be the list of leaf nodes corresponding to that topic on
each containing platform.

   It is not necessary that topics all have the same number of segments,
   therefore some parts of the tree may be deeper than others. Users
   should not assume a uniform depth to all branches of the tree. It is
   also possible that a given level of the tree is not uniformly either
   a dict or a string. For example, in the third building shown in the
   example, zone level devices have an extra segment to indicate they
   are served by a particular air handling unit, however the air
   handling unit device itself has the normal number of segments.

**Request:**

-  Authorization: ``BEARER <jwt_access_token>``

**Response:**

-  With valid BEARER token on success: ``200 OK`` ``201 Created``
   ``204 No Content``

   -  Content Type: ``application/json``

   -  Body:

      ::

             "<device>": "/platforms/:platform/devices/:topic/",
              "<device>": [
                     "/platforms/:platform1/devices/:topic/",
                     "/platforms/:platform2/devices/:topic/",
                     ...
                 ],
                 ...
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

--------------

.. container::
   :name: historians

   .. rubric:: Historians & History
      :name: devices

Historians & History endpoints expose functionality associated with all
historians managed by all connected VOLTTRON platforms.

The ``POST /history`` endpoint will require further definition. This is
intended to provide a richer query API utilizing GraphQL for the system
as a whole. Both the GraphQL and RESTful endpoints are available for
specific historians using the
``/platforms/:platform/historians/:historian`` routes returned by
``GET /historians`` or ``GET /platforms/:platform/historians``. GraphQL
recommends providing both ``GET`` and ``POST`` methods for queries. As
the utility of ``GET`` is frequently limited by the allowed size of
querystrings, a ``GET /history`` endpoint has not, however, been defined
at this time.

.. container::
   :name: get-historians

   .. rubric:: GET /historians
      :name: get-historians

Retrieve routes to historians on all platforms.

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
   :name: post-history

   .. rubric:: POST /history
      :name: post-history

A GraphQL interface to history throughout all historians on all known
platforms. The request body should contain a JSON object following
GraphQL semantics.

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
