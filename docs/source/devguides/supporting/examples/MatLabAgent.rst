.. _MatlabAgent:

MatLab Agent
============

The MatLab agent and Matlab standalone agent together are 
example agents that allow for matlab scripts to be run in a
windows environment. The MatLab agent take advantage of the 
config store to dynamically send scripts and commandline arguments
across the message bus to one or more standalone agents in
windows. The standalone agent then executes the requested script 
and arguments, and sends back the results to the MatLab agent.



Installations
-------------

To use MatLab in Python, the MatLab engine API must be installed.
Instructions to do so are found `here <https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html>`_.


StandAloneMatLab Agent
~~~~~~~~~~~~~~~~~~~~~~

The standalone MatLab agent is designed to be usable in a 
windows environment. 

.. warning:: 

        VOLTTRON is not designed to run in a windows environment. 
        Outside of cases where it is stated to be usable in a 
        windows environment, it should be assumed that it will
        NOT function as expected.

1. Download VOLTTRON

   Download the VOLTTRON develop repository from github.This 
   may be done using any tool you wish. In this case, directly from 
   `GitHub <https://github.com/VOLTTRON/volttron/tree/develop>`_.
   
   |github-image|

2. Setup the PYTHONPATH
   
   Open the windows explorer, and navigate to "Edit environment variables for your account"
   
   |cmd-image|

   Select "new"
   
   |env-vars-image_1|
   
   For "Variable name" enter: PYTOHNPATH
   For "Variable value" either browse to your volttron installation, or enter in the path to your volttron installation
   
   |env-vars-image_2|
   
   Select "OK" twice.

3. Set up the environment.
   
   Open up the command prompt.
   
   |cmd-image_2|
   
   Naviage to your volttron installation.
   
   ``cd \Your\directory\path\to\volttron-develop``
   
   Use pip to install and setup dependencies.
   
   ``pip install -r requirements.txt``
   
   ``pip install -e .``

At this point, the agent is ready to be run. To use the agent, navigate to the
example folder, and use python to start the agent.

``cd examples\StandAloneMatLab\``

``py -2 standalone_matlab.py``


MatLabAgent_v2
~~~~~~~~~~~~~~

This agent is installed in the same way as any agent in the volttron 
platform. See :ref:`Agent Development <Agent-Development>` for 
instructions on installaton and testing agents

Agent Useages and Modifications
-------------------------------


StandAloneMatLab Agent
~~~~~~~~~~~~~~~~~~~~~~

To work with the StandAlone agent, a few modifications will need to be made.

1. settings.py
   * 'vip_address' needs to be set to the address of your volttron instance
   
   * 'port' needs to be set to the port of your volttron instance
   
   * 'server_key' needs to be set to the public server key of your remote platform.
     This can be obtained from the instance using the ``vctl auth serverkey`` command
   
.. note::

        It is recommended that you generate a new agent_public and agent_private
        key for your standalone agent. This can be done using the ``vctl auth keypair``
        command on your volttron instance. If you plan to use multiple standalone agents,
        they will each need their own keypair.

2. standalone_matlab.py

   * @PubSub.subscribe('pubsub','matlab/to_agent/1') should be set to the 
     topic you choose in your config file. (line 74)
   
   * self.vip.pubsub.publish('pubsub', 'matlab/from_agent/1', message=messageOut)
     should be set to the topic you choose in your config file (line 78)
   
   * identity=`standalone_matlab') can be changed.

.. note:: 
        
        These changes are only necessary if you make changes to the example
        config file topics or if you want to run multiple standalone agents.

It is possible to have multiple standalone agents running. In this case,
copy the StandAloneMatLab folder, and make the changes mentioned above.

MatLabAgent_v2
~~~~~~~~~~~~~~

The configuration file for the MatLab agent has four variables.

   1. script_names

   2. script_args
   
   3. topics_to_agents

   4. topics_from_agents

An example config file included with the folder.

.. code::

        {
          # VOLTTRON config files are JSON with support for python style comments.
          "script_names": ["testScript.py"],
          "script_args": [["20"]],
          "topics_to_agents": ["matlab/to_agent/1"],
          "topics_from_agents": "matlab/from_agent/"
        }

To edit the configuration, the format should be as follows:

.. code::

        {
          "script_names": ["script1.py", "script2.py", ...],
          "script_args": [["arg1","arg2"], ["arg1"], ...],
          "topics_to_agents": ["matlab/to_agent/1", "matlab/to_agent/2", ...],
          "topics_from_agents": "matlab/from_agent/"
        }

The config does require that each script lines up with a set of 
commandline arguments, and a topic. So a commandline argument 
must be included, even if it is not used. The placement of 
brackets are important, even when only communicating with one 
standalone agent. 

For example, if only one standalone agent is used, and no command line 
arguments are in place, the config file may look like this.

.. code::

        {
          "script_names": ["testScript.py"],
          "script_args": [["0"]],
          "topics_to_agents": ["matlab/to_agent/1"],
          "topics_from_agents": "matlab/from_agent/"
        }

.. note::

        The only change that needs to be made to agent.py for 
        MatLabAgent_v2 is setting the pattern for self.vip.config.subscribe (line 70)
        Currently it is set to "config". As such, when using the config store, the 
        configuration name must match, regardless of the original file name.

Configuration Modifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The MatLab agent uses the configuration store to dynamically change inputs.
More information on the config store and how it used can be found here.

 * :ref:`VOLTTRON Configuration Store <VOLTTRON-Configuration-Store>`

 * :ref:`Agent Configuration Store <ConfigurationStore>`

 * :ref:`Agent Configuration Store Interface <Agent-Configuration-Store-Interface>`



.. |github-image| image:: files/github-image.png
.. |cmd-image| image:: files/cmd-image.png
.. |env-vars-image_1| image:: files/env-vars-image_1.png
.. |env-vars-image_2| image:: files/env-vars-image_2.png
.. |cmd-image_2| image:: files/cmd-image_2.png

