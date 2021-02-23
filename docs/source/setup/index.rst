.. _setup:

.. _Building-VOLTTRON:

Installing VOLTTRON
===================

.. note:: Volttron version 7.0rc1 is currently tested for Ubuntu versions 18.04 and
     18.10 as well as Linux Mint version 19.3. Version 6.x is tested for Ubuntu
     versions 16.04 and 18.04 as well as Linux Mint version 19.1.


Install Required Software
-------------------------
Ensure that all the
:ref:`required packages <VOLTTRON-Prerequisites>` are installed.


Clone VOLTTRON source code
--------------------------
From version 6.0 VOLTTRON supports two message bus - ZMQ and RabbitMQ.  For the latest
build use the develop branch.  For a more conservative branch
please use the master branch.

::

  git clone https://github.com/VOLTTRON/volttron --branch <branch name>

For other options see: :ref:`Getting VOLTTRON <Repository-Structure>`


Setup virtual environment
-------------------------

The VOLTTRON project includes a bootstrap script which automatically
downloads dependencies and builds VOLTTRON. The script also creates a
Python virtual environment for use by the project which can be activated
after bootstrapping with `. env/bin/activate`. This activated Python
virtual environment should be used for subsequent bootstraps whenever
there are significant changes. The system's Python need only be used on
the initial bootstrap.

Steps for ZMQ
~~~~~~~~~~~~~

::

    cd <volttron clone directory>
    # VOLTTRON 7 required web packages by default so include --web
    python3 bootstrap.py --web
    source env/bin/activate

Proceed to `Testing the Installation`_.


Steps for RabbitMQ
~~~~~~~~~~~~~~~~~~

1. Install Erlang version >= 21
###############################

  For RabbitMQ based VOLTTRON, some of the RabbitMQ specific software packages have to be installed.
  If you are running an **Debian or CentOS system**, you can install the RabbitMQ dependencies by running the
  rabbit dependencies script, passing in the os name and approriate distribution as a parameter.
  The following are supported

    * debian bionic (for Ubuntu 18.04)
    * debian xenial (for Ubuntu 16.04)
    * debian xenial (for Linux Mint 18.04)
    * debian stretch (for Debian Stretch)
    * centos 7 (for CentOS 7)
    * centos 6 (for CentOS 6)

  Example command

  ::

  ./scripts/rabbit_dependencies.sh debian xenial

  **Alternatively**

  You can download and install Erlang from `Erlang Solution <https://www.erlang-solutions.com/resources/download.html>`_
  Please include OTP/components - ssl, public_key, asn1, and crypto.
  Also lock version of Erlang using the `yum-plugin-versionlock <https://access.redhat.com/solutions/98873>`_

2. Configure hostname
######################

  Rabbitmq requires a valid hostname to start.  Use the command hostname on your linux machine to verify if a valid
  hostname is set. If not add a valid hostname to the file /etc/hostname. You would need sudo access to edit this file
  If you want your rabbitmq instance to be reachable externally, then a hostname should be resolvable to a valid ip.
  In order to do this you need to have a entry in /etc/hosts file. For example, the below shows a valid /etc/hosts file

  .. code::

    127.0.0.1 localhost
    127.0.0.1 myhost

    192.34.44.101 externally_visible_hostname

  After the edit, logout and log back in for the changes to take effect.

  If you are testing with VMs make please make sure to provide unique host names for each of the VM you are using.

  .. note::

    If you change /etc/hostname after setting up rabbitmq (<refer to the step that does vcfg --rabbbitmq single), you will have to
    regenerate certificates and restart RabbitMQ.

  .. note::

    RabbitMQ startup error would show up in system log (/var/log/messages) file and not in RabbitMQ logs
    ($RABBITMQ_HOME/var/log/rabbitmq/rabbitmq@hostname.log where $RABBITMQ_HOME is <install dir>/rabbitmq_server-3.7.7)

3. Bootstrap
############

  Install the required software by running the bootstrap script with --rabbitmq option

  ::

      cd volttron

      # python3 bootstrap.py --help will show you all of the "package options" such as
      # installing required packages for volttron central or the platform agent.
      # In VOLTTRON 7 web packages are required so include --web in addition to --rabbitmq

      python3 bootstrap.py --web --rabbitmq [optional install directory defaults to
       <user_home>/rabbitmq_server]

  .. note:: If your PYTHON_PATH is configured for Python 2.7, you'll need to use
    ``python3 bootstrap.py ..``

  This will build the platform and create a virtual Python environment and
  dependencies for RabbitMQ. It also installs RabbitMQ server as the current user.
  If an install path is provided, path should exists and be writeable. RabbitMQ
  will be installed under <install dir>/rabbitmq_server-3.7.7 Rest of the
  documentation refers to the directory <install dir>/rabbitmq_server-3.7.7 as
  $RABBITMQ_HOME

  You can check if RabbitMQ server is installed by checking it's status.

  ::

     $RABBITMQ_HOME/sbin/rabbitmqctl status


  Please note, RABBITMQ_HOME environment variable can be set in ~/.bashrc. If doing so,
  it needs to be set to RabbitMQ installation directory (default path is
  <user_home>/rabbitmq_server/rabbitmq_server-3.7.7)

  ::

     echo 'export RABBITMQ_HOME=$HOME/rabbitmq_server/rabbitmq_server-3.7.7'|tee --append ~/.bashrc | source ~/.bashrc
     # Reload the environment variables in the current shell
     source ~/.bashrc


4. Activate the environment
###########################

  ::

    source env/bin/activate

5. Create RabbitMQ setup for VOLTTRON
######################################

  ::

    vcfg --rabbitmq single [optional path to rabbitmq_config.yml]

  Refer to examples/configurations/rabbitmq/rabbitmq_config.yml for a sample configuration file. At a minimum you would
  need to provide the host name and a unique common-name (under certificate-data) in the
  configuration file. Note. common-name must be unique and the general conventions is to use -root-ca.

  Running the above command without the optional configuration file parameter will prompt user for all the
  needed data at the command prompt and use that to generate a rabbitmq_config.yml file in VOLTTRON_HOME
  directory.

  This scripts creates a new virtual host and creates SSL certificates needed for this VOLTTRON instance.
  These certificates get created under the sub directory "certificates" in your VOLTTRON home
  (typically in ~/.volttron). It then creates the main VIP exchange named "volttron" to route message
  between platform and agents and alternate exchange to capture unrouteable messages.

  NOTE: We configure RabbitMQ instance for a single volttron_home and volttron_instance. This script will
  confirm with the user the volttron_home to be configured. volttron instance name will be read from
  volttron_home/config if available, if not user will be prompted for volttron instance name. To run the
  scripts without any prompts, save the volttron instance name in volttron_home/config file and pass the
  volttron home directory as command line argument For example: "vcfg --vhome /home/vdev/.new_vhome --rabbitmq single"

  Following is the example inputs for "vcfg --rabbitmq single" command. Since no config file is passed the
  script prompts for necessary details.

  ::

    Your VOLTTRON_HOME currently set to: /home/vdev/new_vhome2

    Is this the volttron you are attempting to setup?  [Y]:
    Creating rmq config yml
    RabbitMQ server home: [/home/vdev/rabbitmq_server/rabbitmq_server-3.7.7]:
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
    INFO:rmq_setup.pyc:**Started rmq server at /home/vdev/rabbitmq_server/rabbitmq_server-3.7.7
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
    INFO:rmq_setup.pyc:**Started rmq server at /home/vdev/rabbitmq_server/rabbitmq_server-3.7.7
    INFO:rmq_setup.pyc:

    #######################

    Setup complete for volttron home /home/vdev/new_vhome2 with instance name=volttron1
    Notes:
    - Please set environment variable VOLTTRON_HOME to /home/vdev/new_vhome2 before starting volttron
    - On production environments, restrict write access to
    /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt to only admin user. For example: sudo chown root /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt
    - A new admin user was created with user name: volttron1-admin and password=default_passwd.
    You could change this user's password by logging into https://cs_cbox.pnl.gov:15671/ Please update /home/vdev/new_vhome2/rabbitmq_config.yml if you change password

    #######################


Testing the Installation
------------------------

We are now ready to start VOLTTRON instance. If configured with RabbitMQ message bus a config file would have been
generated in $VOLTTRON_HOME/config with the entry message-bus=rmq. If you need to revert back to ZeroMQ based VOLTTRON,
you will have to either remove "message-bus" parameter or set it to default "zmq" in $VOLTTRON_HOME/config.
The following command starts volttron process in the background

::

  volttron -vv -l volttron.log&

This enters the virtual Python environment and then starts the platform in debug (vv) mode with a log file
named volttron.log. Alternatively you can use the utility script start-volttron script that does the same. To stop
stop volttron you can use the stop-volttron script.

::

  ./start-volttron


.. warning::
    If you plan on running VOLTTRON in the background and detaching it from the
    terminal with the ``disown`` command be sure to redirect stderr and stdout to ``/dev/null``.
    Some libraries which VOLTTRON relies on output directly to stdout and stderr.
    This will cause problems if those file descriptors are not redirected to ``/dev/null``

    ::

        #To start the platform in the background and redirect stderr and stdout
        #to /dev/null
        volttron -vv -l volttron.log > /dev/null 2>&1&



Installing and Running Agents
-----------------------------

VOLTTRON platform comes with several built in services and example agents out of the box. To install a agent
use the script install-agent.py

::

  python scripts/install-agent.py -s <top most folder of the agent> [-c <config file. Might be optional for some agents>]


For example, we can use the command to install and start the Listener Agent - a simple agent that periodically publishes
heartbeat message and listens to everything on the message bus. Install and start the Listener agent using the
following command.

::

  python scripts/install-agent.py -s examples/ListenerAgent --start


Check volttron.log to ensure that the listener agent is publishing heartbeat messages.

::

  tail volttron.log

::

  2016-10-17 18:17:52,245 (listeneragent-3.2 11367) listener.agent INFO: Peer: 'pubsub', Sender: 'listeneragent-3.2_1':, Bus: u'', Topic: 'heartbeat/listeneragent-3.2_1', Headers: {'Date': '2016-10-18T01:17:52.239724+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0'}, Message: {'status': 'GOOD', 'last_updated': '2016-10-18T01:17:47.232972+00:00', 'context': 'hello'}


You can also use the vctl or volttron-ctl command to start, stop or check the status of an agent

::

    (volttron)volttron@volttron1:~/git/rmq_volttron$ vctl status
      AGENT                  IDENTITY            TAG           STATUS          HEALTH
    6 listeneragent-3.2      listeneragent-3.2_1               running [13125] GOOD
    f master_driveragent-3.2 platform.driver     master_driver

::

    vctl stop <agent id>


To stop the platform:

::

  volttron-ctl shutdown --platform

or

::

  ./stop-volttron

**Note:** The default working directory is ~/.volttron. The default
directory for creation of agent packages is ~/.volttron/packaged



Next Steps
----------

Now that the project is configured correctly:

See the following links for core services and volttron features:

 * :ref:`Core Services<core-services>`
 * :ref:`Platform Specifications<platform-specifications>`

See the following links for agent development:

 * :ref:`Agent Development <Agent-Development>`
 * :ref:`VOLTTRON Development in Eclipse <Eclipse>`
 * :ref:`VOLTTRON Development in PyCharm <Pycharm-Dev-Environment>`


Please refer to related topics to for advanced setup instructions

Related Topics
--------------

.. toctree::
    :glob:
    :maxdepth: 2

    RabbitMQ/index
    *

