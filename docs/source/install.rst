.. _install:

===================
Installing Volttron
===================

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


On **Redhat or CENTOS systems**, these can all be installed with the following
command:

.. code-block:: bash

   sudo yum update
   sudo yum install make automake gcc gcc-c++ kernel-devel python-devel openssl openssl-devel libevent-devel git

On **Arch Linux**, the following command will install the dependencies:

.. code-block:: bash

    sudo pacman -S base-devel python2 openssl libssl-dev libsodium

Source Code
-----------


To work with the latest stable code clone the master branch using the following
git command.

.. code-block:: bash

    git clone https://github.com/VOLTTRON/volttron/


You may use the following command to work with the latest code from the develop
branch. It must be run within the VOLLTRON source directory. More discussion on the 
repository structure can be found at :ref:`Repository Structure <Repository-Structure>`.


.. code-block:: bash

    git checkout develop



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

.. note::

  An 'activated' command prompt is like the following

  .. code-block:: bash

    (volttron)user@machine $

Testing
-------

VOLTTRON uses py.test as a framework for executing tests.  py.test is not installed
with the distribution by default.  To install py.test and it's dependencies
execute the following:

.. code-block:: bash

    python bootstrap.py --testing

.. note::

  There are other options for different agent requirements.  To see all of the options use:

  .. code-block:: bash

    python bootstrap.py --help

  in the Extra Package Options section.


To run all of the tests in the volttron repository execute the following in the
root directory using an activated command prompt:

.. code-block:: bash

    ./ci-integration/run-tests.sh


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


Acquiring Third Party Agent Code
--------------------------------

Third party agents developed from a variety of sources are available from the volttron-applications repository (https://github.com/VOLTTRON/volttron-applications.git).  The current best practice is to have the main volttron and the volttron-applications repository within the same common ansestry folder.

.. code-block:: bash

  volttron-repositories/
  |
  |--- volttron/
  |
  |--- volttron-applications/

One can clone the latest applications from the repository via the following command:

.. code-block:: bash

  git clone https://github.com/VOLTTRON/volttron-applications.git

Additional Considerations
-------------------------

If you are planning to install VOLTTRON at scale or to collect data you want to keep, please see the
:ref:`Installation Planning <planning-install>` page.
