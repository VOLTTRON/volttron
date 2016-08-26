============
Installation
============

VOLTTRON requires the following dependencies in order to bootstrap the
development environment.

* Essential build tools (gcc, make, autodev-tools, etc.)
* Python development files (headers)
* Openssl.
* Git (Optional)

On **Debian-based systems**, these can all be installed with the following
command:

.. code-block:: bash

   sudo apt-get update
   sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git

On **Arch Linux**, the following command will install the dependencies:

.. code-block:: bash

    sudo pacman -S base-devel python2 openssl libssl-dev libsodium

Source Code
-----------

To work with the latest devlopment code clone from the develop branch by using
the following git command.

.. code-block:: bash

    git clone https://github.com/VOLTTRON/volttron/ -b develop

To work with the latest stable code clone the master branch using the following
git command.

.. code-block:: bash

    git clone https://github.com/VOLTTRON/volttron/

Bootstrap
---------

To create a development environment, execute the following in the project root
directory.

.. code-block:: bash

    python2.7 bootstrap.py

Activate
--------

Activating the shell sets the correct environment for executing a volttron
instance.  From the project root directory execute the following.

.. code-block:: bash

    source env/bin/activate

*Note that an 'activated' command prompt is like the following*
.. code-block:: bash

    (volttron)user@machine $

Testing
-------

VOLTTRON uses py.test as a framework for executing tests.  py.test is not installed
with the distribution by default.  To install py.test and it's dependencies
execute the following:

.. code-block:: bash

    python bootstrap.py --testing


To run all of the tests in the volttron repository execute the following in the
root directory using an activated command prompt:

.. code-block:: bash

    py.test


Execution
---------

To start a default instance of volttron from an activated command prompt
execute the following.

.. code-block:: bash

    volttron -vv

Or to start volttron in the background with logging to a file called
volttron.log execute the following.

.. code-block:: bash

    volttron -vv -l volttron.log&

Next Steps
----------

* :doc:`agent-development`  
