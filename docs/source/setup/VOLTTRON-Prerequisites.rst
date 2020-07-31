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
       sudo apt-get install build-essential python3-dev python3-venv openssl libssl-dev libevent-dev git

On Ubuntu-based systems, available packages allow you to specify the python3 version, 3.6 or greater is required (Debian itself does not provide those packages).

On arm-based systems (including, but not limited to, Raspbian), you must also install libffi-dev, you can do this with:

.. code-block:: bash

       sudo apt-get install libffi-dev

On **Redhat or CENTOS systems**, these can all be installed with the following
command:

.. code-block:: bash

   sudo yum update
   sudo yum install make automake gcc gcc-c++ kernel-devel python3-devel openssl openssl-devel libevent-devel git

.. note::
   Python 3.6 or greater is required.

If you have an agent which requires the pyodbc package, install the
following:

-  freetds-bin
-  unixodbc-dev

On **Debian-based systems** these can be installed with the following command:

.. code-block:: bash

    sudo apt-get install freetds-bin  unixodbc-dev

On **Redhat or CentOS systems**, these can be installed from the Extra Packages for Enterprise Linux (EPEL) repository:

.. code-block:: bash

    sudo yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
    sudo yum install freetds unixODBC-devel

.. note::
    The above command to install the EPEL repository is for Centos/Redhat 8. Change the number to match your OS version.

    EPEL packages are included in Fedora repositories, so installing EPEL is not required on Fedora.


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

