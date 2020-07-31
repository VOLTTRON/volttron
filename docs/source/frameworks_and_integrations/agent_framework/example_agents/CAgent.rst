.. _CAgent:

CAgent
======

The C Agent uses the ctypes module to load a shared object into memory
so its functions can be called from python.

There are two versions of the C Agent. The first is a standard agent that can
be installed with the make agent script. The other is a driver interface for
the master driver.

Building the Shared Object
--------------------------

The shared object library must be built before installing C Agent examples.
Running *make* in the C Agent source directory will compile the provided C code
using the position independent flag; a requirement for creating shared objects.

Files created by make can be removed by running *make clean*.

Agent Installation
------------------

After building the shared object library the standard agent can be installed
with the scripts/install-agent.py script.

The driver interface example must be copied or moved to the master driver's
interface directory. The C Driver configuration tells the interface where to
find the shared object. An example is available in the C Agent's *driver*
directory.
