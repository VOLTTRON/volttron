.. _Bootstrap-Process:

=================
Bootstrap Process
=================

The `bootstrap.py` Python script in the root directory of the VOLTTRON repository may be used to create
VOLTTRON's Python virtual environment and install or update service agent dependencies.

The first running of `bootstrap.py` will be against the systems `python3` executable.  During this initial step a
virtual environment is created using the `venv` module.  Additionally, all requirements for running a base volttron
instance are installed.  Optionally specifying additional arguments to the `bootstrap.py` script allows a way to
quickly install dependencies for service agents (e.g. bootstrap.py --mysql).

.. code-block:: bash

    # boostrap with additional dependency requirements for web enabled agents.
    user@machine$ python3 bootstrap.py --web

After activating an environemnt (source env/bin/activate) one can use the `bootstrap.py` script to install more
service agent dependencies by executing the same boostrap.py command.

.. note::

    In the following example one can tell the environment is activated based upon the (volttron) prefix to the
    command prompt

.. code-block:: bash

    # Adding additional database requirement for crate
    (volttron) user@machine$ python3 bootstrap.py --crate

If a fresh install is necessary one can use the --force argument to rebuild the virtual environment from scratch.

.. code-block:: bash

    # Rebuild the environment from the system's python3
    user@machine$ python3 bootstrap.py --force

.. note::

    Multiple options can be specified on the command line `python3 bootstrap.py --web --crate` installs
    dependencies for web enabled agents as well as the Crate database historian.

Bootstrap Options
=================

The `bootstrap.py` script takes several options that allow customization of the environment, installing and
update packages, and setting the package locations.  The following sections can be reproduced by executing:

.. code-block:: bash

    # Show the help output from bootstrap.py
    user@machine$ python3 bootstrap --help

Options for customizing the location of the virtual environment.

.. code-block:: bash

    --envdir VIRTUAL_ENV  alternate location for virtual environment
    --force               force installing in non-empty directory
    -o, --only-virtenv    create virtual environment and exit (skip install)
    --prompt PROMPT       provide alternate prompt in activated environment
                        (default: volttron)

Additional options are available for customizing where an environment will retrieve packages and/or upgrade
existing packages installed.

.. code-block:: bash

    update options:
      --offline             install from cache without downloading
      -u, --upgrade         upgrade installed packages
      -w, --wheel           build wheels in the pip wheelhouse

To help boostrap an environment in the shortest number of steps we have grouped dependency packages under named
collections.  For example the --web argument will install six different packages from a single call to
boostrap.py --web.  The following collections are available to use.

.. code-block:: bash

    ...

    Extra packaging options:
      --all             All dependency groups.
      --crate           Crate database adapter
      --databases       All of the databases (crate, mysql, postgres, etc).
      --dnp3            Dependencies for the dnp3 agent.
      --documentation   All dependency groups to allow generation of documentation without error.
      --drivers         All drivers known to the platform driver.
      --influxdb        Influx database adapter
      --market          Base market agent dependencies
      --mongo           Mongo database adapter
      --mysql           Mysql database adapter
      --pandas          Pandas numerical analysis tool
      --postgres        Postgres database adapter
      --testing         A variety of testing tools for running unit/integration tests.
      --web             Packages facilitating the building of web enabled agents.
      --weather         Packages for the base weather agent

    rabbitmq options:
      --rabbitmq [RABBITMQ]
                            install rabbitmq server and its dependencies. optional
                            argument: Install directory that exists and is
                            writeable. RabbitMQ server will be installed in a
                            subdirectory.Defaults to /home/osboxes/rabbitmq_server

    ...
