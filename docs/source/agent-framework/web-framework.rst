.. _Web-Framework:

VOLTTRON Web Framework
======================

This document describes the interaction between web enabled agents and the Master Web Service agent.

The web framework enables agent developers to expose JSON, static, and websocket endpoints.

Web SubSystem
+++++++++++++

Enabling
--------

The web subsystem is not enabled by default as it is only required by a small subset of agents.  To enable the web subsystem the platform instance must have an enabled the web server and the agent must pass enable_web=True to the agent constructor.

Methods
-------

The web subsystem allows an agent to register three different types of endpoints; path based, JSON and websocket.  A path based endpoint allows the agent to specify a prefix and a static path on the file system to serve static files.  The prefix can be a regular expression.

.. note:: The web subsystem is only available when the constructor contains enable_web=True.

The below examples are within the context of an object that has extended the :class:`volttron.platform.vip.agent.Agent` base class.

.. note:: For all endpoint methods the first match wins.  Therefore ordering which endpoints are registered first becomes important.

.. code-block:: python

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        """
        Allow serving of static content from /var/www
        """
        self.vip.web.register_path(r'^/vc/.*', '/var/www')

JSON endpoints allows an agent to serve data responses to specific queries from a web client.non-static responses.  The agent will pass a callback to the subsystem which will be called when the endpoint is triggered.

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


Websocket endpoints allow bi-directional communication between the client and the server.  Client connections can be authenticated during the opening of a websocket through the response of an open callback.


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


