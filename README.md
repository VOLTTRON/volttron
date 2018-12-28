  

![image](docs/source/images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png)

Distributed Control System Platform.

|Branch|Status|
|:---:|---|
|Master Branch| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=master)|
|develop| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=develop)|

VOLTTRONTM is an open source platform for distributed sensing and control. The
platform provides services for collecting and storing data from buildings and
devices and provides an environment for developing applications which interact
with that data.

# NOTE: This is an experiment branch to test and collaborate on Message Bus Refactor effort. VOLTTRON message bus now works with both ZeroMQ and RabbitMQ messaging libraries.
## Features

* [Message Bus](https://volttron.readthedocs.io/en/latest/core_services/messagebus/index.html#messagebus-index) allows agents to subcribe to data sources and publish results and messages

* [Driver framework](https://volttron.readthedocs.io/en/latest/core_services/drivers/index.html#volttron-driver-framework) for collecting data from and sending control actions to buildings and devices
* [Historian framework](https://volttron.readthedocs.io/en/latest/core_services/historians/index.html#historian-index) for storing data
* [Agent lifecycle managment](https://volttron.readthedocs.io/en/latest/core_services/control/AgentManagement.html#agentmanagement) in the platform
* [Web UI](https://volttron.readthedocs.io/en/latest/core_services/service_agents/central_management/VOLTTRON-Central.html#volttron-central) for managing deployed instances from a single central instance.

## Background

VOLTTRONTM is written in Python 2.7 and runs on Linux Operating Systems. For
users unfamiliar with those technologies, the following resources are recommended:

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


**2. Install Erlang version 21 packages.**


 For RabbitMQ based VOLTTRON, some of the RabbitMQ specific software packages have to be installed.

  **On Debian based systems:**

  If you are running an Ubuntu system, you can install the RabbitMQ dependencies by running the rabbit dependencies
  script, passing in the approriate distribution as a parameter. Please note,
  distribution parameter will vary according to the distribution used in your system. For example,

    bionic for Ubuntu 18.04
    xenial for Ubuntu 16.04
    xenial for Linux Mint 18.04
    stretch for Debian Stretch
    jessie for Debian Jessie
  
  ``` 
  ~/volttron/scripts/rabbit_dependencies.sh xenial
  ```

  **On Redhat based systems:**

  Easiest way to install Erlang for use with RabbitMQ is to use [Zero dependency
  Erlang RPM](https://github.com/rabbitmq/erlang-rpm). This included only the components required for RabbitMQ.
  Copy the contents of the repo file provided into /etc/yum.repos.d/rabbitmq-erlang.repo and then run yum install erlang. 
  You would need to do both these as root user. Below is a example
  rabbitmq-erlang.repo file for centos 7 and erlang 21.

  
  ```sh
# In /etc/yum.repos.d/rabbitmq-erlang.repo
[rabbitmq-erlang]
name=rabbitmq-erlang
baseurl=https://dl.bintray.com/rabbitmq/rpm/erlang/21/el/7
gpgcheck=1
gpgkey=https://dl.bintray.com/rabbitmq/Keys/rabbitmq-release-signing-key.asc
repo_gpgcheck=0
enabled=1
  ```
 Once you save the repo file, run the following commands
 ```sh
 sudo yum install erlang
 ```
  
  
 Alternatively,
  You can also download and install Erlang from [Erlang Solutions](https://www.erlang-solutions.com/resources/download.html).
  Please include OTP/components - ssl, public_key, asn1, and crypto.
  Also lock version of Erlang using the [yum-plugin-versionlock](https://access.redhat.com/solutions/98873)

**3. Configure hostname**

Make sure that your hostname is correctly configured in /etc/hosts.
See (https://stackoverflow.com/questions/24797947/os-x-and-rabbitmq-error-epmd-error-for-host-xxx-address-cannot-connect-to-ho). If you are testing with VMs make please make sure to provide unique host names for each of the VM you are using. 

Hostname should be resolvable to a valid ip when running on bridged mode. RabbitMQ checks for this during
initial boot. Without this (for example, when running on a VM in NAT mode)
RabbitMQ  start would fail with the error "unable to connect to empd (
port 4369) on <hostname>." Note: RabbitMQ startup error would show up in syslog (/var/log/messages) file
and not in RabbitMQ logs (/var/log/rabbitmq/rabbitmq@hostname.log)


**4. Download VOLTTRON code from experimental branch**

```sh
git clone -b rabbitmq-volttron https://github.com/VOLTTRON/volttron.git
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

Activate the environment :

```sh
. env/bin/activate
```

**4. Create RabbitMQ setup for VOLTTRON :**
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



**5. Test**

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
Some of the important native RabbitMQ control and management commands are now
integrated with "volttron-ctl" utility. Using volttron-ctl rabbitmq management
utility, we can control and monitor the status of RabbitMQ message bus.

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
    list-users          List users
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
    list-shovel-parameters
                        list all shovel parameters
    list-policies       list all policies
    remove-vhosts       Remove virtual host/s
    remove-users        Remove virtual user/s
    remove-exchanges    Remove exchange/s
    remove-queues       Remove queue/s
    remove-federation-parameters
                        Remove federation parameter
    remove-shovel-parameters
                        Remove shovel parameter
    remove-policies     Remove policy

```

## Multi-Platform Deployment With RabbitMQ Message bus

In ZeroMQ based VOLTTRON, if multiple instances needed to be connected together
and be able to send or receive messages to/from remote instances we would do it
in few different ways.

1. Write an agent that would connect to remote instance directly and publish/subscribe
to messages or perform RPC communication directly.

2. Use special agents such as forwarder/data puller agents to forward/receive
messages to/from remote instances.
messages to/from remote instances.

3. Configure vip address of all remote instances that an instance has to connect to
in it's $VOLTTRON_HOME/external_discovery.json and let the router module in each instance
manage the connection and take care of the message routing for us.
This is the most seamless way to do multi-platform communication.

RabbitMQ's shovel pluggin can be used to replace connection type 2 described above.
Similarly, RabbitMQ's federation pluggin can be used to replace connection type 3.


**Using Federation Pluggin**

Federation pluggin allows us to send and receive messages to/from remote instances with
few simple connection settings. Once a federation link is established to remote instance,
the messages published on the remote instance become available to local instance as if it
were published on the local instance. Before, we illustrate the steps to setup a federation
link, let us start by defining the concept of upstream and downstream server.

Upstream Server - The node that is publishing some message of interest

DownStream Server - The node that wants to receive messages from the upstream server

A federation link needs to be established from downstream server to the upstream server. The
data flows in single direction from upstream server to downstream server. For bi-directional
data flow we would need to create federation links on both the nodes.


1. Setup two VOLTTRON instances using the above steps.
__***Please note that each instance should have a unique instance name
and should be running on machine/VM that has a unique host name.***__


2. In a multi platform setup that need to communicate with each other with
   RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of
   the other instance(RabbitMQ root ca)

   a.  Transfer (scp/sftp/similar)
       voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
       location on the other volttron instance machine. For example, if you have two
       instance v1 and v2, scp v1's v1-root-ca.crt to v2 and
       v2-root-ca.crt to v1.
   
       Note: If using VMs, in order to scp files between VM openssh should be installed and running.

   b. Append the contents of the transferred root ca to the instance's trusted-cas.crt file. Do this on both the instances. Now both     
      the instances <instance_name>-trusted-cas.crt will have two certificates.
   
      For example:
      
      On v1:
      cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/certs/v1-trusted-cas.crt
      
      On v2:
      cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/certs/v2-trusted-cas.crt

3. Stop volttron, stop rabbitmq server and start volttron on both the
instances. This is required only when you update the root certificate and not
required when you add a new shovel/federation between the same hosts

   ```sh
   ./stop-volttron
   ./stop-rabbitmq
   ./start-volttron
   ```

4. Identify upstream servers (publisher nodes) and downstream servers
(collector nodes). To create a RabbitMQ federation, we have to configure
upstream servers on the downstream server and make the VOLTTRON exchange
"federated".

    a.  On the downstream server (collector node),

        ```
        vcfg --rabbitmq federation [optional path to rabbitmq_federation_config.yml
        containing the details of the upstream hostname, port and vhost.
        Example configuration for federation is available
        in examples/configurations/rabbitmq/rabbitmq_federation_config.yml]
        ```

        If no config file is provided, the script will prompt for
        hostname (or IP address), port, and vhost of each upstream node you
        would like to add. Hostname provided should match the hostname in the
        SSL certificate of the upstream server. For bi-directional data flow,
        we will have to run the same script on both the nodes.

    b.  Create a user in the upstream server(publisher) with
    username=<downstream admin user name> (i.e. (instance-name)-admin) and
    provide it access to the  virtual host of the upstream RabbitMQ server. Run
    the below command in the upstream server

        ```sh
         volttron-ctl rabbitmq add-user <username> <password>
         Do you want to set READ permission  [Y/n]
         Do you want to set WRITE permission  [Y/n]
         Do you want to set CONFIGURE permission  [Y/n]

        ```
5. Test the federation setup.

   a. On the downstream server run a listener agent which subscribes to messages from all platforms
   
     - Open the file examples/ListenerAgent/listener/agent.py. Search for @PubSub.subscribe('pubsub', '') and replace that         line with @PubSub.subscribe('pubsub', 'devices', all_platforms=True)
     - updgrade the listener
     ```sh
        scripts/core/upgrade-listener
     ```   

   b. Install master driver, configure fake device on upstream server and start volttron and master driver. vcfg --agent master_driver command can install master driver and setup a fake device.

   ```sh
   ./stop-volttron
   vcfg --agent master_driver
   ./start-volttron
   vctl start --tag master_driver
   ```

   c. Verify listener agent in downstream VOLTTRON instance is able to receive the messages. downstream volttron instance's volttron.log should display device data scrapped by master driver agent in upstream volttron instance 

6. Open ports and https service if needed
   On Redhat based systems ports used by RabbitMQ (defaults to 5671, 15671 for
   SSL, 5672 and 15672 otherwise) might not be open by default. Please
   contact system administrator to get ports opened on the downstream server.
   Following are commands used on centos 7.

   ```
   sudo firewall-cmd --zone=public --add-port=15671/tcp --permanent
   sudo firewall-cmd --zone=public --add-port=5671/tcp --permanent
   sudo firewall-cmd --reload
   ```

7. How to remove federation link

   a. Using the management web interface

   Log into management web interface using downstream server's admin username.
   Navigate to admin tab and then to federation management page. The status of the
   upstream link will be displayed on the page. Click on the upstream link name and
   delete it.

   b. Using "volttron-ctl" command on the upstream server.
   ```
   vctl rabbitmq list-federation-parameters
   NAME                         URI
   upstream-volttron2-rabbit-2  amqps://rabbit-2:5671/volttron2?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-2
   ```

   Grab the upstream link name and run the below command to remove it.

   ```
   vctl rabbitmq remove-federation-parameters upstream-volttron2-rabbit-2
   ```

**Using Shovel Plugin**

In RabbitMQ based VOLTTRON, forwarder and data mover agents will be replaced by shovels
to send or receive remote pubsub messages.
Shovel behaves like a well written client application that connects to its source
( can be local or remote ) and destination ( can be local or remote instance ),
reads and writes messages, and copes with connection failures. In case of shovel, apart
from configuring the hostname, port and virtual host of the remote instance, we will
also have to provide list of topics that we want to forward to remote instance. Shovels
can also be used for remote RPC communication in which case we would have to create shovel
in both the instances, one to send the RPC request and other to send the response back.

*Pubsub Communication*

Following are the steps to create Shovel for multi-platform pubsub communication.

1. Setup two VOLTTRON instances using the steps described in installation section.
Please note that each instance should have a unique instance name.

2. In a multi platform setup that need to communicate with each other with
   RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of
   the other instance(RabbitMQ root ca)

   a.  Transfer (scp/sftp/similar)
   voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
   location on the other volttron instance machine. For example, if you have two
   instance v1 and v2, scp v1's v1-root-ca.crt to v2 and
   v2-root-ca.crt to v1.

   b. Append the contents of the transferred root ca to the instance's root ca.
   For example:
   On v1:
   cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/v1-root-ca.crt
   On v2:
   cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/v2-root-ca.crt

3. Identify the instance that is going to act as the "publisher" instance. Suppose
"v1" instance is the "publisher" instance and "v2" instance is the "subscriber"
instance. Then we need to create a shovel on "v1" to forward messages matching
certain topics to remote instance "v2".

    a.  On the publisher node,

        ```
        vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml
        containing the details of the remote hostname, port, vhost
        and list of topics to forward. Example configuration for shovel is available
        in examples/configurations/rabbitmq/rabbitmq_shovel_config.yml]
        ```

        For this example, let's set the topic to "devices"

        If no config file is provided, the script will prompt for
        hostname (or IP address), port, vhost and list of topics for each
        remote instance you would like to add. For
        bi-directional data flow, we will have to run the same script on both the nodes.

    b.  Create a user in the subscriber node with username set to publisher instance's
        agent name ( (instance-name)-PublisherAgent ) and allow the shovel access to
        the virtual host of the subscriber node.

        ```sh
        cd $RABBITMQ_HOME
        vctl add-user <username> <password>
        ```

4. Test the shovel setup.

   a. Start VOLTTRON on publisher and subscriber nodes.

   b. On the publisher node, start a master driver agent that publishes messages related to
   a fake device. ( Easiest way is to run volttron-cfg command and follow the steps )

   c. On the subscriber node, run a listener agent which subscribes to messages
   from all platforms (set @PubSub.subscribe('pubsub', 'devices', all_platforms=True)
   instead of @PubSub.subscribe('pubsub', '') )

   d. Verify listener agent in subscriber node is able to receive the messages
   matching "devices" topic.

5. How to remove the shovel setup.

   a. Using the management web interface

   Log into management web interface using publisher instance's admin username.
   Navigate to admin tab and then to shovel management page. The status of the
   shovel will be displayed on the page. Click on the shovel name and delete
   the shovel.

   b. Using "volttron-ctl" command on the publisher node.
   ```
   vctl rabbitmq list-shovel-parameters
   NAME                     SOURCE ADDRESS                                                 DESTINATION ADDRESS                                            BINDING KEY
   shovel-rabbit-3-devices  amqps://rabbit-1:5671/volttron1?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-1  amqps://rabbit-3:5671/volttron3?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-3  __pubsub__.volttron1.devices.#
   ```

   Grab the shovel name and run the below command to remove it.

   ```
   vctl rabbitmq remove-shovel-parameters shovel-rabbit-3-devices
   ```

*RPC Communication*

Following are the steps to create Shovel for multi-platform RPC communication.

1. Setup two VOLTTRON instances using the steps described in installation section.
Please note that each instance should have a unique instance name.

2. In a multi platform setup that need to communicate with each other with
RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of
the other instance(RabbitMQ root ca)

    a.  Transfer (scp/sftp/similar)
   voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
   location on the other volttron instance machine. For example, if you have two
   instance v1 and v2, scp v1's v1-root-ca.crt to v2 and
   v2-root-ca.crt to v1.

    b. Append the contents of the transferred root ca to the instance's root ca.
   For example:

   On v1:
   cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/v1-root-ca.crt
   On v2:
   cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/v2-root-ca.crt


3. Typically RPC communication is 2 way communication so we will to setup shovel in both the VOLTTRON instances. In RPC calls there are two instances of shovel. One serving as the caller (makes RPC request) and the other acting as a callee (replies to RPC request). Identify the instance is the "caller" and which is the "callee." Suppose "v1" instance is the "caller" instance and "v2" instance is the "callee" instance.

   a. On both the client and server nodes, shovel instances need to be created. In this example, v1’s shovel would forward the RPC call    request from an agent on v1 to v2 and similarly v2’s shovel will forward the RPC reply from agent on v2 back to v1.


     ```
     vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml containing the details of the
     **remote** hostname, port, vhost, volttron instance name (so in v1's yml file parameters would point to v2
     and vice versa), and list of agent pair identities (local caller, remote callee). Example configuration for shovel
     is available in examples/configurations/rabbitmq/rabbitmq_shovel_config.yml.]
     
     For this example, let's say that we are using the schedule-example and acutator agents.

     For v1, the agent pair identities would be:
     - [Scheduler, platform.actuator]

     For v2, they would be:
     - [platform.actuator, Scheduler]

     Indicating the flow from local agent to remote agent.
     ```

     If no config file is provided, the script will prompt for hostname (or IP address), port, vhost and
     list of agent pairs for each remote instance you would like to add.


   b. On the client node create a user with username set to server instance's agent name ( (instance-name)-RPCCallee ) and allow the      shovel access to the virtual host of the server node. Similarly, on the server node, create a user with username set to client       instance's agent name ( (instance-name)-RPCCaller ) and allow the shovel access to the virtual host of the client node.

        ```sh
        cd $RABBITMQ_HOME
        vctl add-user <username> <password>
        ```

4. Test the shovel setup 

   a. On client node:


	   Make necessary changes to RPC methods of  client agent.

	    For this example, in volttron/examples/SchedulerExample/schedule_example/agent.py:
	    * Search for 'campus/building/unit' in publish_schedule method. Replace with
	    'devices/fake-campus/fake-building/fake-device'
	    * Search for ['campus/building/unit3',start,end] in the use_rpc method, replace with:                 msg = [
			   ['fake-campus/fake-building/fake-device',start,end].
	    * Add: kwargs = {"external_platform": 'v2'} on the line below
	    * On the result = self.vip.rpc.call method below, replace "msg).get(timeout=10)" with:
		  msg, **kwargs).get(timeout=10),
	    * In the second try clause of the use_rpc method:
		* Replace result['result'] with result[0]['result']
		* Add kwargs = {"external_platform": 'v2'} as the first line of the if statement
		* Replace 'campus/building/unit3/some_point' with 'fake-campus/fake-building/fake-device/PowerState'
		* Below 'fake-campus/fake-building/fake-device/PowerState' add: 0,
		* Replace '0.0').get(timeout=10) with **kwargs).get(timeout=10)


   Next, install an example scheduler agent:
   
   ```sh
   #!/bin/bash
   python /home/username/volttron/scripts/install-agent.py -c /home/username/volttron/examples/SchedulerExample/schedule-example.agent -s examples/SchedulerExample --start --force -i Scheduler
   ```

   and start it.


   b. On the server node:

   Run upgrade script to install actuator agent.

   ```sh
     #!/bin/bash
     python /home/username/volttron/scripts/install-agent.py -s services/core/ActuatorAgent --start --force -i platform.actuator
   ```
    
   Run the upgrade script to install the listener agent.
   
   ```sh
   scripts/core/upgrade-listener
   ```   


   Install master driver, configure fake device on upstream server and start volttron and master driver.
   vcfg --agent master_driver command can install master driver and setup a fake device.
   
    ```sh
    
    ./stop-volttron
    vcfg --agent master_driver
    ./start-volttron
    vctl start --tag master_driver
    ```

   Start actuator agent and listener agents.

   The output for the server node with a successful shovel run should look similar to:
   ```sh
   2018-12-19 15:38:00,009 (listeneragent-3.2 13039) listener.agent INFO: Peer: pubsub, Sender: platform.driver:, Bus: , Topic: devices/fake-campus/fake-building/fake-device/all, Headers: {'Date': '2018-12-19T20:38:00.001684+00:00', 'TimeStamp': '2018-12-19T20:38:00.001684+00:00', 'min_compatible_version': '5.0', 'max_compatible_version': u'', 'SynchronizedTimeStamp': '2018-12-19T20:38:00.000000+00:00'}, Message:
    [{'Heartbeat': True, 'PowerState': 0, 'ValveState': 0, 'temperature': 50.0},
     {'Heartbeat': {'type': 'integer', 'tz': 'US/Pacific', 'units': 'On/Off'},
      'PowerState': {'type': 'integer', 'tz': 'US/Pacific', 'units': '1/0'},
      'ValveState': {'type': 'integer', 'tz': 'US/Pacific', 'units': '1/0'},
      'temperature': {'type': 'integer',
                      'tz': 'US/Pacific',
                      'units': 'Fahrenheit'}}]

   ```



5. How to remove the shovel setup.

   a. Using the management web interface

   Log into management web interface using publisher instance's admin username.
   Navigate to admin tab and then to shovel management page. The status of the
   shovel will be displayed on the page. Click on the shovel name and delete
   the shovel.

   b. Using "volttron-ctl" command on the publisher node.
   ```sh
   vctl rabbitmq list-shovel-parameters
   NAME                     SOURCE ADDRESS                                                 DESTINATION ADDRESS                                            BINDING KEY
   shovel-rabbit-3-devices  amqps://rabbit-1:5671/volttron1?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-1  amqps://rabbit-3:5671/volttron3?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-3  __pubsub__.volttron1.devices.#
   ```

   Grab the shovel name and run the below command to remove it.

   ```
   vctl rabbitmq remove-shovel-parameters shovel-rabbit-3-devices
   ```

*DataMover Communication*

The DataMover Historian is used to send data from one instance of VOLTTRON to another, using RPC shovel. Messages are inserted into the backup queue of the remote historian to help ensure that the messages are recorded.

Following are the steps to create Shovel for multi-platform DataMover communication.

1. Setup two VOLTTRON instances using the steps described in installation section.
Please note that each instance should have a unique instance name.

2. In a multi platform setup that need to communicate with each other with
RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of
the other instance (RabbitMQ root ca)

    a.  Transfer (scp/sftp/similar)
   voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
   location on the other volttron instance machine. For example, if you have two
   instance v1 and v2, scp v1's v1-root-ca.crt to v2 and
   v2-root-ca.crt to v1.

    b. Append the contents of the transferred root ca to the instance's root ca.
   For example:

   On v1:
   cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/v1-root-ca.crt
   On v2:
   cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/v2-root-ca.crt


3. Typically RPC communication is 2 way communication so we will to setup shovel in both the VOLTTRON instances. In RPC calls there are two instances of shovel. One serving as the caller (makes RPC request) and the other acting as a callee (replies to RPC request). Identify the instance is the "caller" and which is the "callee." Suppose "v1" instance is the "caller" instance and "v2" instance is the "callee" instance.

   a. On both the client and server nodes, shovel instances need to be created. In this example, v1’s shovel would forward the RPC call    request from an agent on v1 to v2 and similarly v2’s shovel will forward the RPC reply from agent on v2 back to v1.


     ```
     vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml containing the details of the
     **remote** hostname, port, vhost, volttron instance name (so in v1's yml file parameters would point to v2
     and vice versa), and list of agent pair identities (local caller, remote callee). Example configuration for shovel
     is available in examples/configurations/rabbitmq/rabbitmq_shovel_config.yml.]
     
     For this example, let's say that we are using the schedule-example and acutator agents.

     For v1, the agent pair identities would be:
     - [platform.historian, data.mover]

     For v2, they would be:
     - [data.mover, platform.historian]

     Indicating the flow from local agent to remote agent.
     ```

     If no config file is provided, the script will prompt for hostname (or IP address), port, vhost and
     list of agent pairs for each remote instance you would like to add.


   b. On the client node create a user with username set to server instance's agent name ( (instance-name)-RPCCallee ) and allow the      shovel access to the virtual host of the server node. Similarly, on the server node, create a user with username set to client       instance's agent name ( (instance-name)-RPCCaller ) and allow the shovel access to the virtual host of the client node.

        ```sh
        cd $RABBITMQ_HOME
        vctl add-user <username> <password>
        ```

4. Test the shovel / DataMover setup 

   a. On client node:
   Start SQLHistorian (identiy is platform.historian). Easiest way to accomplish this is to stop VOLTTRON, reconfigure to have RabbitMQ message bus and install platform.historian already installed, and start VOLTTRON again. 
   
   ```sh
   
   vcfg

   Your VOLTTRON_HOME currently set to: /home/vdev/new_vhome2

   Is this the volttron you are attempting to setup?  [Y]: 
   What is the external instance ipv4 address? [tcp://127.0.0.1]: 
   What is the instance port for the vip address? [22916]: 
   What is type of message bus? [zmq]: rmq
   Is this instance a volttron central? [N]: N
   Will this instance be controlled by volttron central? [Y]: N
   Would you like to install a platform historian? [N]: Y
   Configuring /home/kirsten/volttron/services/core/SQLHistorian
   Should agent autostart? [N]: N
   Would you like to install a master driver? [N]: N
   Would you like to install a listener agent? [N]: N
   Finished configuration

   You can now start the volttron instance.

   If you need to change the instance configuration you can edit
   the config file at /home/kirsten/.volttron1/config

   ./start-volttron
   ```
   
   
   Start platform.historian
   
   b. On server node:
   
      Install master driver, configure fake device on upstream server and start volttron and master driver. vcfg --agent master_driver command can install master driver and setup a fake device.

   ```sh
   
   ./stop-volttron
   vcfg --agent master_driver
   ./start-volttron
   vctl start --tag master_driver
   ```
   
   Install DataMover agent
   
   ```sh
   
   #!/bin/bash
   export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)
   cat > $CONFIG <<EOL
   {
       "destination-vip": "amqp://test2:test2@localhost:5672/test2",
       "destination-serverkey": "1yEUcpIcQTJzpvEwl-7KNCxe_f5rhhoShv9f3A8wdUg",
       "destination-instance-name": "RPCCaller",
       "destination-message-bus": "rmq"
   }
   EOL
   python /home/vdev/volttron/scripts/install-agent.py -c $CONFIG -s services/core/DataMover --start --force -i data.mover
   # Finally remove the temporary config file
   rm $CONFIG
   ```
   
   
   and start it. 
   
   
   To confirm that the DataMover agent is working, run the ``tail -f volttron.log`` from the volttron directory to look for output similar to the following.
   
   On the client:
   
   ```sh
   
   DEBUG: insert called by data.mover with 1 records
   2018-12-28 14:39:45,148 (sqlhistorianagent-3.6.1 13416) volttron.platform.agent.base_historian DEBUG: Beginning publish loop.
   2018-12-28 14:39:45,159 (sqlhistorianagent-3.6.1 13416) volttron.platform.dbutils.sqlitefuncts DEBUG: Managing store - timestamp limit: None  GB size limit: None
   2018-12-28 14:39:45,169 (sqlhistorianagent-3.6.1 13416) volttron.platform.agent.base_historian INFO: Historian processed 13156 total records.
   2018-12-28 14:39:45,169 (sqlhistorianagent-3.6.1 13416) volttron.platform.agent.base_historian DEBUG: Exiting publish loop.

   ```
   On the server:
   
   ```sh
   
   2018-12-28 17:57:35,001 (master_driveragent-3.2 11848) master_driver.driver DEBUG: fake-campus/fake-building/fake-device next scrape scheduled: 2018-12-28 22:57:40+00:00
   2018-12-28 17:57:35,002 (master_driveragent-3.2 11848) master_driver.driver DEBUG: scraping device: fake-campus/fake-building/fake-device
   2018-12-28 17:57:35,002 (master_driveragent-3.2 11848) master_driver.driver DEBUG: publishing: devices/fake-campus/fake-building/fake-device/all
   2018-12-28 17:57:35,007 (datamoveragent-0.1 17502) datamover.agent DEBUG: In capture data
   2018-12-28 17:57:35,007 (datamoveragent-0.1 17502) datamover.agent DEBUG: message in capture_data [{'Heartbeat': False, 'PowerState': 0, 'temperature': 50.0, 'ValveState': 0}, {'Heartbeat': {'units': 'On/Off', 'type': 'integer', 'tz': 'US/Pacific'}, 'PowerState': {'units': '1/0', 'type': 'integer', 'tz': 'US/Pacific'}, 'temperature': {'units': 'Fahrenheit', 'type': 'integer', 'tz': 'US/Pacific'}, 'ValveState': {'units': '1/0', 'type': 'integer', 'tz': 'US/Pacific'}}]
   2018-12-28 17:57:35,017 (datamoveragent-0.1 17502) volttron.platform.agent.base_historian DEBUG: Beginning publish loop.
   2018-12-28 17:57:35,017 (datamoveragent-0.1 17502) datamover.agent DEBUG: publish_to_historian number of items: 1
   2018-12-28 17:57:35,017 (datamoveragent-0.1 17502) datamover.agent DEBUG: Last timeout: 1546037766.0 current time: 1546037855.0
   2018-12-28 17:57:35,017 (datamoveragent-0.1 17502) datamover.agent DEBUG: Sending to destination historian.
   2018-12-28 17:57:35,037 (datamoveragent-0.1 17502) volttron.platform.agent.base_historian INFO: Historian processed 1905 total records.
   2018-12-28 17:57:35,037 (datamoveragent-0.1 17502) volttron.platform.agent.base_historian DEBUG: Exiting publish loop.
   2018-12-28 17:57:35,013 (master_driveragent-3.2 11848) master_driver.driver DEBUG: finish publishing: devices/fake-campus/fake-building/fake-device/all
   ```
   

5. How to remove the shovel setup.

   a. Using the management web interface

   Log into management web interface using publisher instance's admin username.
   Navigate to admin tab and then to shovel management page. The status of the
   shovel will be displayed on the page. Click on the shovel name and delete
   the shovel.

   b. Using "volttron-ctl" command on the publisher node.
   ```sh
   vctl rabbitmq list-shovel-parameters
   NAME                     SOURCE ADDRESS                                                 DESTINATION ADDRESS                                            BINDING KEY
   shovel-rabbit-3-devices  amqps://rabbit-1:5671/volttron1?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-1  amqps://rabbit-3:5671/volttron3?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-3  __pubsub__.volttron1.devices.#
   ```

   Grab the shovel name and run the below command to remove it.

   ```
   vctl rabbitmq remove-shovel-parameters shovel-rabbit-3-devices
   ```

** RabbitMQ Trouble Shooting **

   1. Check the status of the federation connection.

      ```
      $RABBITMQ_HOME/sbin/rabbitmqctl eval 'rabbit_federation_status:status().'
      ```

      If everything is properly configured, then the status is set to "running".
      If not look for the error status. Some of the typical errors are,

      a. "failed_to_connect_using_provided_uris" - Check if RabbitMQ user is
         created in downstream server node. Refer to step 3 b of federation
         setup

      b. "unknown ca" - Check if the root CAs are copied to all the nodes
         correctly. Refer to step 2 of federation setup

      c. "no_suitable_auth_mechanism" - Check if the AMPQ/S ports are correctly
         configured.

   2. Check the status of the shovel connection.

      ```
      $RABBITMQ_HOME/sbin/rabbitmqctl eval 'rabbit_shovel_status:status().'
      ```

      If everything is properly configured, then the status is set to "running".
      If not look for the error status. Some of the typical errors are,

      i. "failed_to_connect_using_provided_uris" - Check if RabbitMQ user is created
         in subscriber node. Refer to step 3 b of shovel setup

      ii. "unknown ca" - Check if the root CAs are copied to remote servers
           correctly. Refer to step 2 of shovel setup

      iii. "no_suitable_auth_mechanism" - Check if the AMPQ/S ports are correctly
           configured.

   2. Check the RabbitMQ logs for any errors.

       ```
       tail -f <volttron source dir>/rabbitmq.log
       ```


   3. If rabbitmq startup hangs
      a. Check for errors in rabbitmq log. There is a rabbitmq.log file in your
      volttron source directory that is a symbolic link to the rabbitmq server
      logs.

      b. Check for errors in syslog (/var/log/syslog or /var/log/messages)
      c. If there are no errors in either of the logs, stop rabbitmq and
         starting rabbitmq server in foreground and see if there are any errors
         written on the console. Once you find the error you can kill the
         process by entering Ctl+C, fix the error and start rabbitmq again using
         ./start-rabbitmq from volttron source directory.

         ```
         ./stop-volttron
         ./stop-rabbitmq
         @RABBITMQ_HOME/sbin/rabbitmq-server
         ```

   4. ssl trouble shooting.
      There are few things that are essential for SSL certificates to work
      right.
      a. Please use a unique common-name for CA certificate for each volttron
         instance. This is configured under certificate-data in the
         rabbitmq_config.yml or if no yml file is used while configuring a
         volttron single instance (using vcfg --rabbitmq single). Certificate
         generated for agent will automatically get agent's vip identity as the
         certificate's common-name
      b. host name in ssl certificate should match hostname used to access the
      server. For example, if the fully qualified domain name was configured in
      the certificate-data, you should use the fully qualified domain name to
      access rabbitmq's management url.

      c. Check if your system time is correct especially if you are running
      virtual machines. If the system clock is not right, it could lead to
      ssl certificate errors
   
   5. DataMover troubleshooting. 
      a. If output from volttron.log is not as expected check for  ``{'alert_key': 'historian_not_publishing'}`` in the server node's volttron.log. Most likely cause is the historian is not running properly or credentials between client and server nodes was not set properly.  
      
      

## Next Steps
We request you to explore and contribute towards development of VOLTTRON message
bus refactor task. This is an ongoing task and we are working towards completing
the following:
* Integrating Volttron Central to use RabbitMQ message bus with SSL.
* Test scripts for RabbitMQ message bus.
* Scalability tests for large scale VOLTTRON deployment.

## Acquiring Third Party Agent Code
Third party agents are available under volttron-applications repository. In
order to use those agents, add volttron-applications repository in the same
directory that contains volttron source code clone using following command:

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
