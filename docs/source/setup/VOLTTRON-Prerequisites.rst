.. _VOLTTRON-Prerequisites:

Required Software: Linux
========================

The following packages will need to be installed on the system:

-  git
-  build-essential
-  python3.6-dev
-  python3.6-venv
-  openssl
-  libssl-dev
-  libevent-dev

On **Debian-based systems**, these can all be installed with the following
command:

.. code-block:: bash

       sudo apt-get update
       sudo apt-get install build-essential python3.6-dev python3.6-venv openssl libssl-dev libevent-dev git

On **Redhat or CENTOS systems**, these can all be installed with the following
command:

.. code-block:: bash

   sudo yum update
   sudo yum install make automake gcc gcc-c++ kernel-devel python3.6-devel pythone3.6-venv openssl openssl-devel libevent-devel git

.. note::
   The above commands are specific to 3.6, however you could use 3.6 or greater in them.

If you have an agent which requires the pyodbc package, install the
following:

-  freetds-bin
-  unixodbc-dev

::

    sudo apt-get install freetds-bin  unixodbc-dev

Possible issues
~~~~~~~~~~~~~~~

The /tmp directory must allow exec. This error could manifest itself
during the building of gevent.

::

    # Executing mount should have an entry like the following
    mount

    tmpfs on /tmp type tmpfs (rw,nosuid,nodev)

To change the mount you can use the following code

::

    # remount /tmp to allow exec
    sudo mount -o remount,exec /tmp

::

    # remount /tmp to disallow exec
    sudo mount -o remount,noexec /tmp

