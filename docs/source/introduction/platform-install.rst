.. _Platform-Installation:

.. role:: bash(code)
   :language: bash

=======================
Installing the Platform
=======================

VOLTTRON is written in Python 3.6+ and runs on Linux Operating Systems.  For users unfamiliar with those technologies,
the following resources are recommended:

-   `Python 3.6 Tutorial <https://docs.python.org/3.6/tutorial>`_
-   `Linux Tutorial <http://ryanstutorials.net/linuxtutorial>`_

This guide will specify commands to use to successfully install the platform on supported Linux distributions, but a
working knowledge of Linux will be helpful for troubleshooting and may improve your ability to get more out of your
deployment.

.. note::

    Volttron version 7.0rc1 is currently tested for Ubuntu versions 18.04 and 18.10 as well as Linux Mint version 19.3.
    Version 6.x is tested for Ubuntu versions 16.04 and 18.04 as well as Linux Mint version 19.1.


.. _Platform-Prerequisites:

Step 1 - Install prerequisites
==============================

The following packages will need to be installed on the system:

*  git
*  build-essential
*  python3.6-dev
*  python3.6-venv
*  openssl
*  libssl-dev
*  libevent-dev

On **Debian-based systems**, these can all be installed with the following command:

.. code-block:: bash

       sudo apt-get update
       sudo apt-get install build-essential python3-dev python3-venv openssl libssl-dev libevent-dev git

On Ubuntu-based systems, available packages allow you to specify the Python3 version, 3.6 or greater is required
(Debian itself does not provide those packages).

.. code-block:: bash

       sudo apt-get install build-essential python3.6-dev python3.6-venv openssl libssl-dev libevent-dev git


On arm-based systems (including, but not limited to, Raspbian), you must also install libffi-dev, you can do this with:

.. code-block:: bash

       sudo apt-get install libffi-dev

.. note::

    On arm-based systems, the available apt package repositories for Raspbian versions older than buster (10) do not
    seem to be able to be fully satisfied.  While it may be possible to resolve these dependencies by building from
    source, the only recommended usage pattern for VOLTTRON 7 and beyond is on raspberry pi OS 10 or newer.

On **Redhat or CENTOS systems**, these can all be installed with the following
command:

.. code-block:: bash

   sudo yum update
   sudo yum install make automake gcc gcc-c++ kernel-devel python3-devel openssl openssl-devel libevent-devel git

.. warning::
   Python 3.6 or greater is required, please ensure you have installed a supported version with :bash:`python3 --version`

If you have an agent which requires the pyodbc package, install the following additional requirements:

*  freetds-bin
*  unixodbc-dev

On **Debian-based systems** these can be installed with the following command:

.. code-block:: bash

    sudo apt-get install freetds-bin  unixodbc-dev

On **Redhat or CentOS systems**, these can be installed from the Extra Packages for Enterprise Linux (EPEL) repository:

.. code-block:: bash

    sudo yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sudo yum install freetds unixODBC-devel

.. note::
    The above command to install the EPEL repository is for Centos/Redhat 8. Change the number to match your OS version.
    EPEL packages are included in Fedora repositories, so installing EPEL is not required on Fedora.

It may be possible to deploy VOLTTRON on a system not listed above but may involve some troubleshooting and dependency
management on the part of the user.

In order to support historians, the python installation must include the built-in sqlite3 support (a compile time option).
This is included in all of the linux distribution packages referenced above, which is the recommended and supported way of running python.
In cases where a user needs to compile their own python (not an officially supported configuration), make sure that the sqlite3 option is enabled.

Step 2 - Clone VOLTTRON code
============================


.. _Repository-Structure:

Repository Structure
--------------------

There are several options for using the VOLTTRON code depending on whether you require the most stable version of the
code or want the latest updates as they happen. In order of decreasing stability and increasing currency:

* `Main` - Most stable release branch, current major release is 7.0.  This branch is default.
* `develop` - contains the latest `finished` features as they are developed.  When all features are stable, this branch
  will be merged into `Main`.

  .. note::

     This branch can be cloned by those wanting to work from the latest version of the platform but should not be
     used in deployments.

* Features are developed on “feature” branches or developers' forks of the main repository.  It is not recommended to
  clone these branches except for exploring a new feature.

.. note::

    VOLTTRON versions 6.0 and newer support two message buses - ZMQ and RabbitMQ.

.. code-block:: bash

    git clone https://github.com/VOLTTRON/volttron --branch <branch name>


Step 3 - Setup virtual environment
==================================

The :ref:`bootstrap.py <Bootstrap-Process>` script in the VOLTTRON root directory will create a
`virtual environment <https://docs.python-guide.org/dev/virtualenvs/>`_ and install the package's Python dependencies.
Options exist for upgrading or rebuilding existing environments, and for adding additional dependencies for optional
drivers and agents included in the repository.

.. note::

    The :bash:`--help` option for `bootstrap.py` can specified to display all available optional parameters.


.. _ZeroMQ-Install:

Steps for ZeroMQ
----------------

Run the following command to install all required packages:

.. code-block:: bash

    cd <volttron clone directory>
    python3 bootstrap.py

Then activate the Python virtual environment:

.. code-block:: bash

    source env/bin/activate

Proceed to step 4.

.. note::

    You can deactivate the environment at any time by running `deactivate`.


.. _RabbitMQ-Install:

Steps for RabbitMQ
------------------

Step 1 - Install Required Packages and Activate the Virtual Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Setting up RabbmitMQ requires additional steps; but before running those steps we still need to install the required
packages and activate the virtual environment just as we did in the Steps for ZeroMQ. To do so, see :ref:`ZeroMQ-Install`.
Once finished, proceed to the next step.


Step 2 - Install Erlang packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For RabbitMQ based VOLTTRON, some of the RabbitMQ specific software packages have to be installed.


On Debian based systems and CentOS 8
""""""""""""""""""""""""""""""""""""

If you are running a Debian or CentOS 8 system, you can install the RabbitMQ dependencies by running the
"rabbit_dependencies.sh" script, passing in the OS name and appropriate distribution as parameters. The
following are supported:

*   `debian bionic` (for Ubuntu 18.04)

*   `debian focal` (for Ubuntu 20.04)


Example command:

.. code-block:: bash

    ./scripts/rabbit_dependencies.sh debian xenial


Alternatively
"""""""""""""

You can download and install Erlang from `Erlang Solutions <https://www.erlang-solutions.com/resources/download.html>`_.
Please include OTP/components - ssl, public_key, asn1, and crypto.
Also lock your version of Erlang using the `yum-plugin-versionlock <https://access.redhat.com/solutions/98873>`_.

.. note::
    Currently VOLTTRON only officially supports specific versions of Erlang for each operating system:
          * 1:24.1.7-1 for Debian
          * 24.2-1.el8 for CentOS 8


Step 3 - Configure hostname
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure that your hostname is correctly configured in /etc/hosts.
See this `StackOverflow post <https://stackoverflow.com/questions/24797947/os-x-and-rabbitmq-error-epmd-error-for-host-xxx-address-cannot-connect-to-ho>`_.
If you are testing with VMs make please make sure to provide unique host names for each of the VMs you are using.

The hostname should be resolvable to a valid IP when running on bridged mode. RabbitMQ checks for this during initial
boot. Without this (for example, when running on a VM in NAT mode) RabbitMQ  start-up would fail with the error "unable
to connect to empd (port 4369) on <hostname>."

.. note::

    RabbitMQ startup error would show up in the VM's syslog (/var/log/messages) file and not in RabbitMQ logs
    (/var/log/rabbitmq/rabbitmq@hostname.log)


Step 4 - Bootstrap the environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    cd volttron
    python3 bootstrap.py --rabbitmq [optional install directory. defaults to <user_home>/rabbitmq_server]

This will build the platform and create a virtual Python environment and dependencies for RabbitMQ.  It also installs
RabbitMQ server as the current user.  If an install path is provided, that path should exist and the user should have
write permissions.  RabbitMQ will be installed under `<install dir>/rabbitmq_server-<rmq-version>`. The rest of the
documentation refers to the directory `<install dir>/rabbitmq_server-<rmq-version>` as `$RABBITMQ_HOME`.

.. note::

   There are many additional :ref:`options for bootstrap.py <Bootstrap-Process>` for including dependencies, altering
   the environment, etc.

By bootstrapping the environment for RabbitMQ, an environmental variable $RABBITMQ_HOME is created for your convenience.
Thus, you can use $RABBITMQ_HOME to see if the RabbitMQ server is installed by checking its status:

.. code-block:: bash

    $RABBITMQ_HOME/sbin/rabbitmqctl status

.. note::

    The `RABBITMQ_HOME` environment variable can be set in ~/.bashrc. If doing so, it needs to be set to the RabbitMQ
    installation directory (default path is `<user_home>/rabbitmq_server/rabbitmq_server-3.9.7`)

.. code-block:: bash

    echo 'export RABBITMQ_HOME=$HOME/rabbitmq_server/rabbitmq_server-3.9.7'|sudo tee --append ~/.bashrc
    source ~/.bashrc
    $RABBITMQ_HOME/sbin/rabbitmqctl status


Step 5 - Configure RabbitMQ setup for VOLTTRON
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    vcfg rabbitmq single [--config optional path to rabbitmq_config.yml]

A sample configuration file can be found in the VOLTTRON repository in **examples/configurations/rabbitmq/rabbitmq_config.yml**.
At a minimum you will need to provide the host name and a unique common-name (under certificate-data) in the configuration file.

.. note::

    common-name must be unique and the general convention is to use `<volttron instance name>-root-ca`.

Running the above command without the optional configuration file parameter will cause the user user to be prompted for
all the required data in the command prompt. "vcfg" will use that data to generate a rabbitmq_config.yml file in the
:term:`VOLTTRON_HOME` directory.

.. note::

    If the above configuration file is being used as a basis for creating your own configuration file, be sure to update
    it with the hostname of the deployment (this should be the fully qualified domain name of the system).

This script creates a new virtual host and creates SSL certificates needed for this VOLTTRON instance.  These
certificates get created under the subdirectory "certificates" in your VOLTTRON home (typically in ~/.volttron). It
then creates the main VIP exchange named "volttron" to route message between the platform and agents and alternate
exchange to capture unrouteable messages.

.. note::

    We configure the RabbitMQ instance for a single :term:`VOLTTRON_HOME` and :term:`VOLTTRON_INSTANCE`. This script
    will confirm with the user the volttron_home to be configured.  The VOLTTRON instance name will be read from
    `volttron_home/config` if available, if not the user will be prompted for VOLTTRON instance name.  To run the
    scripts without any prompts, save the the VOLTTRON instance name in volttron_home/config file and pass the VOLTTRON
    home directory as a command line argument. For example:

    .. code-block:: bash

       vcfg --vhome /home/vdev/.new_vhome --rabbitmq single

.. note::

    The default behavior generates a certificate which is valid for a period of 1 year.

The Following are the example inputs for `vcfg rabbitmq single` command.  Since no config file is passed the script
prompts for necessary details.

.. code-block:: console

    Your VOLTTRON_HOME currently set to: /home/vdev/new_vhome2

    Is this the volttron you are attempting to setup?  [Y]:
    Creating rmq config yml
    RabbitMQ server home: [/home/vdev/rabbitmq_server/rabbitmq_server-3.9.7]:
    Fully qualified domain name of the system: [cs_cbox.pnl.gov]:

    Enable SSL Authentication: [Y]:

    Please enter the following details for root CA certificates
    Country: [US]:
    State: Washington
    Location: Richland
    Organization: PNNL
    Organization Unit: Volttron-Team
    Common Name: [volttron1-root-ca]:
    Do you want to use default values for RabbitMQ home, ports, and virtual host: [Y]: N
    Name of the virtual host under which RabbitMQ VOLTTRON will be running: [volttron]:
    AMQP port for RabbitMQ: [5672]:
    http port for the RabbitMQ management plugin: [15672]:
    AMQPS (SSL) port RabbitMQ address: [5671]:
    https port for the RabbitMQ management plugin: [15671]:
    INFO:rmq_setup.pyc:Starting rabbitmq server
    Warning: PID file not written; -detached was passed.
    INFO:rmq_setup.pyc:**Started rmq server at /home/vdev/rabbitmq_server/rabbitmq_server-3.9.7
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
    INFO:rmq_setup.pyc:
    Checking for CA certificate

    INFO:rmq_setup.pyc:
    Root CA (/home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt) NOT Found. Creating root ca for volttron instance
    Created CA cert
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
    INFO:rmq_setup.pyc:**Stopped rmq server
    Warning: PID file not written; -detached was passed.
    INFO:rmq_setup.pyc:**Started rmq server at /home/vdev/rabbitmq_server/rabbitmq_server-3.9.7
    INFO:rmq_setup.pyc:

    #######################

    Setup complete for volttron home /home/vdev/new_vhome2 with instance name=volttron1
    Notes:

    -   Please set environment variable `VOLTTRON_HOME` to `/home/vdev/new_vhome2` before starting volttron

    -   On production environments, restrict write access to
        /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt to only admin user. For example: sudo chown root /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt

    -   A new admin user was created with user name: volttron1-admin and password=default_passwd.
        You could change this user's password by logging into <https://cs_cbox.pnl.gov:15671/> Please update /home/vdev/new_vhome2/rabbitmq_config.yml if you change password

    #######################


Test the VOLTTRON Deployment
============================

We are now ready to start VOLTTRON instance. If configured with RabbitMQ message bus a config file would have been
generated in `$VOLTTRON_HOME/config` with the entry ``message-bus=rmq``. If you need to revert back to ZeroMQ based
VOLTTRON, you will have to either remove the ``message-bus`` parameter or set it to the default "zmq" in
`$VOLTTRON_HOME/config`.

The following command starts volttron process in the background:

.. code-block:: bash

  volttron -vv -l volttron.log&

This enters the virtual Python environment and then starts the platform in debug (vv) mode with a log file
named volttron.log. Alternatively you can use the utility script start-volttron script that does the same.

.. code-block:: bash

  ./start-volttron

To stop the platform, use the `vct` command:

.. code-block:: bash

  volttron-ctl shutdown --platform

or use the included `stop-volttron` script:

.. code-block:: bash

  ./stop-volttron


.. warning::
    If you plan on running VOLTTRON in the background and detaching it from the
    terminal with the ``disown`` command be sure to redirect stderr and stdout to ``/dev/null``.
    Some libraries which VOLTTRON relies on output directly to stdout and stderr.
    This will cause problems if those file descriptors are not redirected to ``/dev/null``

    ::

        #To start the platform in the background and redirect stderr and stdout
        #to /dev/null
        volttron -vv -l volttron.log > /dev/null 2>&1&


.. _installing-and-running-agents:

Installing and Running Agents
-----------------------------

VOLTTRON platform comes with several built in services and example agents out of the box. To install a agent
use the script `install-agent.py`

.. code-block:: bash

  python scripts/install-agent.py -s <top most folder of the agent> [-c <config file. Might be optional for some agents>]


For example, we can use the command to install and start the Listener Agent - a simple agent that periodically publishes
heartbeat message and listens to everything on the message bus.  Install and start the Listener agent using the
following command:

.. code-block:: bash

  python scripts/install-agent.py -s examples/ListenerAgent --start


Check volttron.log to ensure that the listener agent is publishing heartbeat messages.

.. code-block:: bash

  tail volttron.log

.. code-block:: console

  2016-10-17 18:17:52,245 (listeneragent-3.2 11367) listener.agent INFO: Peer: 'pubsub', Sender: 'listeneragent-3.2_1':, Bus: u'', Topic: 'heartbeat/listeneragent-3.2_1', Headers: {'Date': '2016-10-18T01:17:52.239724+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0'}, Message: {'status': 'GOOD', 'last_updated': '2016-10-18T01:17:47.232972+00:00', 'context': 'hello'}


You can also use the `volttron-ctl` (or `vctl`) command to start, stop or check the status of an agent

.. code-block:: console

    (volttron)volttron@volttron1:~/git/rmq_volttron$ vctl status
      AGENT                  IDENTITY            TAG           STATUS          HEALTH
    6 listeneragent-3.2      listeneragent-3.2_1               running [13125] GOOD
    f platform_driveragent-3.2 platform.driver     platform_driver

.. code-block:: bash

    vctl stop <agent id>


.. note::

    The default working directory is ~/.volttron. The default directory for creation of agent packages is
    `~/.volttron/packaged`


Next Steps
==========

There are several walk-throughs and detailed explanations of platform features to explore additional aspects of the
platform:

*   :ref:`Agent Framework <Agent-Framework>`
*   :ref:`Driver Framework <Driver-Framework>`
*   Demonstration of the :ref:`management UI <Device-Configuration-in-VOLTTRON-Central>`
*   :ref:`RabbitMQ setup <RabbitMQ-Overview>` with Federation and Shovel plugins
