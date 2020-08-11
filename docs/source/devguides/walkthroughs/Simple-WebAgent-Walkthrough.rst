.. _Simple-WebAgent-Walkthrough:

Simple Web Agent Walkthrough
============================

A simple web enabled agent that will hook up with a volttron message bus and
allow interaction between it via http.  This example agent shows a simple file
serving agent, a json-rpc based call, and a websocket based connection
mechanism.

Starting VOLTTRON Platform
--------------------------

.. note:: Activate the environment first :ref:`active the environment <activated-environment>`

In order to start the simple web agent, we need to bind the VOLTTRON instance
to the a web server.  We need to specify the address and the port for the
web server. For example, if we want to bind the localhost:8080 as the web server
we start the VOLTTRON platform as follows:

``./start-volttron --bind-web-address http://127.0.0.1:8080``

Once the platform is started, we are ready to run the Simple Web Agent.

Running Simple Web Agent
------------------------

.. note:: The following assumes the shell is located at the :ref:`VOLTTRON_ROOT`.

Copy the following into your shell (save it to a file for executing it again
later).

.. code-block:: console

    python scripts/install-agent.py \
        --agent-source examples/SimpleWebAgent \
        --tag simpleWebAgent \
        --vip-identity webagent \
        --force \
        --start

This will create a web server on http://localhost:8080. The index.html file
under ``simpleweb/webroot/simpleweb/`` can be any html page which binds to the
VOLTTRON message bus .This provides a simple example of providing a web endpoint
in VOLTTRON.

Path based registration examples
--------------------------------

- Files will need to be in webroot/simpleweb in order for them to be browsed
  from http://localhost:8080/simpleweb/index.html

- Filename is required as we don't currently autoredirect to any default pages
  as shown in ``self.vip.web.register_path("/simpleweb", os.path.join(WEBROOT))``

The following two examples show the way to call either a jsonrpc (default)
endpoint and one that returns a different content-type. With the JSON-RPC
example from volttron central we only allow post requests, however this is not
required.

- Endpoint will be available at http://localhost:8080/simple/text ``self.vip.web.register_endpoint("/simple/text", self.text)``

- Endpoint will be available at http://localhost:8080/simple/jsonrpc ``self.vip.web.register_endpoint("/simpleweb/jsonrpc", self.rpcendpoint)``
- Text/html content type specified so the browser can act appropriately like ``[("Content-Type", "text/html")]``
- The default response is application/json so our endpoint returns appropriately with a json based response.
