.. _Platforms-Configs-Endpoints:

==========================
Platforms Configs Endpoints
==========================

Platforms Configs endpoints expose functionality associated with platform configuration files.
These endpoints are for platform-level configurations. Agent configurations are managed by
the :ref:`Platforms Agents Configs <Platforms-Agents-Configs-Endpoints>` endpoints.

.. attention::
    All Platforms Configs endpoints require a JWT bearer token obtained through the
    ``POST /authenticate`` or ``PUT /authenticate`` endpoints.

--------------

GET /platforms/:platform/configs
================================

Get routes to available configuration files for the specified platform.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "route_options": {
                    "<config_name>": "/platforms/:platform/configs/:config_name",
                    "<config_name>": "/platforms/:platform/configs/:config_name"
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

---------------------------------------------------------------

POST /platforms/:platform/configs
================================

Save a new platform configuration file.

The file name should be passed in the query parameter file-name.

The platform configuration files are currently either JSON or INI files. The MIME type of the request will be either
``application/json`` or ``text/plain`` in the case of INI files. This endpoint will return an error if the file already exists.
To update an existing file, use the PUT /platforms/:platform/configs/:file_name endpoint.

.. warning::

    Editing platform configuration files can affect the ability of the platform to restart. It is not currently possible
    to repair an unstartable platform from the API. Fixing mistakes will require direct access to the device or SSH.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``
* Content Type: ``application/json`` or ``text/plain``
* Query Parameters:
    * file-name: The name of the file. If the file will be saved in a subdirectory, ``file-name`` should be a
      URL-encoded path to the location of the file relative to the ``VOLTTRON_HOME`` directory. Paths outside of
      ``VOLTTRON_HOME`` will be disallowed.
* Body (shown for JSON):

  .. code-block::

   {
        "<setting_name>": <value>,
        "<setting_name>": <value>,
   }

Response:
---------

* **With valid BEARER token on success:** ``201 Created``
    * Location: ``/platforms/:platform/configs/:file_name``
    * Content Type: ``application/json``

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

---------------------------------------------------------------

GET /platforms/:platform/configs/:config_name
=============================================

Get a configuration file for the platform (not for an individual agent).

The platform configuration files are currently either JSON or INI files. The MIME type of the response will be either
``applciation/json`` or ``text/plain`` in the case of INI files.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``200 OK``
    - `JSON file:`
        - Content Type: ``application/json``
        - Body:

        .. code-block:: JSON

            {
                "<setting_name>": <value>,
                "<setting_name>": <value>,
            }

    - `INI file:`
            - Content Type: ``text/plain``
            - Body:

            .. code-block:: INI

                [section_name]
                key1=value1
                key2=value2

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

---------------------------------------------------------------

PUT /platforms/:platform/configs/:config_name
==============================================

Replace an existing platform configuration file.

The platform configuration files are currently either JSON, INI files. The MIME type of the response will be either
``applciation/json`` or ``text/plain`` in the case of INI files. This endpoint will return an error if the file does not
already exist. To create a new file, use the ``POST /platforms/:platform/configs`` endpoint.

If the file is located in a subdirectory, ``:config_name`` should be a URL-encoded path to the location of the file
relative to the ``VOLTTRON_HOME`` directory. Paths outside of ``VOLTTRON_HOME`` will be disallowed.

.. warning::

    Editing platform configuration files can affect the ability of the platform to restart. It is not currently possible
    to repair an unstartable platform from the API. Fixing mistakes will require direct access to the device or SSH.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``
* Content Type: ``application/json`` or ``text/plain``
* Body (shown for JSON):

  .. code-block::

   {
        "<setting_name>": <value>,
        "<setting_name>": <value>,
   }

Response:
---------

* **With valid BEARER token on success:** ``201 Created``
    * Location: ``/platforms/:platform/configs/:file_name``
    * Content Type: ``application/json``

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``

---------------------------------------------------------------

DELETE /platforms/:platform/configs/:config_name
================================================

Delete an existing platform configuration file.

If the file is located in a subdirectory, ``:config_name`` should be a URL-encoded path to the location of the file
relative to the ``VOLTTRON_HOME`` directory. Paths outside of ``VOLTTRON_HOME`` will be disallowed.

.. warning::

    Editing platform configuration files can affect the ability of the platform to restart. It is not currently possible
    to repair an unstartable platform from the API. Fixing mistakes will require direct access to the device or SSH.

Request:
--------

* Authorization: ``BEARER <jwt_access_token>``

Response:
---------

* **With valid BEARER token on success:** ``204 No Content``

* **With valid BEARER token on failure:** ``400 Bad Request``
    - Content Type: ``application/json``
    - Body:

      .. code-block:: JSON

            {
                "error": "<Error Message>"
            }

* **With invalid BEARER token:** ``401 Unauthorized``
