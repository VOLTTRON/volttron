  

![image](docs/source/images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png)

Distributed Control System Platform.

|Branch|Status|
|:---:|---|
|Master Branch| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=master)|
|Releases 4.1| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=releases/4.1)|
|develop| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=develop)|

VOLTTRONTM is an open source platform for distributed sensing and control. The platform provides services for collecting and storing data from buildings and devices and provides an environment for developing applications which interact with that data.

# NOTE: This is an experiment branch to test and collaborate on Message Bus Refactor effort. VOLTTRON message bus now works with both ZeroMQ and RabbitMQ messaging libraries.
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


 For RabbitMQ based VOLTTRON, some of the RabbitMQ specific software packages have to be installed.

 **a. Install Erlang packages.**

  Please refer to [rabbitmq website](https://www.rabbitmq.com/which-erlang.html) to find the right version of Erlang to be installed for the version of RabbitMQ you intend to install. Also please note, RabbitMQ does not support Erlang versions older than 19.3 and newer than 20.3.x (including 21.0)

  **On Debian based systems:**

  Grab the right package for your OS version from https://packages.erlang-solutions.com/erlang/#tabs-debian.
  Example install commands for Ubuntu artful 64 bit is given below
 
  ```sh
  wget http://packages.erlang-solutions.com/site/esl/esl-erlang/FLAVOUR_1_general/esl-erlang_20.3-1~ubuntu~xenial_amd64.deb
  sudo dpkg -i esl-erlang_20.3-1~ubuntu~artful_amd64.deb
  ```

  **On Redhat based systems:**

  Easiest way to install Erlang for use with Rabbitmq is to use [Zero dependency
  Erlang RPM](https://github.com/rabbitmq/erlang-rpm). This included only the components required for RabbitMQ.
  Copy the contents of the repo file provided into /etc/yum.repos.d/rabbitmq-erlang.repo and then run yum install erlang. You would need to do both these as root user. below is a example rabbitmq-erlang.repo file for centos 7 and erlang 20.7
  
  ```sh
# In /etc/yum.repos.d/rabbitmq-erlang.repo
[rabbitmq-erlang]
name=rabbitmq-erlang
baseurl=https://dl.bintray.com/rabbitmq/rpm/erlang/20/el/7
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
  You can also download and install Erlang from [Erlang Solutions](https://www.erlang-solutions.com/resources/download.html). Please include OTP/components - ssl, public_key, asn1, and crypto. Also lock version of Erlang using the [yum-plugin-versionlock](https://access.redhat.com/solutions/98873)

  **b. Install RabbitMQ server package**

On Debian based systems:

```sh
 sudo apt-get install init-system-helpers socat adduser logrotate
 wget https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.7.6/rabbitmq-server_3.7.6-1_all.deb
 dpkg -i rabbitmq-server_3.7.6-1_all.deb
 ```

On Redhat based systems:

Download the appropriate rpm from [rabbitmq site](https://www.rabbitmq.com/install-rpm.html) and install using  "yum install <name>.rpm" command
```sh
# following commands are for CentOS 7 and rabbitmq-server 3.7.4
wget https://dl.bintray.com/rabbitmq/all/rabbitmq-server/3.7.4/rabbitmq-server-3.7.4-1.el7.noarch.rpm
sudo yum install rabbitmq-server-3.7.4-1.el7.noarch.rpm
```
**b. Start rabbitmq server**
	
Make sure that your hostname is correctly configured in /etc/hosts. See (https://stackoverflow.com/questions/24797947/os-x-and-rabbitmq-error-epmd-error-for-host-xxx-address-cannot-connect-to-ho)

Hostname should be resolvable to a valid ip. Rabbitmq checks for this during inital boot. Without this (for example, when running on a VM in NAT mode) rabbitmq  start would fail with the error "unable to connect to empd (port 4369) on <hostname>. 

Note: rabbitmq startup error would show up in syslog (/var/log/messages) file and not in rabbitmq logs (/var/log/rabbitmq/rabbitmq@hostname.log)
	
Start rabbitmq-server
```sh
sudo service rabbitmq-server start
```


**c. Enable RabbitMQ management, federation, shovel and auth_mechanism_ssl plugins**
```sh
sudo rabbitmq-plugins enable rabbitmq_management
sudo rabbitmq-plugins enable rabbitmq_federation
sudo rabbitmq-plugins enable rabbitmq_federation_management
sudo rabbitmq-plugins enable rabbitmq_shovel
sudo rabbitmq-plugins enable rabbitmq_auth_mechanism_ssl
```

**3. Download VOLTTRON code from experimental branch**
```sh
git clone -b rabbitmq-volttron https://github.com/VOLTTRON/volttron.git
cd volttron
python bootstrap.py
```

This will build the platform and create a virtual Python environment. It will
also install the dependencies for rabbimq.  Activate the environment :

```sh
. env/bin/activate
```

**4. Create RabbitMQ setup for VOLTTRON :**
```sh
python volttron/utils/rmq_setup.py single
```

User can choose to run with or without ssl authentication by choosing Y/N when
prompted. Description below explains the steps when user chooses to run the
platform with SSL based authentication. This creates a new virtual host
“volttron” and creates ssl certificates needed for this VOLTTRON instance.
These certificates get created under the sub directory "certificates" in
your VOLTTRON home (typically in ~/.volttron). It then creates the main VIP
exchange named "volttron" to route message between platform and agents and
alternate exchange to capture unrouteable messages.

This script prompt for multiple information from the user regarding the
VOLTTRON instance for which we are configuring rabbitmq. For each VOLTTRON
instance there a single instance-ca certificate is created. All VOLTTRON
instances that need to work together in a federation/shovel setup needs to
have a instance-ca certificate signed by the same root CA.  A single VOLTTRON
instance can create a self signed root ca. Instance-ca for all VOLTTRON
instances should be generated in this VOLTTRON instance and should be scp-ed
into the other instance.
 
Following is the example inputs for rmq_setup.py single command for VOLTTRON
instance that has root CA.
```sh
python volttron/utils/rmq_setup.py single
Your VOLTTRON_HOME currently set to: /home/velo/new_volttron
Is this the volttron instance you are attempting to configure rabbitmq for? [Y]:

What is the name of the virtual host under which Rabbitmq VOLTTRON will be running? [volttron]:

Do you want SSL Authentication [Y]: 

Use default rabbitmq configuration [Y]:

Creating new VIRTUAL HOST: volttron

Create new exchange: volttron

Create new exchange: undeliverable

Checking for CA certificate

What is the fully qualified domain name of the system? [vbox2.pnl.gov]:

Do you want to create a self-signed root CA certificate that can sign all volttron instance CA in your setup: [N]: y

Please enter the following for certificate creation:

C - Country(US):

ST - State(Washington):

L - Location(Richland):

O - Organization(PNNL):

OU - Organization Unit(Volttron Team):

CN - Common Name(vbox2 volttron-ca):

Created CA cert

Creating new USER: volttron1

Create READ, WRITE and CONFIGURE permissions for the user: volttron1

What is the admin user name: [volttron1]:

Please do the following to complete setup

1. Move the rabbitmq.conf filein VOLTTRON_HOME directory into your rabbitmq
configuration directory (/etc/rabbitmq in RPM/Debian systems)

2.On production setup: Restrict access to private key files in
VOLTTRON_HOME/certificates/ to only rabbitmq user and admin. By default private
key files generated have read access to all.

3. For custom ssl ports: Generated configuration uses default rabbitmq ssl
   ports. Modify both rabbitmq.conf and VOLTTRON_HOME/rabbitmq_config.json if
   using different ports.

4. Restart rabbitmq-server.
	sudo service rabbitmq-server restart
```

Example inputs for 'python rmq_setup.py single' command for a volttron instance
that does not contain the root CA cert

```sh
python volttron/utils/rmq_setup.py single
Your VOLTTRON_HOME currently set to: /home/velo/volttron_test

Is this the volttron instance you are attempting to configure rabbitmq for? [Y]:

Name of this volttron instance: [volttron1]:

What is the name of the virtual host under which Rabbitmq VOLTTRON will be running? [volttron]:

Use default rabbitmq configuration [Y]:

Creating new VIRTUAL HOST: volttron

Create new exchange: volttron

Create new exchange: undeliverable

Checking for CA certificate

What is the fully qualified domain name of the system? [localhost.localdomain]: osboxes.pnl.gov

Do you want to create a self-signed root CA certificate that can sign all volttron instance CA in your setup: [N]: N

Enter path to intermediate CA certificate of this volttron instance: /home/velo/volttron1-ca.crt

Enter path to private key file for this instance CA: /home/velo/volttron1-ca.pem

Creating new USER: volttron1

Create READ, WRITE and CONFIGURE permissions for the user: volttron1

What is the admin user name: [volttron1]:
Please do the following to complete setup

1. Move the rabbitmq.conf filein VOLTTRON_HOME directory into your rabbitmq
configuration directory (/etc/rabbitmq in RPM/Debian systems)

2.On production setup: Restrict access to private key files in
VOLTTRON_HOME/certificates/ to only rabbitmq user and admin. By default private
key files generated have read access to all.

3. For custom ssl ports: Generated configuration uses default rabbitmq ssl
   ports. Modify both rabbitmq.conf and VOLTTRON_HOME/rabbitmq_config.json if
   using different ports.

4. Restart rabbitmq-server.
	sudo service rabbitmq-server restart
```
**5. Update RabbitMQ configuration file and restart RabbitMQ server**
Follow the instructions provided as output of 'python rmq_setup.py single' command to create the rabbitmq.conf, change permissions for ssl private key files and restart rabbitmq-server

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
We can configure multi-platform VOLTTRON setup with RabbitMQ message bus using
built-in "federation" feature provided by RabbitMQ.

1. Generate ssl certificates for the new volttron instance.
   In a multi platform setup that need to communicate with each other with
   rabbitmq over ssl, each volttron instance should have a intermediate CA and
   all intermediate CAs( for each volttron instance) should be signed by the
   same ROOT CA.

   a. To generate intermediate CA for the second volttron instance,
      run the following command in the instance containing the ROOT CA.
      volttron-pkg create_instance_ca <instance_name>

```
(volttron)[velo@osboxes myvolttron]$ volttron-pkg create_instance_ca volttron2

Created files:
/home/velo/.volttron_r2/certificates/certs/volttron2-ca.crt
/home/velo/.volttron_r2/certificates/private/volttron2-ca.pem
```

    b. Transfer (scp/sftp/similar) the generated .crt and .pem files to the
       second volttron instance and make sure that the files have read access to
       rabbitmq user

    c. Do the initial setup of Erlang, Rabbitmq, Rabbitmq plugins, and volttron
       using the steps above

    d. Run "python volttron/utils/rmq_setup.py single" command but when prompted
       for creation of root certificate choose N. The script will now prompt you
       for the location of the instance CA (intermediate CA). Provide the path
       of the files your transferred to this machine.


2. Identify upstream servers (publisher nodes) and downstream servers
(collector nodes). To create a RabbitMQ federation, we have to configure
upstream servers on the downstream server and make the VOLTTRON exchange
"federated".

    a.  On the downstream server (collector node),

        ```
        python volttron/utils/rmq_setup.py federation
        ```

        Please provide the hostname (or IP address) and port of the upstream nodes when
        prompted. The hostname provided should match the hostname in the ssl
        certificate of the upstream server. For bi-directional data flow,
        we will have to run the same script on both the nodes.

    b.  Create a user in the upstream server with username=downstream admin
    user name. (i.e. <instance-name>-admin) and provide it access to the
    virtualhost of the upstream rabbitmq server.

        ```sh
        sudo rabbitmqctl add_user <username> <password>
        sudo rabbitmqctl set_permissions -p volttron <username> ".*" ".*" ".*"
        ```
3. Test the federation setup.
   a. On the downstream server run a listener agent which subscribes to messages
   from all platforms (set @PubSub.subscribe('pubsub', '', all_platforms=True)
   instead of @PubSub.subscribe('pubsub', '') )
   b.Start volttron on upstream volttron
   c. Verify listener agent in downstream volttron instance is able to receive
   the messages.

4. Open ports and https service if needed
   On Redhat based systems ports used by rabbbitmq - 5671, 15671 for ssl, 5672
   and 15672 otherwise - might not be open by default. In that case please
   contact system administrator to get ports opened on the downstream server.
   Following are commands used on centos 7.

   ```
   sudo firewall-cmd --zone=public --add-port=15671/tcp --permanent
   sudo firewall-cmd --zone=public --add-port=5671/tcp --permanent
   sudo firewall-cmd --zone=public --add-port=5671/tcp --permanent
   sudo firewall-cmd --reload
   ```

## Next Steps
We request you to explore and contribute towards development of VOLTTRON message bus refactor task. This is an ongoing task and we are working towards completing the following:
* Integrating Volttron Central, forwarder, data mover and other agents which connect to remote instances to use RabbitMQ message bus with SSL.
* Streamlining the installation steps.
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
