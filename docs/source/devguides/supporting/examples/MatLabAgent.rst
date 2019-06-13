.. _MatlabAgent:

MatLab Agent
============

The MatLab agent and Matlab standalone agent together are 
example agents that allow for matlab scripts to be run in a
Windows environment and interact with the VOLTTRON platform running in a Linux environment. 
The MatLab agent takes advantage of the config store to 
dynamically send scripts and commandline arguments across 
the message bus to one or more standalone agents in
Windows. The standalone agent then executes the requested script 
and arguments, and sends back the results to the MatLab agent.

Setup on Linux
--------------

1. Setup and run Volttron from develop branch using instructions here

.. _MatlabAgent_config:
2. Update configuration for MatLabAgent_v2 at <volttron source dir>/example/MatLabAgent_v2/config. 

The configuration file for the MatLab agent has four variables.

   1. script_names

   2. script_args
   
   3. topics_to_matlab

   4. topics_to_volttron

An example config file included with the folder.

.. code::

        {
          # VOLTTRON config files are JSON with support for python style comments.
          "script_names": ["testScript.py"],
          "script_args": [["20"]],
          "topics_to_matlab": ["matlab/to_matlab/1"],
          "topics_to_volttron": "matlab/to_volttron/"
        }

To edit the configuration, the format should be as follows:

.. code::

        {
          "script_names": ["script1.py", "script2.py", ...],
          "script_args": [["arg1","arg2"], ["arg1"], ...],
          "topics_to_matlab": ["matlab/to_matlab/1", "matlab/to_matlab/2", ...],
          "topics_to_volttron": "matlab/to_volttron/"
        }

The config requires that each script name lines up with a set of 
commandline arguments and a topic. So a commandline argument 
must be included, even if it is not used. The placement of 
brackets are important, even when only communicating with one 
standalone agent. 

For example, if only one standalone agent is used, and no command line 
arguments are in place, the config file may look like this.

.. code::

        {
          "script_names": ["testScript.py"],
          "script_args": [["0"]],
          "topics_to_matlab": ["matlab/to_matlab/1"],
          "topics_to_volttron": "matlab/to_volttron/"
        }


3. Install MatLabAgent_v2 and start agent

``python scripts/install-agents.py -s examples/MatLabAgent_v2 -c examples/MatLabAgent_v2/config --start``

Configuration Modifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The MatLab agent uses the configuration store to dynamically change inputs.
More information on the config store and how it used can be found here.

 * :ref:`VOLTTRON Configuration Store <VOLTTRON-Configuration-Store>`

 * :ref:`Agent Configuration Store <ConfigurationStore>`

 * :ref:`Agent Configuration Store Interface <Agent-Configuration-Store-Interface>`



Setup on Windows
----------------

Install pre-requisites
~~~~~~~~~~~~~~~~~~~~~~~
1. Install python 2.7 from `here <https://www.python.org/downloads/windows/>`__.

2. Install MatLab engine from  `here <https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html>`_.

Install StandAloneMatLab Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The standalone MatLab agent is designed to be usable in a 
Windows environment. 

.. warning:: 

        VOLTTRON is not designed to run in a Windows environment. 
        Outside of cases where it is stated to be usable in a 
        Windows environment, it should be assumed that it will
        NOT function as expected.


1. Download VOLTTRON

   Download the VOLTTRON develop repository from github. Download the zip  
   from `GitHub <https://github.com/VOLTTRON/volttron/tree/develop>`_. 
   
   |github-image|

   |github-zip-image|

   Once the zipped file has been downloaded, go to your Downloads folder,
   right-click on the file, and select "Extract All..."

   |extract-image_1|

   Choose a location for the extracted folder, and select "Extract"

   |extract-image_2|


2. Setup the PYTHONPATH
   
   Open the Windows explorer, and navigate to "Edit environment variables for your account."
   
   |cmd-image|

   Select "New"
   
   |env-vars-image_1|
   
   For "Variable name" enter: "PYTOHNPATH"
   For "Variable value" either browse to your volttron installation, or enter in the path to your volttron installation.
   
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
   
   .. note::
   
     If you get the error doing the second step because of an already installed volttron from a different directory, manually delete the volttron-egg.link file from your <python path>\Lib\site-pacakages directory ( for example, del  C:\Python27\lib\site-packages\volttron-egg.link ) and re run the second command

4. Configure the agent

The configuration settings for the standalone agent are in setting.py (located in the same directory as the standalone agent)

**settings.py**

   * 'volttron_to_matlab' needs to be set to the topic that will send your script
     and command line arguments to your stand alone agent. This was defined in :ref:`config. <MatlabAgent_config>`

   * 'matlab_to_volttron' needs to be set to the topic that will send your script's
     output back to your volttron platform. This was defined in :ref:`config. <MatlabAgent_config>`

   * 'vip_address' needs to be set to the address of your volttron instance
   
   * 'port' needs to be set to the port of your volttron instance
   
   * 'server_key' needs to be set to the public server key of your primary volttron platform.
     This can be obtained from the primary volttron platform  using ``vctl auth serverkey``.
     (volttron must be running to use this command)


.. note:: 
        
        These changes are only necessary if you make changes to the example
        config file topics or if you want to run multiple standalone agents.

It is possible to have multiple standalone agents running. In this case,
copy the StandAloneMatLab folder, and make the changes mentioned above.

.. note::

        It is recommended that you generate a new agent_public and agent_private
        key for your standalone agent. This can be done using the ``vctl auth keypair``
        command on your primary volttron platform. If you plan to use multiple standalone agents,
        they will each need their own keypair.

5. Add standalone agent key to volttron platform
   
   * Copy the public key from settings.py in the StandAloneMatLab folder.

   * While the primary volttron platform is running on the linux machine, 
     add the agent public key using the vctl auth command.
     
   .. code::
        
        vctl auth add --credentials <standalone agent public key>

6. Run standalone agent


At this point, the agent is ready to run. To use the agent, navigate to the
example folder and use python to start the agent.

``cd examples\StandAloneMatLab\``

``python standalone_matlab.py``

.. note::

If you have python3 as your default python run the command ``python -2 standalone_matlab.py``


.. |github-image| image:: files/github-image.png
.. |cmd-image| image:: files/cmd-image.png
.. |env-vars-image_1| image:: files/env-vars-image_1.png
.. |env-vars-image_2| image:: files/env-vars-image_2.png
.. |cmd-image_2| image:: files/cmd-image_2.png
.. |github-zip-image| image:: files/github-zip-image.png
.. |extract-image_1| image:: files/extract-image_1.png
.. |extract-image_2| image:: files/extract-image_2.png
