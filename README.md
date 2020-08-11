![image](docs/source/images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/fcf58045b4804edf8f4d3ecde3016f76)](https://app.codacy.com/gh/VOLTTRON/volttron?utm_source=github.com&utm_medium=referral&utm_content=VOLTTRON/volttron&utm_campaign=Badge_Grade_Settings)

VOLTTRON™ is an open source platform for distributed sensing and control. The
platform provides services for collecting and storing data from buildings and
devices and provides an environment for developing applications which interact
with that data.

[![Build Status](https://travis-ci.org/VOLTTRON/volttron.svg?branch=develop)](https://travis-ci.org/VOLTTRON/volttron)

## Features

-   [Message Bus](https://volttron.readthedocs.io/en/latest/core_services/messagebus/index.html#messagebus-index) allows agents to subcribe to data sources and publish results and messages.
-   [Driver framework](https://volttron.readthedocs.io/en/latest/core_services/drivers/index.html#volttron-driver-framework) for collecting data from and sending control actions to buildings and devices.
-   [Historian framework](https://volttron.readthedocs.io/en/latest/core_services/historians/index.html#historian-index) for storing data.
-   [Agent lifecycle managment](https://volttron.readthedocs.io/en/latest/core_services/control/AgentManagement.html#agentmanagement) in the platform
-   [Web UI](https://volttron.readthedocs.io/en/latest/core_services/service_agents/central_management/VOLTTRON-Central.html#volttron-central) for managing deployed instances from a single central instance.

## Installation

VOLTTRON is written in Python 3.6+ and runs on Linux Operating Systems. For
users unfamiliar with those technologies, the following resources are recommended:

-   <https://docs.python.org/3.6/tutorial/>
-   <http://ryanstutorials.net/linuxtutorial>

### 1. Install prerequisites

(<https://volttron.readthedocs.io/en/latest/setup/VOLTTRON-Prerequisites.html#volttron-prerequisites>).

From version 7.0, VOLTTRON requires python 3 with a minimum version of 3.6; it is tested only systems supporting that as a native package.
On Debian-based systems (Ubuntu bionic, debian buster, raspbian buster), these can all be installed with the following commands:

```sh
sudo apt-get update
sudo apt-get install build-essential libffi-dev python3-dev python3-venv openssl libssl-dev libevent-dev git
 ```
(Note: `libffi-dev` seems to only be required on arm-based systems.)

 On Redhat or CENTOS systems, these can all be installed with the following command:
```sh
sudo yum update
sudo yum install make automake gcc gcc-c++ kernel-devel python3.6-devel pythone3.6-venv openssl openssl-devel libevent-devel git
 ```

### 2. Clone VOLTTRON code

From version 6.0, VOLTTRON supports two message buses - ZMQ and RabbitMQ. 

```sh
git clone https://github.com/VOLTTRON/volttron --branch <branch name>
```

### 3. Setup virtual environment

#### Steps for ZMQ

Run the following command to install all required packages

```sh
cd <volttron clone directory>
python3 bootstrap.py
source env/bin/activate
```

Proceed to step 4.

You can deactivate the environment at any time by running `deactivate`.

#### Steps for RabbitMQ

##### 1. Install Erlang version 21 packages

For RabbitMQ based VOLTTRON, some of the RabbitMQ specific software packages have to be installed.

###### On Debian based systems and CentOS 6/7

If you are running an Debian or CentOS system, you can install the RabbitMQ dependencies by running the rabbit 
  dependencies script, passing in the OS name and appropriate distribution as parameters. The following are supported:

-   `debian bionic` (for Ubuntu 18.04)

-   `debian xenial` (for Ubuntu 16.04)

-   `debian xenial` (for Linux Mint 18.04)

-   `debian stretch` (for Debian Stretch)

-   `debian buster` (for Debian Buster)

-   `raspbian buster` (for Raspbian/Raspberry Pi OS buster)

Example command:

```sh
./scripts/rabbit_dependencies.sh debian xenial
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
2020-04-20 18:49:31,395 (listeneragent-3.3 13458) __main__ INFO: Peer: pubsub, Sender: listeneragent-3.2_1:, Bus: , Topic: heartbeat/listeneragent-3.2_1, Headers: {'TimeStamp': '2020-04-20T18:49:31.393651+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
'GOOD'
2020-04-20 18:49:36,394 (listeneragent-3.3 13458) __main__ INFO: Peer: pubsub, Sender: listeneragent-3.2_1:, Bus: , Topic: heartbeat/listeneragent-3.2_1, Headers: {'TimeStamp': '2020-04-20T18:49:36.392294+00:00', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
'GOOD'
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

## Acquiring Third Party Agent Code

Third party agents are available under the volttron-applications repository. In
order to use those agents, clone the volttron-applications repository into the same
directory as the VOLTTRON source code:

```sh
cd <parent directory of volttron>
git clone https://github.com/VOLTTRON/volttron-applications.git develop
```

## Contribute

How to [contribute](http://volttron.readthedocs.io/en/latest/community_resources/index.html#contributing-back) back:

-   Issue Tracker: <https://github.com/VOLTTRON/volttron/issues>
-   Source Code: <https://github.com/VOLTTRON/volttron>

## Support

There are several options for VOLTTRONTM [support](https://volttron.readthedocs.io/en/latest/community_resources/index.html#volttron-community).

-   A VOLTTRONTM office hours telecon takes place every other Friday at 11am Pacific over Zoom.
-   A mailing list for announcements and reminders
-   The VOLTTRONTM contact email for being added to office hours, the mailing list, and for inquiries is: volttron@pnnl.gov
-   The preferred method for questions is through stackoverflow since this is easily discoverable by others who may have the same issue. <https://stackoverflow.com/questions/tagged/volttron>
-   GitHub issue tracker for feature requests, bug reports, and following development activities <https://github.com/VOLTTRON/volttron/issues>
-   VOLTTRON now has a Slack channel - Sign up here: <https://volttron-community.signup.team/>

## License

The project is [licensed](LICENSE.md) under Apache 2.
