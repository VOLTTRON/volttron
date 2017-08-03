.. _Pycharm-Dev-Environment:

Pycharm Development Environment
===============================

Pycharm is an IDE dedicated to developing python projects. It provides coding
assistance and easy access to debugging tools as well as integration with
py.test. It is a popular tool for working with VOLTTRON.
Jetbrains provides a free community version that can be downloaded from
https://www.jetbrains.com/pycharm/


Open Pycharm and Load VOLTTRON
------------------------------

When launching Pycharm for the first time we have to tell it where to find the
VOLTTRON source code. If you have already cloned the repo then point Pycharm to
the cloned project. Pycharm also has options to access remote repositories.

Subsequent instances of Pycharm will automatically load the VOLTTRON project.

|Open Pycharm|
|Load Volttron|


Set the Project Interpreter
---------------------------

This step should be completed after running the bootstrap script in the VOLTTRON
source directory. Pycharm needs to know which python environment it should  use
when running and debugging code. This also tells Pycharm where to find python
dependencies.

|Set Project Interpreter|


Running the VOLTTRON Process
----------------------------

If you are not interested in running the VOLTTRON process itself in Pycharm then
this step can be skipped.

In **Run > Edit Configurations** create a configuration that has
`<your source dir>/env/bin/volttron` in the script field, `-vv` in the script
parameters field (to turn on verbose logging), and set the working directory to
the top level source directory.

VOLTTRON can then be run from the Run menu.

|Run Settings|


Running an Agent
----------------

Before running any agents in Pycharm we must allow VOLTTRON to talk to them.
Standalone agents do not have encryption keys set up  up as do agents installed
on the platform, so VOLTTRON will reject communications from them.

In a terminal window, cd to the VOLTTRON repository and activate the
virtual environment before starting VOLTTRON.

.. code-block:: shell

   $ source env/bin/activate
   (volttron)$ volttron -vv -l volttron.log&

We can now tell VOLTTRON to accept messages from any standalone agent run with
Pycharm. This id done with an `auth` command. This interactive command will ask
for information about who can connect to VOLTTRON. Accept all of the default
fields except for **credentials**. There enter `/.*/`

.. code-block:: shell

   (volttron)$ volttron-ctl auth add
   domain []: 
   address []: 
   user_id []: 
   capabilities (delimit multiple entries with comma) []: 
   roles (delimit multiple entries with comma) []: 
   groups (delimit multiple entries with comma) []: 
   mechanism [CURVE]: 
   credentials []: /.*/
   comments []: 
   enabled [True]:

.. warning::

   Allowing agent communications from any key is not secure and should never
   be done in a real life deployment.

Running an agent is configured similarly to running VOLTTRON proper. In
**Run > Edit Configurations** add a configuration and give it the same name
as your agent. In the Environment Variables field add the variable
`AGENT_CONFIG` that has the path to the agent's configuration file as its value.
A good place to keep configuration files is in a directory called `config` in
top level source directory; git will ignore changes to these files.

|Listener Settings|
|Run Listener|


Testing an Agent
----------------

Agent tests written in py.test can be run simply by right-clicking the tests
directory and selecting `Run 'py.test in tests`.

|Run Tests|


.. |Open Pycharm| image:: files/00_open_pycharm.png
.. |Load Volttron| image:: files/01_load_volttron.png
.. |Set Project Interpreter| image:: files/02_set_project_interpreter.png
.. |Run Settings| image:: files/03_run_settings.png
.. |Listener Settings| image:: files/04_listener_settings.png
.. |Run Listener| image:: files/05_run_listener.png
.. |Run Tests| image:: files/06_run_tests.png
