.. _VOLTTRON-Quick-Start:

.. role:: bash(code)
   :language: bash

=======================
VOLTTRON Quick Start
=======================

This tutorial has been written with the intent of helping folks get up-and-running with VOLTTRON. The tutorial is designed to deploy on Linux virtual machines. While not going too much into depth, it covers the following topics:

-   Install the VOLTTRON platform and verify the installation.
-   Get familiar with the VOLTTRON components.
-   Get familiar with the VOLTTRON commands.

Prerequisites
==============================

In this tutorial we will demonstrate installing the VOLTTRON platform at an `Ubuntu 20.04 LTS (Focal Fossa) <https://releases.ubuntu.com/20.04/>`_ Virtual machine. In order to follow the tutorial, the prerequisites are as follows:

-   Linux OS image (e.g., Ubuntu 20.04)
-   Virtualization software (e.g., VirtualBox, VMware)
-   Internet accessibility
-   sudo capability

Installation Steps
==============================

1. Install prerequisites
------------------------------

The first step is to make sure required dependencies are fulfilled. Install the dependencies with the following command:

.. code-block:: bash

       $ sudo apt-get update
       $ sudo apt-get install build-essential python3-dev python3-venv openssl libssl-dev libevent-dev git

Verify python installation with the following command:

.. code-block:: bash

       $ python3 --version

.. code-block:: bash

       # expected output similar to this
       Python 3.8.10


Similarly, verify git installation.

.. code-block:: bash

       $ git --version

.. code-block:: bash

       # expected output similar to this
       git version 2.25.1

2. Download VOLTTRON code
------------------------------

Download the VOLTTRON code to the default home directory using :code:`git clone` command.

.. code-block:: bash

       $ cd ~
       $ git clone https://github.com/VOLTTRON/volttron

.. code-block:: bash

       # expected output similar to this
       Cloning into 'volttron'...
       remote: Enumerating objects: 82987, done.
       remote: Counting objects: 100% (4892/4892), done.
       remote: Compressing objects: 100% (1971/1971), done.
       remote: Total 82987 (delta 3155), reused 4294 (delta 2890), pack-reused 78095
       Receiving objects: 100% (82987/82987), 102.73 MiB | 4.19 MiB/s, done.
       Resolving deltas: 100% (57997/57997), done.
       Checking out files: 100% (1807/1807), done.
       ...

.. note::

   In this tutorial we download the VOLTTRON code to the default home directory. 
   However, feel free to download the code to a different place as desired.

.. code-block:: bash

       # $ mkdir <path-to-dir>
       # $ cd <path-to-dir>
       # $ git clone https://github.com/VOLTTRON/volttron

After successfully downloading the VOLTTRON package, change the current working path to the code path. Then, inspect the source code files.

.. code-block:: bash

       $ cd volttron
       $ ls

.. code-block:: bash

       # expected output similar to this
       bootstrap.py     deprecated    pylintrc          requirements.py  stop-volttron
       ci-integration   docs          pytest.ini        scripts          TERMS.md
       CONTRIBUTING.md  examples      README.md         services         volttron
       COPYRIGHT        integrations  readthedocs.yml   setup.py         volttron_data
       debugging_utils  LICENSE.md    RELEASE_NOTES.md  start-volttron   volttrontesting

3. Bootstrap VOLTTRON environment
------------------------------

VOLTTRON is a Python-based platform. In this step, we will rely on the :code:`bootstrap.py` script in the root directory to bootstrap the platform environment. This process will create a virtual environment and install the package's Python dependencies.

.. note::

   VOLTTRON provides different message bus options. In this tutorial we will demonstrate the default ZeroMQ option. (Read more about :ref:`message bus<Message-Bus>`.)


Bootstrap the VOLTTRON environment by running the following command. (This may take a while.)

.. code-block:: bash

       $ python3 bootstrap.py

.. code-block:: bash

       # expected output similar to this
       UPDATE: []
       Installing required packages
       + pip install --no-deps wheel==0.30
       Collecting wheel==0.30
       Using cached
       <https://files.pythonhosted.org/packages/0c/80/16a85b47702a1f47a63c104c91abdd0a6704ee8ae3b4ce4afc49bc39f9d9/wheel-0.30.0-py2.py3-none-any.whl>
       ...


After bootstrap finished, we activate the Python virtual environment with the following command:

.. code-block:: bash

       $ source env/bin/activate

You may notice the command prompt has changed and there is the virtual environment name as prefix. e.g., :code:`(volttron) user@host:~/volttron $`. The prefix environment name indicates the virtual environment is activated.

Alternatively, you can use the following command to verify if the virtual environment is up.

.. code-block:: bash

       $ env |grep VIRTUAL_ENV |wc -l

.. code-block:: bash

       # expected output 1(virtual environment is up) or 0 (not up)


Use `deactivate` command to deactivate the virtual environment, i.e., :code:`$ deactivate volttron`. Note: if you run this command, remember to re-activate the virtual environment to follow the rest of the steps.            

.. note::

   In this tutorial the VOLTTRON platform is deployed in `virtualenv <https://virtualenv.pypa.io/en/latest/>`_. In case you choose other virtual environment, make adjustment as needed.


4. Start VOLTTRON
------------------------------

In this step, we will start the VOLTTRON platform and demonstrate several VOLTTRON commands.

Start the VOLTTRON platform with the following command:

.. code-block:: bash

       $ ./start-volttron

.. code-block:: bash

       # expected output similar to this
       ...
       Starting VOLTTRON verbosely in the background with VOLTTRON_HOME=/home/user/.volttron
       Waiting for VOLTTRON to startup..
       VOLTTRON startup complete

Check the status of VOLTTRON with the following command:

.. code-block:: bash

       $ vctl status

For fresh installation, the result might look like the following since there are no agents installed yet. 

.. code-block:: bash

       # expected output similar to this
       No installed Agents found

.. tip::

    Use :code:`vctl status` to check status. 
    This is a very useful command to inspect the status of VOLTTRON.

VOLTTRON platform comes with several built in services and example agents out of the box. In this demo, we use the Listener Agent - a simple agent that periodically publishes heartbeat message and listens to everything on the message bus. (Read more about :ref:`agent <Agent-Framework>`.)

Install the Listener agent using the following command:

.. code-block:: bash

       $ vctl install examples/ListenerAgent --tag listener


.. code-block:: bash

       # expected output similar to this
       Agent b755bae2-a3f5-44a0-b01f-81e30b989138 installed


Start the agent we just installed specified by the `listener` tag.

.. code-block:: bash

       $ vctl start --tag listener

.. code-block:: bash

       # expected output similar to this
       Starting b755bae2-a3f5-44a0-b01f-81e30b989138 listeneragent-3.3

Check the status again.

.. code-block:: bash

       $ vctl status

.. code-block:: bash

       # expected output similar to this
       UUID AGENT             IDENTITY            TAG      STATUS          HEALTH
       8 listeneragent-3.3 listeneragent-3.3_1 listener running [2192]  GOOD


From the above result, we can tell the listener agent is functioning properly!

.. tip::

    While the :code:`--tag` sub-command is optional, a tag is helpful for managing agents by adding semantic tags to different topics, so that topic can be queried by tags instead of specific topic name or topic name pattern. 

    You can choose any tag name that makes sense to you, as long as the tags are already defined in the VOLTTRON tagging schema. (Read more about :ref:`tag <Tagging-Service-Specification>`.)

In addition to the :code:`vctl status`, another way to check VOLTTRON status is by inspecting the :code:`volttron.log` file. The file provides rich information about the platform and becomes handy for debug purposes.

.. code-block:: bash

       $ tail -f volttron.log


.. code-block:: bash

       # example output (success)
       # listener agent is publishing heartbeat messages successively.
       2022-03-04 14:12:46,463 (listeneragent-3.3 2192) __main__ INFO: Peer: pubsub, Sender: listeneragent-3.3_1:, Bus: , Topic: heartbeat/listeneragent-3.3_1, Headers: {'TimeStamp': '2022-03-04T19:12:46.460096+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message: 'GOOD'
       ...


.. code-block:: bash

       # example output (error)
       2022-03-04 13:16:05,469 (listeneragent-3.3 3233) volttron.platform.vip.agent.core ERROR: No response to hello message after 10 seconds.
       2022-03-04 13:16:05,469 (listeneragent-3.3 3233) volttron.platform.vip.agent.core ERROR: Type of message bus used zmq
       2022-03-04 13:16:05,469 (listeneragent-3.3 3233) volttron.platform.vip.agent.core ERROR: A common reason for this is a conflicting VIP IDENTITY.
       2022-03-04 13:16:05,469 (listeneragent-3.3 3233) volttron.platform.vip.agent.core ERROR: Another common reason is not having an auth entry onthe target instance.
       2022-03-04 13:16:05,469 (listeneragent-3.3 3233) volttron.platform.vip.agent.core ERROR: Shutting down agent.
       ...

5. Stop VOLTTRON (Optional)
------------------------------

To stop VOLTTRON, use the following command: 

.. code-block:: bash

       $ ./stop-volttron

.. code-block:: bash

       # expected output similar to this
       Shutting down VOLTTRON

After stopping the platform, check the status again to verify the VOLTTRON platform is shut down.

.. code-block:: bash

       $ vctl status

.. code-block:: bash

       # expected output similar to this
       VOLTTRON is not running. This command requires VOLTTRON platform to be running

Clean up (Optional)
==============================

If for some reason you would like to clean up VOLTTRON, here is the guide to remove the whole VOLTTRON package

- remove the code folder (e.g., :code:`~/volttron/`)
- remove the :code:`.volttron/` folder at :code:`VOLTTRON_HOME/.volttron` (e.g., by default at :code:`~/.volttron`)

Summary
==============================

This short tutorial for VOLTTRON first-time users. We covered the following topics. 

-   VOLTTRON platform installation. (e.g., on a Virtual Machine.)
-   VOLTTRON components. (e.g., agent, message bus, tag.)
-   VOLTTRON commands. (e.g., :code:`start-volttron`, :code:`vctl status`.)


Next Steps
==============================

There are several walk-throughs and detailed explanations of platform features to explore additional aspects of the
platform:

*   :ref:`Agent Framework <Agent-Framework>`
*   :ref:`Driver Framework <Driver-Framework>`
*   Demonstration of the :ref:`management UI <Device-Configuration-in-VOLTTRON-Central>`
*   :ref:`RabbitMQ setup <RabbitMQ-Overview>` with Federation and Shovel plugins

