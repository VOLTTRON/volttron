.. _Web-Framework:

=============
Web Framework
=============

This document describes the interaction between web enabled agents and the Master Web Service agent.

The web framework enables agent developers to expose JSON, static, and websocket endpoints.

Web SubSystem
=============

Enabling
--------

The web subsystem is not enabled by default as it is only required by a small subset of agents.
To enable the web subsystem the platform instance must have an enabled the web server and the agent
must pass enable_web=True to the agent constructor.

.. code-block:: python

    class WebAgent(Agent):
        def __init__(self, **kwargs):
            super(WebAgent, self).__init__(enable_web=True,**kwargs)


MANIFEST File
-------------

The MANIFEST.in file is used to package additional files needed for your web enabled agent.
Please read the python packaging `documentation <https://packaging.python.org/guides/using-manifest-in/>`_
on the MANIFEST.in file. For most cases, i.e. when you only need to include a webroot directory for html
and javascript, the manifest file only needs to include the `recursive-include` command. For example, the entirety
of the VolttronCentral MANIFEST.in file is:

.. code-block:: python

    recursive-include volttroncentral/webroot *

The MANIFEST.in file should be located in the root directory of the agent. All pathing for the MANIFEST.in file
commands are relative to this root directory.

Routes
-------

The web subsystem allows an agent to register three different types of routes; file paths, endpoints, and websockets.

.. note::
    For all endpoint methods the first match wins.  Therefore ordering which endpoints are registered first becomes important.


File Path
~~~~~~~~~

A path based endpoint allows the agent to specify a prefix and a static path on the file system to serve static files.
The prefix can be a regular expression.

The below examples are within the context of an object that has extended the :class:`volttron.platform.vip.agent.Agent` base class.


.. code-block:: python

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        """
        Allow serving of static content from /var/www
        """
        self.vip.web.register_path(r'^/vc/.*', '/var/www')


Endpoint
~~~~~~~~~

JSON endpoints allows an agent to serve data responses to specific queries from a web client.non-static responses.
The agent will pass a callback to the subsystem which will be called when the endpoint is triggered.

.. code-block:: python

    def jsonrpc(env, data):
    """
    The main entry point for jsonrpc data
    """
        return {'dyamic': 'data'}

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
    """
    Register the /vc/jsonrpc endpoint for doing json-rpc based methods
    """
        self.vip.web.register_endpoint(r'/vc/jsonrpc', self.jsonrpc)


Websocket
~~~~~~~~~

Websocket endpoints allow bi-directional communication between the client and the server.
Client connections can be authenticated during the opening of a websocket through the response of an open callback.


.. code-block:: python

    def _open_authenticate_ws_endpoint(self, fromip, endpoint):
        """
        A client attempted to open an endpoint to the server.

        Return True or False if the endpoint should be allowed.

        :rtype: bool
        """
        return True

    def _ws_closed(self, endpoint):
        _log.debug("CLOSED endpoint: {}".format(endpoint))

    def _ws_received(self, endpoint, message):
        _log.debug("RECEIVED endpoint: {} message: {}".format(endpoint,
                                                              message))

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.vip.web.register_websocket(r'/vc/ws', self.open_authenticate_ws_endpoint, self._ws_closed, self._ws_received)
