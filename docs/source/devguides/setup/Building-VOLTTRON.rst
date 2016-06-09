.. _Building-VOLTTRON:

Building VOLTTRON
==================

The VOLTTRON project includes a bootstrap script which automatically
downloads dependencies and builds VOLTTRON. The script also creates a
Python virtual environment for use by the project which can be activated
after bootstrapping with ". env/bin/activate". This activated Python
virtual environment should be used for subsequent bootstraps whenever
there are significant changes. The system's Python need only be used on
the initial bootstrap.

Before bootstrapping, ensure the `required
packages :ref:<VOLTTRON-Prerequisites>` are installed. If you intend to
develop in Eclipse, we recommend creating the work directory: ~/git or
~/workspace. Then run the following commands in the work directory to
work with the master branch of the repository:

::

    git clone <https://github.com/VOLTTRON/volttron>
    cd volttron

    # bootstrap.py --help will show you all of the "package options" such as 
    #installing required packages for volttron central or the platform agent.
    python2.7 bootstrap.py

For other options see: :ref:`Getting VOLTTRON <VOLTTRON-Source-Options>`

Note: Some packages (especially numpy) can be very verbose when they
install. Please wait for the wall of text to finish.

To test that installation worked, start up the platform in verbose mode
and set a log file:

::

    # Activate the terminal
    source env/bin/activate

    # Start the platform in the background
    volttron -vv -l volttron.log&

    # If no errors are present then your setup is correct.  You can
    # also tail the log file to see if the platform started correctly
    tail -f volttron.log

If you are developing in Eclipse, you should update the Python path at
this point. See: :ref:`Eclipse-Dev-Environment <Eclipse-Dev-Environment>`

Note: The default working directory is ~/.volttron. The default
directory for creation of agent packages is ~/.volttron/packaged

To test agent deployment and messaging, build and deploy ListenerAgent.
From the volttron directory:

::

    # Activate the terminal
    source env/bin/activate

    # Package the agent
    volttron-pkg package examples/ListenerAgent

    # Set the agent's configuration file
    volttron-pkg configure ~/.volttron/packaged/listeneragent-3.0-py2-none-any.whl examples/ListenerAgent/config

    # Install the agent (volttron must be running):
    volttron-ctl install ~/.volttron/packaged/listeneragent-3.0-py2-none-any.whl

    # Start the agent:
    volttron-ctl start --name listeneragent-3.0

    # Verify the agent has started
    volttron-ctl status

    # Note the uuid
    # Check that Listener is publishing heartbeat message: 
    cat volttron.log

    # Stop the agent
    volttron-ctl stop --name listeneragent-3.0


    # -- or --
    volttron-ctl stop <uuid>

See :ref:`Speeding Up VOLTTRON Builds <Speeding-Builds>` for information on
improving VOLTTRON build times.
