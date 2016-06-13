VOLTTRON Central Management Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Agent Introduction
==================

The VOLTTRON Central Agent (VCM) is responsible for controlling multiple
VOLTTRON instances through a single interfaces.  The VOLTTRON instances
can be either local or remote.  VCM leverages an internal VOLTTRON web server
providing a interface to our JSON-RPC based web api.  Both the web api and
the interface are served through the VCM agent. There is a `VOLTTRON
Central Demo <VOLTTRON-Central-Demo>`__ that will allow you to quickly
setup and see the current offerings of the interface. VOLTTRON Central
will allow you to

-  See a list of platforms being managed.
-  Add and remove platforms.
-  Install, start and stop agents to the registered platforms.
-  Create dynamic graphs from the historians based upon points.
-  Execute functions on remote platforms.

Instance Configuration
======================

In order for any web agent to be enabled, there must be a port configured to
serve the content.  The easiest way to do this is to create a config file in
the root of your VOLTTRON_HOME directory. (to do this automatically see :ref:`
VOLTTRON Config<VOLTTRON-Config>`)

The following is an example of the configuration file

::

    [volttron]
    vip-addres=tcp://127.0.0.1:22916
    bind-web-address=http://127.0.0.1:8080

** Note the above configuration will open a discoverable port for the volttron
   instance.  In addition, the opening of this web address allows you to serve
   both static as well as dynamic pages.

Verify that the instance is serving properly by pointing your web browser to

::

    http://127.0.0.1:8080/discovery/

This is the required information for a VolttronCentralPlatform to be able to
be managed.

VOLTTRON Central Manager Configuration
======================================
The following is the default configuration file for VOLTTRON Central

::

    {
        # The agentid is used during display on the VOLTTRON central platform
        # it does not need to be unique.
        "agentid": "volttron central",
        
        # Authentication for users is handled through a naive password algorithm
        # Note in the following example the user and password are identical.
        # import hashlib
        # hashlib.sha512(password).hexdigest() where password is the plain text password.
        "users" : {
            "reader" : {
                "password" : "2d7349c51a3914cd6f5dc28e23c417ace074400d7c3e176bcf5da72fdbeb6ce7ed767ca00c6c1fb754b8df5114fc0b903960e7f3befe3a338d4a640c05dfaf2d",
                "groups" : [
                    "reader"
                ]
            },
            "writer" : {
                "password" : "f7c31a682a838bbe0957cfa0bb060daff83c488fa5646eb541d334f241418af3611ff621b5a1b0d327f1ee80da25e04099376d3bc533a72d2280964b4fab2a32",
                "groups" : [
                    "writer"
                ]
            },
            "admin" : {
                "password" : "c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd472634dfac71cd34ebc35d16ab7fb8a90c81f975113d6c7538dc69dd8de9077ec",
                "groups" : [
                    "admin"
                ]
            },
            "dorothy" : {
                "password" : "cf1b67402d648f51ef6ff8805736d588ca07cbf018a5fba404d28532d839a1c046bfcd31558dff658678b3112502f4da9494f7a655c3bdc0e4b0db3a5577b298",
                "groups" : [
                    "reader, writer"
                ]
            }
        }
    }

Agent Execution
===============

To start VOLTTRON Central first make sure the `VOLTTRON instance is
running <Eclipse-Dev-Environment#execute-volttron-platform-from-shell>`__.
Next create/choose the config file to use. Finally from an activated
shell in the root of the VOLTTRON repository execute

::

    # Arguments are package to execute, config file to use, tag to use as reference
    ./scripts/core/pack_install.sh services/core/VolttronCentral services/core/VolttronCentral/config vc

    # Start the agent
    volttron-ctl start --tag vc

