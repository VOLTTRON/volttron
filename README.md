


![image](docs/source/images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png)

Distributed Control System Platform.

|Branch|Status|
|:---:|---|
|Master Branch| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=master)|
|Releases 4.1| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=releases/4.1)|
|develop| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=develop)|

VOLTTRONTM is an open source platform for distributed sensing and control. The platform provides services for collecting and storing data from buildings and devices and provides an environment for developing applications which interact with that data.

# NOTE: This is an experiment branch to test and collaborate on Message Bus Refactor effort. Message bus now works with both ZeroMQ and RabbitMQ messaging libraries.
## Features

* [Message Bus](https://volttron.readthedocs.io/en/latest/core_services/messagebus/index.html#messagebus-index) allows agents to subcribe to data sources and publish results and messages

* [Driver framework](https://volttron.readthedocs.io/en/latest/core_services/drivers/index.html#volttron-driver-framework) for collecting data from and sending control actions to buildings and devices
* [Historian framework](https://volttron.readthedocs.io/en/latest/core_services/historians/index.html#historian-index) for storing data
* [Agent lifecycle managment](https://volttron.readthedocs.io/en/latest/core_services/control/AgentManagement.html#agentmanagement) in the platform
* [Web UI](https://volttron.readthedocs.io/en/latest/core_services/service_agents/central_management/VOLTTRON-Central.html#volttron-central) for managing deployed instances from a single central instance.

## Background

VOLTTRONTM is written in Python 2.7 and runs on Linux Operating Systems. For users unfamiliar with those technologies, the following resources are recommended:

https://docs.python.org/2.7/tutorial/
http://ryanstutorials.net/linuxtutorial/

## Installation

 **1. Install needed [prerequisites]**

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


**2. Install RabbitMQ**


 For RabbitMQ based VOLTTRON, some of the RabbitMQ required software packages have to be installed.

 **a. Install Erlang packages.**

  Please refer to [rabbitmq website](https://www.rabbitmq.com/which-erlang.html) to find the right version of Erlang to be installed for the version of RabbitMQ you intend to install

  On Debian based systems:

  ```sh
  wget https://packages.erlang-solutions.com/erlang-solutions_1.0_all.deb
  sudo dpkg -i erlang-solutions_1.0_all.deb
  sudo apt-get install erlang erlang-nox
  ```

  On Redhat based systems:

  Easiest way to install Erlang for use with Rabbitmq is to use [Zero dependency
  Erlang RPM](https://github.com/rabbitmq/erlang-rpm). This included only the components required for RabbitMQ.
  Copy the contents of the repo file provided in
  /etc/yum.repos.d/rabbitmq-erlang.repo and then run yum install erlang. You
  would need to do both these as root user.

  You can also download and install Erlang from [Erlang Solutions](https://www.erlang-solutions.com/resources/download.html). Please include OTP/components - ssl, public_key, asn1, and crypto. Also lock version of Erlang using the [yum-plugin-versionlock](https://access.redhat.com/solutions/98873)

  **b. Install RabbitMQ server package**

On Debian based systems:
```sh
sudo apt-get install rabbitmq-server
```
On Redhat based systems:

Download the appropriate rpm from [rabbitmq site](https://www.rabbitmq.com/install-rpm.html) and install using  "yum install <name>.rpm" command
```sh
# following commands are for CentOS 7
wget https://dl.bintray.com/rabbitmq/all/rabbitmq-server/3.7.4/rabbitmq-server-3.7.4-1.el7.noarch.rpm
sudo yum install rabbitmq-server-3.7.4-1.el7.noarch.rpm
```


Start rabbitmq-server
```sh
sudo rabbitmq-server start &
```
Note: If you are running in a virtual machine, please make sure that your hostname is
correctly configured in /etc/hosts. See (https://stackoverflow.com/questions/24797947/os-x-and-rabbitmq-error-epmd-error-for-host-xxx-address-cannot-connect-to-ho)


**c. Enable RabbitMQ management, federation and shovel plugins**
```sh
sudo rabbitmq-plugins enable rabbitmq_management
sudo rabbitmq-plugins enable rabbitmq_federation
sudo rabbitmq-plugins enable rabbitmq_federation_management
sudo rabbitmq-plugins enable rabbitmq_shovel
```

**d. Download the version of pika library from below specified git repository
into
your home directory.**
```sh
cd ~
git clone -b gevent_connection_adapter https://github.com/shwethanidd/pika.git
```

**3. Download VOLTTRON code from experimental branch**
```sh
git clone -b rabbitmq-volttron https://github.com/VOLTTRON/volttron.git
cd volttron
python bootstrap.py
```

This will build the platform and create a virtual Python environment. Activate the environment :

```sh
. env/bin/activate
```

**4. Install pika library inside VOLTTRON environment:**
```sh
pip install -e ~/pika
```

**5. Create RabbitMQ setup for VOLTTRON :**
```sh
python volttron/utils/rmq_mgmt.py single
```

This creates a new virtual host “volttron” and a new administrative user "volttron". It then creates the main VIP
exchange named "volttron" to route message between platform and agents and alternate exchange to capture unrouteable
messages.

We need to set the VOLTTRON instance name and type of message bus in the configuration file located in $VOLTTRON_HOME/config.
Message bus type has to be either "rmq" or "zmq".

Edit your VOLTTRON config file to match the file below:
```sh
[volttron]
message-bus = rmq
vip-address = tcp://127.0.0.1:22916
instance-name = volttron1
```


**6. Test**


We are now ready to start VOLTTRON with RabbitMQ message bus. If we need to revert back to ZeroMQ based VOLTTRON, we
will have to either remove "message-bus" parameter or set it to default "zmq" in $VOLTTRON\_HOME/config.

```sh
volttron -vv -l volttron.log&
```
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

## VOLTTRON RabbitMQ control and management utility
Some of the important native RabbitMQ control and management commands are now integrated with "volttron-ctl" utility. Using
volttron-ctl rabbitmq management utility, we can control and monitor the status of RabbitMQ message bus.

```sh
volttron-ctl rabbitmq --help
usage: volttron-ctl command [OPTIONS] ... rabbitmq [-h] [-c FILE] [--debug]
                                                   [-t SECS]
                                                   [--msgdebug MSGDEBUG]
                                                   [--vip-address ZMQADDR]
                                                   ...
subcommands:

    add-vhost           add a new virtual host
    add-user            Add a new user. User will have admin privileges
                        i.e,configure, read and write
    add-exchange        add a new exchange
    add-queue           add a new queue
    list-vhosts         List virtual hosts
    list-user-properties
                        List users
    list-exchanges      add a new user
    list-exchange-properties
                        list exchanges with properties
    list-queues         list all queues
    list-queue-properties
                        list queues with properties
    list-bindings       list all bindings with exchange
    list-federation-parameters
                        list all federation parameters
    list-connections    list open connections
    remove-vhosts       Remove virtual host/s
    remove-users        Remove virtual user/s
    remove-exchanges    Remove exchange/s
    remove-queues       Remove queue/s
```

## Multi-Platform Deployment With RabbitMQ Message bus
We can configure multi-platform VOLTTRON setup with RabbitMQ message bus using built-in "federation" feature provided by RabbitMQ. The
first step to do so would be to identify upstream servers (publisher nodes) and downstream servers (collector nodes).
To create a RabbitMQ federation, we have to configure upstream servers and make the VOLTTRON exchange "federated".

On the downstream server (collector node),

```
python volttron/utils/rmq_mgmt.py federation
```

We need to provide the hostname (or IP address) and port of the upstream nodes when prompted. For bi-directional data flow, we will have to run the same script on both the nodes.

## Next Steps
We request you to explore and contribute towards development of VOLTTRON message bus refactor task. This is an ongoing task and we
 are working towards completing the below:
* Adding authentication and authorization feature to RabbitMQ message bus.
* Authenticated connection amongst multiple platform instances.
* Creation of Each agent has to have a unique RabbitMQ user id.
* Testing of RabbitMQ shovel for multi-platform over NAT setup

## Acquiring Third Party Agent Code
Third party agents are available under volttron-applications repository. In order to use those agents, add volttron-applications repository under the volttron/applications directory by using following command:

```sh
git subtree add –prefix applications https://github.com/VOLTTRON/volttron-applications.git develop –squash
```

## Next Steps
We request you to explore and contribute towards development of VOLTTRON message bus refactor task. This is an ongoing task and we
 are working towards completing the below:
* Adding authentication and authorization feature to RabbitMQ message bus.
* Authenticated connection amongst multiple platform instances.
* Creation of Each agent has to have a unique RabbitMQ user id.
* Testing of RabbitMQ shovel for multi-platform over NAT setup

## Acquiring Third Party Agent Code
Third party agents are available under volttron-applications repository. In order to use those agents, add volttron-applications repository under the volttron/applications directory by using following command:

```sh
git subtree add –prefix applications https://github.com/VOLTTRON/volttron-applications.git develop –squash
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
The project is [licensed](TERMS.md) under a modified BSD license.