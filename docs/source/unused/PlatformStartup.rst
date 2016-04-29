Platform Startup
----------------

With volttron-lite running, you need to perform the following commands:

-  Install the agent executable: volttron-ctrl install-executable \\
-  Install agent launch file: volttron-ctrl load-agent \\ [\\]
-  Enable automatic starting of agent: volttron-ctrl enable-agent \\
-  Test start the agent: volttron-ctrl start \\

Then restart volttron-lite and the agent should start automatically.
Autostart can be skipped using the --skip-autstart command-line option.

By convention, agents should have either a .service or .agent suffix.
.service agents are considered essential to the platform and are started
before other agents. Below is an example.

::

    [volttron]$ . bin/activate
    (volttron)[volttron]$ cd examples/ListenerAgent
    (volttron)[ListenerAgent]$ python setup.py bdist_egg
    ...
    creating 'dist/listeneragent-3.0-py2.7.egg' and adding 'build/bdist.linux-x86_64/egg' to it
    ...
    (volttron)[ListenerAgent]$ volttron-ctrl install-executable dist/listeneragent-3.0-py2.7.egg 
    (volttron)[ListenerAgent]$ volttron-ctrl load listeneragent.launch.json listener.agent
    (volttron)[ListenerAgent]$ volttron-ctrl list-executables
    listeneragent-3.0-py2.7.egg
    (volttron)[ListenerAgent]$ volttron-ctrl list-agents
    AGENT           AUTOSTART  STATUS
    listener.agent  disabled         
    (volttron)[ListenerAgent]$ volttron-ctrl enable-agent listener.agent
    (volttron)[ListenerAgent]$ volttron-ctrl list-agents
    AGENT           AUTOSTART  STATUS
    listener.agent   enabled         
    (volttron)[ListenerAgent]$ volttron-ctrl start listener.agent
    (volttron)[ListenerAgent]$ volttron-ctrl list-agents
    AGENT           AUTOSTART  STATUS
    listener.agent   enabled   running
    (volttron)[ListenerAgent]$ volttron-ctrl stop listener.agent
    (volttron)[ListenerAgent]$ volttron-ctrl list-agents
    AGENT           AUTOSTART  STATUS
    listener.agent   enabled        0

Full `ExampleSetup <ExampleSetup>`__
