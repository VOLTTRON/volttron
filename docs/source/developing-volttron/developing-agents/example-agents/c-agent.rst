.. _C-Agent:

=======
C Agent
=======

The C Agent uses the `ctypes` module to load a shared object into memory so its functions can be called from Python.

There are two versions of the C Agent:

* A standard agent that can be installed with the agent installation process
* A driver which can can be controlled using the Platform Driver Agent


Building the Shared Object
--------------------------

The shared object library must be built before installing C Agent examples.  Running ``make`` in the C Agent source
directory will compile the provided C code using the position independent flag, a requirement for creating shared
objects.

Files created by make can be removed by running

.. code-block:: bash

    make clean


Agent Installation
------------------

After building the shared object library the standard agent can be installed with the ``scripts/install-agent.py``
script:

.. code-block:: bash

    python scripts/install-agent.py -s examples/CAgent

The other is a driver interface for the Platform Driver.  To use the C driver, the driver code file must be moved into
the Platform Driver's `interfaces` directory:

    ::

        examples/CAgent/c_agent/driver/cdriver -> services/core/PlatformDriverAgent/platform_driver/interfaces


The C Driver configuration tells the interface where to find the shared object.  An example is available in the C
Agent's `driver` directory.
