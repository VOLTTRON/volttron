==================
Deployment Options
==================

There are several ways to deploy the VOLTTRON platform in a Linux environment. It is up to the user to determine which
is right for them. The following assumes that the platform has already been bootstrapped and is ready to run.

Simple Command Line
*******************

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
****************************************

A simple, more long term solution, is to run volttron in the background and disown it from the current terminal.

.. warning::
    If you plan on running VOLTTRON in the background and detaching it from the
    terminal with the ``disown`` command be sure to redirect stderr and stdout to ``/dev/null``.
    Even if logging to a file is used some libraries which VOLTTRON relies on output
    directly to stdout and stderr. This will cause problems if those file descriptors
    are not redirected to ``/dev/null``.

::

    $volttron -vv -l volttron.log > /dev/null 2>&1&

Alternatively:

::

    ``./start-volttron``

.. note:: If you are not in an activated environment, this script will start
    the platform running in the background in the correct environment, however
    the environment will not be activated for you, you must activate it yourself.

**If there are other jobs running in your terminal be sure to disown the correct one.**

::

    $jobs
    [1]+  Running                 something else
    [2]+  Running                 ./start-volttron

    #Disown VOLTTRON
    $disown %2

This will run the VOLTTRON platform in the background and turn it into a daemon. The log output will be directed
to a file called ``volttron.log`` in the current directory.

To keep the size of the log under control for more longer term deployments us the rotating log configuration file
``examples/rotatinglog.py``.

::

    $volttron -vv --log-config examples/rotatinglog.py > /dev/null 2>&1&

This will start a rotate the log file at midnight and limit the total log data to seven days worth.

The main downside to this approach is that the VOLTTRON platform will not automatically
resume if the system is restarted. It will need to be restarted manually after reboot.

Setting up VOLTTRON as a System Service
***************************************

Systemd
-------

An example service file ``scripts/admin/volttron.service`` for systemd cas be used as a starting point
for setting up VOLTTRON as a service. Note that as this will redirect all the output that would 
be going to stdout - to the syslog.  This can be accessed using journalctl. For systems that run 
all the time or have a high level of debugging turned on, we recommend checking the system's 
logrotate settings.

::

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

::

    #Copy the service file into place
    cp scripts/admin/volttron.service /etc/systemd/system/

    #Set the correct permissions if needed
    chmod 644 /etc/systemd/system/volttron.service

    #Notify systemd that a new service file exists (this is crucial!)
    systemctl daemon-reload

    #Start the service
    systemctl start volttron.service

Init.d
------

An example init script ``scripts/admin/volttron`` can be used as a starting point for
setting up VOLTTRON as a service on init.d based systems.

Minor changes may be needed for the file to work on the target system. Specifically
the ``USER``, ``VLHOME``, and ``VOLTTRON_HOME`` variables may need to be changed.

::

    ...
    #Change this to the user VOLTTRON will run as.
    USER=volttron
    #Change this to the install location of VOLTTRON
    VLHOME=/var/lib/volttron

    ...

    #Uncomment and change this to specify a different VOLTTRON_HOME
    #export VOLTTRON_HOME=/home/volttron/.volttron


The script can be installed with the following commands. These need to be run as root or
with sudo as appropriate.

::

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
