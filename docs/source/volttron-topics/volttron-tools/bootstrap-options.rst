.. _Bootstrap-Options:

VOLTTRON Bootstrap Script
=========================

The bootstrap.py Python script in the root directory of the VOLTTRON repository may be used to create
VOLTTRON's Python virtual environment and install or update VOLTTRON dependencies into the virtual
environment.

Bootstrapping is broken into two stages. The first stage should only be invoked once per virtual
environment. It downloads Virtualenv and creates a virtual Python environment in the virtual
environment directory (defaults to a subdirectory named env in the same directory as this script).
It then executes stage two using the newly installed virtual environment. Stage two uses the
new virtual Python environment to install VOLTTRON and its dependencies.

If a new dependency is added, this script may be run again using the Python executable in the
virtual environment to re-run stage two:

  env/bin/python bootstrap.py

To speed up bootstrapping in a test environment, use the --wheel feature, which might look something
like this:

  $ export PIP_WHEEL_DIR=/path/to/cache/wheelhouse
  $ export PIP_FIND_LINKS=file://$PIP_WHEEL_DIR
  $ mkdir -p $PIP_WHEEL_DIR
  $ python2.7 bootstrap.py -o
  $ env/bin/python bootstrap.py --wheel
  $ env/bin/python bootstrap.py

Instead of setting the environment variables, a pip configuration file may be used. Look here for more
information on configuring pip:

  https://pip.pypa.io/en/latest/user_guide.html#configuration

Bootstrap Options
-----------------

To facilitate bootstrapping the various configurations of the VOLTTRON platform, the bootstrap script
provides several options. Options exist for each message bus, specifying a new environment, updating
an existing environment, and installing some optional dependencies for features like historians.

These options may be invoked to alter the operation of the bootstrap script.

.. code-block::

    --envdir VIRTUAL_ENV: This option allows the user to specify the directory for the creation of a
    new environment. If an environment exists, this can be used to create a second environment with an
    alternative set of dependencies.

    --force: This option will force bootstrapping in a non-empty directory. This may be used to reset
    an environment or if a previous bootstrapping attempt has failed.

    -o, --only-virtenv: This option will cause bootstrap to create a new Python virtual environment
    without installing any VOLTTRON dependencies.

    --prompt PROMPT: Specify prompt to use in an activated environment, defaults to (volttron)
    (Prompt specifies the string proceeding <user>@<host> in an activated environment, e.i. Running
    bootstrap with --prompt test would result in "(test) <user>@<host>:~/volttron$ " in bash)

    --offline: Install from Pip cache, prevents downloading dependencies

    -u, --upgrade: Upgrade installed packages to newest version

    -w, --wheel: Build wheels in the Pip wheelhouse (Pip package cache)


Optional Arguments
~~~~~~~~~~~~~~~~~~

These options can be added to the command to run the bootstrap script to cause the process to produce
varying levels of output during operation.

.. code-block::

    -help, --help: This option will display a message describing the options described below, and then
    exist the bootstrap script.

    -q, --quiet: This option will limit the output of the bootstrap script.

    -v, --verbose: This option will cause the bootstrap script to produce additional output.

Packaging Arguments
~~~~~~~~~~~~~~~~~~~

Packaging arguments can be added to the bootstrap argument list to specify an additional set of packages
to install beyond those required for "vanilla" VOLTTRON. Multiple packaging arguments can be specified
(e.i. python3 bootstrap.py --testing --databases ...)

.. code-block::

    --crate: Install crate.io Python database driver (crate) for use with Crate historian

    --databases: Install Python database drivers for historians - Crate (crate), InfluxDB (influxdb),
        MongoDB (pymongo), MySQL (mysql-connector-python-rf)

    --dnp3: Install Python Distributed Network Protocol 3 wrapper (pydnp3)

    --documentation: Install requirements for building VOLTTRON documentation - Mock (mock), MySQL
        (mysql-connector-python-rf), PSUtil (psutil), MongoDB (pymongo), Sphinx (sphinx),
        Recommonmark (recommonmark), Read the Docs Sphinx theme (sphinx-rtd-theme)

    --drivers: Install device communication wrappers for VOLTTRON driver framework - Modbus (pymodbus),
        Modbus Test Kit (modbus-tk), BACnet (bacpypes), Serial (pyserial)

    --influxdb: Install InfluxDB Python database driver (influxdb) for use with influxdb historian

    --market: Install requirements for VOLTTRON Market Service - NumPy (numpy), Transitions (transitions)

    --mongo: Install MongoDB Python database driver (pymongo) for use with MongoDB historian

    --mysql: Install MySQL database connector for Python (mysql-connector-python-rf)

    --pandas: Install Pandas (pandas) and NumPy (numpy)

    --postgres: Install Psycopg (postgres)

    --testing: Install testing infrastructure dependencies - Mock (mock), PyTest (pytest), PyTest-timeout
        (pytest-timeout), Websocket-Client (websocket-client)

    --rabbitmq <optional installation directory>: Install Python Pika client library for use with RabbitMQ VOLTTRON deployments
        (gevent-pika) If RabbitMQ is not installed at <user_home>/rabbitmq_server, the user should specify the optional
        argument. RabbitMQ deployments require additional setup, for more information please read the RabbitMQ portion
        of section 3 in the README in the root VOLTTRON directory.

    --weather: Install Python unit conversion library Pint (point)
