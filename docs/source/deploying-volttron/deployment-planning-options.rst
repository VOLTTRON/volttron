.. _Planning-Deployments:

=====================
Planning a Deployment
=====================

The 3 major installation types for VOLTTRON are doing development, doing research using VOLTTRON, and
collecting and managing physical devices.

Development and Research installation tend to be smaller footprint installations. For development, the
data is usually synthetic or copied from another source. The existing documentation covers development
installs in significant detail.

Other deployments will have a better installation experience if they consider certain kinds of questions
while they plan their installation.


Questions
=========

  * Do you want to send commands to the machines ?
  * Do you want to store the data centrally ?
  * How many machines do you expect to collect data from on each "collector" ?
  * How often will the machines collect data ?
  * Are all the devices visible to the same network ?
  * What types of VOLTTRON applications do you want to run ?


Commands
--------

If you wish to send commands to the devices, you will want to install and configure the Volttron Central
agent. If you are only using VOLTTRON to securely collect the data, you can turn off the extra agents
to reduce the footprint.


Storing Data
------------

VOLTTRON supports multiple historians. MySQL and MongoDB are the most commonly used. As you plan your
installation, you should consider how quickly you need access to the data and where.  If you are looking
at the health and well-being of an entire suite of devices, its likely that you want to do that from a
central location.  Analytics can be performed at the edge by VOLTTRON applications or can be performed
across the data usually from a central data repository.  The latency that you can tolerate in your data
being available will also determine choices in different agents (ForwardHistorian versus Data Mover)


How Many
--------

The ratio of how many devices-to-collector machine is based on several factors. These include:

      * how much memory and network bandwidth the collection machine has.  More = More devices
      * how fast the local storage is can affect how fast the data cache can be written.  Very slow
        storage devices can fall behind

The second half of the "how many" question is how many collector platforms are writing to a single
VOLTTRON platform to store data - and whether that storage is local, remote, big enough, etc.

If you are storing more than moderate amount of data, you will probably benefit from installing
your database on a different machine than your concrete historian machine.

.. note::

    This is contra-indicated if you have a slow network connection between you concrete historian and your database
    machine.

In synthetic testing up to 6 virtual machines hosting 500 devices each (18 points) were easily
supported by a single centralized platform writing to a Mongo database - using a high speed network.
That central platform experienced very little CPU or memory load when the VOLTTRON Central agent was disabled.


How Often
---------

This question is closely related to the last. A higher sampling frequency will create more data.  This
will place more work in the storage phase.


Networks
--------

In many cases, there are constraints on how networks can interact with each other. In many cases,
these include security considerations.  On some sites, the primary network will be protected from less
secure networks and may require different installation considerations.  For example, if a data collector
machine and the database machine are on the same network with sufficient security, you may choose
to have the data collector write directly to the database.  If the collector is on an isolated building
network then you will likely need to use the ForwardHistorian to bridge the two networks.


Other Considerations
--------------------

Physical location and maintenance of collector machines must be considered in all live deployments.
Although the number of data points may imply a heavy load on a data collection box, the physical constraints
may limit the practicality of having more than a single box.  The other side of that discussion is deploying
many collector boxes may be simpler initially, but may create a maintenance challenge if you don't
plan ahead on how you apply patches, etc.

Naming conventions should also be considered.  The ability to trace data through the system and identify
the collector machine and device can be invaluable in debugging and analysis.


.. _Deployment-Options:

Deployment Options
==================

There are several ways to deploy the VOLTTRON platform in a Linux environment. It is up to the user to determine which
is right for them. The following assumes that the platform has already been bootstrapped and is ready to run.


Simple Command Line
-------------------

With the VOLTTRON environment activated the platform can be started simply by running VOLTTRON on the command
line.

::

    $volttron -vv

This will start the platform in the current terminal with very verbose logging turned on. This
is most appropriate for testing Agents or testing a deployment for problems before switching to a
more long term solution. This will print all log messages to the console in real time.

This should not be used for long term deployment. As soon as an SSH session is terminated for whatever reason
the processes attached to that session will be killed. This also will not capture log message to a file.


Running VOLTTRON as a Background Process
----------------------------------------

A simple, more long term solution, is to run volttron in the background and disown it from the current terminal.

.. warning::
    If you plan on running VOLTTRON in the background and detaching it from the
    terminal with the ``disown`` command be sure to redirect stderr and stdout to ``/dev/null``.
    Even if logging to a file is used some libraries which VOLTTRON relies on output
    directly to stdout and stderr. This will cause problems if those file descriptors
    are not redirected to ``/dev/null``.

.. code-block:: bash

    $volttron -vv -l volttron.log > /dev/null 2>&1&

Alternatively:

.. code-block:: bash

    ``./start-volttron``

.. note::

    If you are not in an activated environment, this script will start the platform running in the background in the
    correct environment, however the environment will not be activated for you, you must activate it yourself.

**If there are other jobs running in your terminal be sure to disown the correct one.**

.. code-block:: console

    $jobs
    [1]+  Running                 something else
    [2]+  Running                 ./start-volttron

    #Disown VOLTTRON
    $disown %2

This will run the VOLTTRON platform in the background and turn it into a daemon. The log output will be directed
to a file called ``volttron.log`` in the current directory.

To keep the size of the log under control for more longer term deployments us the rotating log configuration file
``examples/rotatinglog.py``.

.. code-block:: bash

    $volttron -vv --log-config examples/rotatinglog.py > /dev/null 2>&1&

This will start a rotate the log file at midnight and limit the total log data to seven days worth.

The main downside to this approach is that the VOLTTRON platform will not automatically
resume if the system is restarted. It will need to be restarted manually after reboot.


Setting up VOLTTRON as a System Service
---------------------------------------


Systemd
^^^^^^^

An example service file ``scripts/admin/volttron.service`` for systemd cas be used as a starting point
for setting up VOLTTRON as a service. Note that as this will redirect all the output that would
be going to stdout - to the syslog.  This can be accessed using `journalctl`.  For systems that run
all the time or have a high level of debugging turned on, we recommend checking the system's
logrotate settings.

.. code-block:: console

    [Unit]
    Description=VOLTTRON Platform Service
    After=network.target

    [Service]
    Type=simple

    #Change this to the user that VOLTTRON will run as.
    User=volttron
    Group=volttron

    #Uncomment and change this to specify a different VOLTTRON_HOME
    #Environment="VOLTTRON_HOME=/home/volttron/.volttron"

    #Change these to settings to reflect the install location of VOLTTRON
    WorkingDirectory=/var/lib/volttron
    ExecStart=/var/lib/volttron/env/bin/volttron -vv
    ExecStop=/var/lib/volttron/env/bin/volttron-ctl shutdown --platform


    [Install]
    WantedBy=multi-user.target

After the file has been modified to reflect the setup of the platform you can install it with the
following commands. These need to be run as root or with sudo as appropriate.

.. code-block:: console

    #Copy the service file into place
    cp scripts/admin/volttron.service /etc/systemd/system/

    #Set the correct permissions if needed
    chmod 644 /etc/systemd/system/volttron.service

    #Notify systemd that a new service file exists (this is crucial!)
    systemctl daemon-reload

    #Start the service
    systemctl start volttron.service


Init.d
^^^^^^

An example init script ``scripts/admin/volttron`` can be used as a starting point for
setting up VOLTTRON as a service on init.d based systems.

Minor changes may be needed for the file to work on the target system. Specifically
the ``USER``, ``VLHOME``, and ``VOLTTRON_HOME`` variables may need to be changed.

.. code-block:: console

    ...
    #Change this to the user VOLTTRON will run as.
    USER=volttron
    #Change this to the install location of VOLTTRON
    VLHOME=/var/lib/volttron

    ...

    #Uncomment and change this to specify a different VOLTTRON_HOME
    #export VOLTTRON_HOME=/home/volttron/.volttron


The script can be installed with the following commands.  These need to be run as root or with `sudo` as appropriate.

.. code-block:: console

    #Copy the script into place
    cp scripts/admin/volttron /etc/init.d/

    #Make the file executable
    chmod 755 /etc/init.d/volttron

    #Change the owner to root
    chown root:root /etc/init.d/volttron

    #These will set it to startup automatically at boot
    update-rc.d volttron defaults

    #Start the service
    /etc/init.d/volttron start
