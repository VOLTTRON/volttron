.. _VOLTTRON-MultiPlatform:

=======================================
MultiPlatform Message Bus Communication
=======================================

The multi platform message bus communication allows the user to connect to remote VOLTTTRON platforms seamlessly. This
bypasses the need for an agent wanting to send/receive messages to/from remote platforms from having to setup the
connection to remote platform directly. Instead, the router module in each platform will maintain connections to the
remote platforms internally, that means it will connect, disconnect and monitor the status of each connection.

.. toctree::
    :glob:
    :maxdepth: 2

    *
