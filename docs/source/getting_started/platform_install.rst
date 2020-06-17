.. _Platform-Installation:

================================
Installing the VOLTTRON Platform
================================

VOLTTRON is written in Python 3.6+ and runs on Linux Operating Systems. For users unfamiliar with those technologies,
the following resources are recommended:

-   <https://docs.python.org/3.6/tutorial/>
-   <http://ryanstutorials.net/linuxtutorial>

Step 1 - Install prerequisites
==============================

(<https://volttron.readthedocs.io/en/latest/setup/VOLTTRON-Prerequisites.html#volttron-prerequisites>).

From version 7.0, VOLTTRON requires Python 3 with a minimum version of 3.6; it is tested only systems supporting that as
a native package.  On Debian-based systems (Ubuntu Bionic, Debian Buster, Raspbian Buster), these can all be installed
with the following commands:

.. code-block:: console

    sudo apt-get update
    sudo apt-get install build-essential libffi-dev python3-dev python3-venv openssl libssl-dev libevent-dev git
     ```

.. note:: `libffi-dev` seems to only be required on arm-based systems

On Redhat or CENTOS systems, these can all be installed with the following command:

.. code-block:: console

    sudo yum update
    sudo yum install make automake gcc gcc-c++ kernel-devel python3.6-devel pythone3.6-venv openssl openssl-devel libevent-devel git


Step 2 - Clone VOLTTRON code
============================

.. code-block:: console

    git clone https://github.com/VOLTTRON/volttron --branch <branch name>


Step 3 - Setup Python virtual environment
=========================================

From version 6.0, VOLTTRON supports two message buses - ZeroMQ (ZMQ) and RabbitMQ (RMQ), please follow the following
steps corresponding to the message bus for your deployment.

Setup steps for ZMQ
-------------------

Run the following command to install all required packages:

.. code-block:: console

    cd <volttron clone directory>
    python3 bootstrap.py
    source env/bin/activate

Then proceed to step 4

.. note:: You can deactivate the environment at any time by running `deactivate`

Setup steps for RabbitMQ
------------------------


For RabbitMQ based VOLTTRON, some of the additional RabbitMQ specific software packages have to be installed:

1. Install Erlang version 21 packages

###### On Debian based systems (other than Raspbian) and CentOS 6/7

If you are running an Debian or CentOS system, you can install the RabbitMQ dependencies by running the rabbit
  dependencies script, passing in the OS name and appropriate distribution as parameters. The following are supported:

-   `debian bionic` (for Ubuntu 18.04)

-   `debian xenial` (for Ubuntu 16.04)

-   `debian xenial` (for Linux Mint 18.04)

-   `debian stretch` (for Debian Stretch)

Example command:

```sh
./scripts/rabbit_dependencies.sh debian xenial
```

###### On Raspbian buster

To get the rabbmq dependencies, install the system rabbitmq-server package, and disable the system daemon with the following commands:

```sh
sudo apt-get install rabbitmq-server
sudo systemctl stop rabbitmq-server
sudo systemctl disable rabbitmq-server
```

###### Alternatively

You can download and install Erlang from [Erlang Solutions](https://www.erlang-solutions.com/resources/download.html).
Please include OTP/components - ssl, public_key, asn1, and crypto.
Also lock your version of Erlang using the [yum-plugin-versionlock](https://access.redhat.com/solutions/98873)

##### 2. Configure hostname

Make sure that your hostname is correctly configured in /etc/hosts.
See (<https://stackoverflow.com/questions/24797947/os-x-and-rabbitmq-error-epmd-error-for-host-xxx-address-cannot-connect-to-ho>). If you are testing with VMs make please make sure to provide unique host names for each of the VM you are using.

The hostname should be resolvable to a valid IP when running on bridged mode. RabbitMQ checks for this during initial
boot. Without this (for example, when running on a VM in NAT mode) RabbitMQ  start would fail with the error "unable to
connect to empd (port 4369) on <hostname>." Note: RabbitMQ startup error would show up in syslog (/var/log/messages) file
and not in RabbitMQ logs (/var/log/rabbitmq/rabbitmq@hostname.log)

##### 3. Bootstrap

```sh
cd volttron
python3 bootstrap.py --rabbitmq [optional install directory. defaults to
<user_home>/rabbitmq_server]
```

This will build the platform and create a virtual Python environment and
dependencies for RabbitMQ. It also installs RabbitMQ server as the current user.
If an install path is provided, that path should exist and the user should have
write permissions. RabbitMQ will be installed under `<install dir>/rabbitmq_server-3.7.7`.
The rest of the documentation refers to the directory `<install dir>/rabbitmq_server-3.7.7` as
`$RABBITMQ_HOME`

You can check if the RabbitMQ server is installed by checking its status. Please
note, the `RABBITMQ_HOME` environment variable can be set in ~/.bashrc. If doing so,
it needs to be set to the RabbitMQ installation directory (default path is
`<user_home>/rabbitmq_server/rabbitmq_server-3.7.7`)

```sh
echo 'export RABBITMQ_HOME=$HOME/rabbitmq_server/rabbitmq_server-3.7.7'|sudo tee --append ~/.bashrc
source ~/.bashrc

$RABBITMQ_HOME/sbin/rabbitmqctl status
```

##### 4. Activate the environment

```sh
source env/bin/activate
```

You can deactivate the environment at any time by running `deactivate`.

##### 5. Create RabbitMQ setup for VOLTTRON:

```sh
vcfg --rabbitmq single [optional path to rabbitmq_config.yml]
```

Refer to [examples/configurations/rabbitmq/rabbitmq_config.yml](examples/configurations/rabbitmq/rabbitmq_config.yml)
for a sample configuration file.
At a minimum you will need to provide the host name and a unique common-name
(under certificate-data) in the configuration file. Note: common-name must be
unique and the general convention is to use `<voltttron instance name>-root-ca`.

Running the above command without the optional configuration file parameter will
cause the user user to be prompted for all the required data in the command prompt
vcfg will use that data to generate a rabbitmq_config.yml file in the `VOLTTRON_HOME`
directory.

If the above configuration file is being used as a basis, be sure to update it with
the hostname of the deployment (this should be the fully qualified domain name
of the system).

This script creates a new virtual host and creates SSL certificates needed
for this VOLTTRON instance. These certificates get created under the subdirectory
"certificates" in your VOLTTRON home (typically in ~/.volttron). It
then creates the main VIP exchange named "volttron" to route message between
the platform and agents and alternate exchange to capture unrouteable messages.

NOTE: We configure the RabbitMQ instance for a single volttron_home and
volttron_instance. This script will confirm with the user the volttron_home to
be configured. The VOLTTRON instance name will be read from volttron_home/config
if available, if not the user will be prompted for VOLTTRON instance name. To
run the scripts without any prompts, save the the VOLTTRON instance name in
volttron_home/config file and pass the VOLTTRON home directory as a command line
argument. For example: `vcfg --vhome /home/vdev/.new_vhome --rabbitmq single`

The Following are the example inputs for `vcfg --rabbitmq single` command. Since no
config file is passed the script prompts for necessary details.

```sh
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

-   Please set environment variable `VOLTTRON_HOME` to `/home/vdev/new_vhome2` before starting volttron

-   On production environments, restrict write access to
    /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt to only admin user. For example: sudo chown root /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt

-   A new admin user was created with user name: volttron1-admin and password=default_passwd.
    You could change this user's password by logging into <https://cs_cbox.pnl.gov:15671/> Please update /home/vdev/new_vhome2/rabbitmq_config.yml if you change password

#######################
```

### 4. Test

We are now ready to start the VOLTTRON instance. If configured with a RabbitMQ message bus a config file would have been
 generated in `$VOLTTRON\_HOME/config` with the entry `message-bus=rmq`. If you need to revert back to ZeroMQ based
 VOLTTRON, you will have to either remove "message-bus" parameter or set it to default "zmq" in `$VOLTTRON\_HOME/config`
  and restart the volttron process. The following command starts the VOLTTORN process in the background:

```sh
volttron -vv -l volttron.log &
```

This command causes the shell to enter the virtual Python environment and then starts the platform in debug (vv) mode
with a log file named volttron.log.

Next, start an example listener to see it publish and subscribe to the message bus:

```sh
scripts/core/upgrade-listener
```

This script handles several different commands for installing and starting an agent after removing an old copy. This
simple agent publishes a heartbeat message and listens to everything on the message bus. Look at the VOLTTRON log to see
the activity:

```sh
tail volttron.log
```

Listener agent heartbeat publishes appear in the logs as:

```sh
2016-10-17 18:17:52,245 (listeneragent-3.2 11367) listener.agent INFO: Peer: 'pubsub', Sender: 'listeneragent-3.2_1'
:, Bus: u'', Topic: 'heartbeat/listeneragent-3.2_1', Headers:
{'Date': '2016-10-18T01:17:52.239724+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0'},
Message: {'status': 'GOOD', 'last_updated': '2016-10-18T01:17:47.232972+00:00', 'context': 'hello'}
```

To top the platform run the following command:

```sh
./stop-volttron
```

## Next Steps

There are several [walkthroughs](https://volttron.readthedocs.io/en/latest/devguides/index.html#devguides-index) to explore additional aspects of the platform:

-   [Agent Development Walkthrough](https://volttron.readthedocs.io/en/latest/devguides/agent_development/Agent-Development.html#agent-development)
-   Demonstration of the [management UI](https://volttron.readthedocs.io/en/latest/devguides/walkthroughs/VOLTTRON-Central-Demo.html#volttron-central-demo)
-   RabbitMQ setup with Federation and Shovel plugins
-   Backward compatibility with the RabbitMQ message bus
