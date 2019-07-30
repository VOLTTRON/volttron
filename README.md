  

![image](docs/source/images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png)

Distributed Control System Platform.

VOLTTRON&trade; is an open source platform for distributed sensing and control. The
platform provides services for collecting and storing data from buildings and
devices and provides an environment for developing applications which interact
with that data.

## Features

* [Message Bus](https://volttron.readthedocs.io/en/latest/core_services/messagebus/index.html#messagebus-index) allows agents to subcribe to data sources and publish results and messages
* [Driver framework](https://volttron.readthedocs.io/en/latest/core_services/drivers/index.html#volttron-driver-framework) for collecting data from and sending control actions to buildings and devices
* [Historian framework](https://volttron.readthedocs.io/en/latest/core_services/historians/index.html#historian-index) for storing data
* [Agent lifecycle managment](https://volttron.readthedocs.io/en/latest/core_services/control/AgentManagement.html#agentmanagement) in the platform
* [Web UI](https://volttron.readthedocs.io/en/latest/core_services/service_agents/central_management/VOLTTRON-Central.html#volttron-central) for managing deployed instances from a single central instance.

## Background

VOLTTRON is written in Python 2.7 and runs on Linux Operating Systems. For
users unfamiliar with those technologies, the following resources are recommended:

https://docs.python.org/2.7/tutorial/
http://ryanstutorials.net/linuxtutorial/

## Installation

 ### 1. Install prerequisites

(https://volttron.readthedocs.io/en/latest/setup/VOLTTRON-Prerequisites.html#volttron-prerequisites).

 On Debian-based systems, these can all be installed with the following command:

 ```sh
    sudo apt-get update
    sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git
 ```
 On Redhat or CENTOS systems, these can all be installed with the following command:
 ```sh
   sudo yum update
   sudo yum install make automake gcc gcc-c++ kernel-devel python-devel openssl openssl-devel libevent-devel git
 ```

 ### 2. Clone VOLTTRON code

From version 6.0 VOLTTRON supports two message bus - ZMQ and RabbitMQ. 

```sh
git clone https://github.com/VOLTTRON/volttron --branch <branch name>
```

### 3. Setup virtual environment

#### Steps for ZMQ
Run the following command to install all required packages

```sh
cd <volttron clone directory>
python bootstrap.py
source env/bin/activate
```

Proceed to step 4. 

#### Steps for RabbitMQ

  ##### 1. Install Erlang version 21 packages

  For RabbitMQ based VOLTTRON, some of the RabbitMQ specific software packages have to be installed.

  **On Debian based systems and CentOS 6/7**

  If you are running an Debian or CentOS system, you can install the RabbitMQ dependencies by running the rabbit 
  dependencies script, passing in the os name and approriate distribution as a parameter. The following are  
  supported

  debian bionic (for Ubuntu 18.04)
  debian xenial (for Ubuntu 16.04)
  debian xenial (for Linux Mint 18.04)
  debian stretch (for Debian Stretch)
  centos 7 (for CentOS 7)
  centos 6 (for CentOS 6)

  Example command
  ```sh
  ./scripts/rabbit_dependencies.sh debian xenial
  ```

  **Alternatively**

  You can download and install Erlang from [Erlang Solutions](https://www.erlang-solutions.com/resources/download.html).
  Please include OTP/components - ssl, public_key, asn1, and crypto.
  Also lock version of Erlang using the [yum-plugin-versionlock](https://access.redhat.com/solutions/98873)

  ##### 2. Configure hostname

  Make sure that your hostname is correctly configured in /etc/hosts.
  See (https://stackoverflow.com/questions/24797947/os-x-and-rabbitmq-error-epmd-error-for-host-xxx-address-cannot-connect-to-ho). If you are testing with VMs make please make sure to provide unique host names for each of the VM you are using. 

  Hostname should be resolvable to a valid ip when running on bridged mode. RabbitMQ checks for this during
  initial boot. Without this (for example, when running on a VM in NAT mode)
  RabbitMQ  start would fail with the error "unable to connect to empd (
  port 4369) on <hostname>." Note: RabbitMQ startup error would show up in syslog (/var/log/messages) file
  and not in RabbitMQ logs (/var/log/rabbitmq/rabbitmq@hostname.log)

  ##### 3. bootstrap

  ```sh
  cd volttron
  python bootstrap.py --rabbitmq [optional install directory. defaults to
  <user_home>/rabbitmq_server]
  ```

  This will build the platform and create a virtual Python environment and
  dependencies for RabbitMQ. It also installs RabbitMQ server as the current user.
  If an install path is provided, path should exists and be writeable. RabbitMQ
  will be installed under <install dir>/rabbitmq_server-3.7.7 Rest of the
  documentation refers to the directory <install dir>/rabbitmq_server-3.7.7 as
  $RABBITMQ_HOME

  You can check if RabbitMQ server is installed by checking it's status. Please
  note, RABBITMQ_HOME environment variable can be set in ~/.bashrc. If doing so,
  it needs to be set to RabbitMQ installation directory (default path is
  <user_home>/rabbitmq_server/rabbitmq_server/rabbitmq_server-3.7.7)

  ```
  echo 'export RABBITMQ_HOME=$HOME/rabbitmq_server/rabbitmq_server-3.7.7'|sudo tee --append ~/.bashrc
  source ~/.bashrc
  ```

  ```
  $RABBITMQ_HOME/sbin/rabbitmqctl status
  ```

  ###### 4. Activate the environment

  ```sh
  source env/bin/activate
  ```

  ##### 5. Create RabbitMQ setup for VOLTTRON:
  ```
  vcfg --rabbitmq single [optional path to rabbitmq_config.yml]
  ```

  Refer to examples/configurations/rabbitmq/rabbitmq_config.yml for a sample configuration file.
  At a minimum you would need to provide the host name and a unique common-name
  (under certificate-data) in the configuration file. Note. common-name must be
  unique and the general conventions is to use  <voltttron instance name>-root-ca.

  Running the above command without the optional configuration file parameter will
  prompt user for all the needed data at the command prompt and use that to
  generate a rabbitmq_config.yml file in VOLTTRON_HOME directory.

  This scripts creates a new virtual host  and creates SSL certificates needed
  for this VOLTTRON instance. These certificates get created under the sub
  directory "certificates" in your VOLTTRON home (typically in ~/.volttron). It
  then creates the main VIP exchange named "volttron" to route message between
  platform and agents and alternate exchange to capture unrouteable messages.

  NOTE: We configure RabbitMQ instance for a single volttron_home and
  volttron_instance. This script will confirm with the user the volttron_home to
  be configured. volttron instance name will be read from volttron_home/config
  if available, if not user will be prompted for volttron instance name. To
  run the scripts without any prompts, save the volttron instance name in
  volttron_home/config file and pass the volttron home directory as command line
  argument For example: "vcfg --vhome /home/vdev/.new_vhome --rabbitmq single"

  Following is the example inputs for "vcfg --rabbitmq single" command. Since no
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
  - Please set environment variable VOLTTRON_HOME to /home/vdev/new_vhome2 before starting volttron
  - On production environments, restrict write access to
  /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt to only admin user. For example: sudo chown root /home/vdev/new_vhome2/certificates/certs/volttron1-root-ca.crt
  - A new admin user was created with user name: volttron1-admin and password=default_passwd.
  You could change this user's password by logging into https://cs_cbox.pnl.gov:15671/ Please update /home/vdev/new_vhome2/rabbitmq_config.yml if you change password

  #######################

  ```



### 4. Test

We are now ready to start VOLTTRON instance. If configureds with RabbitMQ message bus a config file would have got generated in $VOLTTRON\_HOME/config with the entry message-bus=rmq. If you need to revert back to ZeroMQ based VOLTTRON, you
will have to either remove "message-bus" parameter or set it to default "zmq" in $VOLTTRON\_HOME/config and restart volttron process. The following command starts volttron process in the background

```sh
volttron -vv -l volttron.log&
```

This enters the virtual Python environment and then starts the platform in debug (vv) mode with a log file named volttron.log.

Next, start an example listener to see it publish and subscribe to the message bus:

```sh
scripts/core/upgrade-listener
```

This script handles several different commands for installing and starting an agent after removing an old copy. This simple agent publishes a heartbeat message and listens to everything on the message bus. Look at the VOLTTRON log to see the activity:

```sh
tail volttron.log
```
Results in:

```sh
2016-10-17 18:17:52,245 (listeneragent-3.2 11367) listener.agent INFO: Peer: 'pubsub', Sender: 'listeneragent-3.2_1'
:, Bus: u'', Topic: 'heartbeat/listeneragent-3.2_1', Headers:
{'Date': '2016-10-18T01:17:52.239724+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0'},
Message: {'status': 'GOOD', 'last_updated': '2016-10-18T01:17:47.232972+00:00', 'context': 'hello'}
```

Stop the platform:

```sh
volttron-ctl shutdown --platform
```

## Next Steps

There are several [walkthroughs](https://volttron.readthedocs.io/en/latest/devguides/index.html#devguides-index) to explore additional aspects of the platform:

* [Agent Development Walkthrough](https://volttron.readthedocs.io/en/latest/devguides/agent_development/Agent-Development.html#agent-development)
* Demonstration of the [management UI](https://volttron.readthedocs.io/en/latest/devguides/walkthroughs/VOLTTRON-Central-Demo.html#volttron-central-demo)
* Rabbitmq Setup with Federation and Shovel plugins
* Backward compatibility with RabbitMQ message bus

## Acquiring Third Party Agent Code
Third party agents are available under volttron-applications repository. In
order to use those agents, add volttron-applications repository in the same
as volttron source code clone using following command:

```sh
cd <parent directory of volttron>
git clone https://github.com/VOLTTRON/volttron-applications.git develop
```

## Contribute

How to [contribute](http://volttron.readthedocs.io/en/latest/community_resources/index.html#contributing-back) back:

* Issue Tracker: https://github.com/VOLTTRON/volttron/issues
* Source Code: https://github.com/VOLTTRON/volttron

## Support
There are several options for VOLTTRONTM [support](https://volttron.readthedocs.io/en/latest/community_resources/index.html#volttron-community).

* A VOLTTRONTM office hours telecon takes place every other Friday at 11am Pacific over Skype.
* A mailing list for announcements and reminders
* The VOLTTRONTM contact email for being added to office hours, the mailing list, and for inquiries is: volttron@pnnl.gov
* The preferred method for questions is through stackoverflow since this is easily discoverable by others who may have the same issue. https://stackoverflow.com/questions/tagged/volttron
* GitHub issue tracker for feature requests, bug reports, and following development activities https://github.com/VOLTTRON/volttron/issues

## License
The project is [licensed](LICENSE.md) under Apache 2.
