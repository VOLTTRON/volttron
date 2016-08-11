.. _VOLTTRON-Prerequisites:

Required Sofware: Linux
-------------------------

The following packages will need to be installed if they are not
already:

-  git
-  build-essential
-  python-dev
-  openssl
-  libssl-dev
-  libevent-dev

   ::

       sudo apt-get update
       sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git

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

