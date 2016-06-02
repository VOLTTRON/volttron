.. _Resource-Monitor:

Reource Monitor
=================

The :ref:`VOLTTRON™ Restricted <Volttron-Restricted>` additions provide
additional protection against an agent consuming too many resources to
the point of the host system becoming unresponsive or unstable. The
resource monitor uses Linux control groups (or cgroups) to limit the CPU
cycles and memory an individual agent may consume, preventing its
possible overconsumption from adversely affecting other agents and
services on the system. The execution requirements of an agent are set
when :ref:`provisioning an agent <Agent-Signing>` for service.

When a request is made to move an agent to a new platform, part of the
validation of the agent includes checking its execution requirements
against resources currently available on the system. If the resources
are available and the agent has passed all other validation, the agent
will be executed and retain those resource guarantees throughout its
lifetime on that platform. If the agent, however, requests memory or CPU
cycles that are not available, its move request is denied and it will
not execute on the requested platform.

Once an agent has been assigned resources, it is the responsibility of
that agent to manage use of its resources. While an agent may exceed its
resource guarantees when system utilization is low, when resources given
to other agents are required, an agent exceeding the use in its contract
may be terminated.

Execution Requirements
----------------------

The execution requirements are specified as a JSON formatted document
embedded in the agent during initial provisioning and takes the
following form:

.. code:: JSON

    {
      "requirements": {
        "cpu.bogomips": 100,
        "memory.soft_limit_in_bytes": 2000000
      }
    }

The contract *must* contain the ``requirements`` object, specifying the
soft requirements, and might optionally specify a ``hard_requirements``
object.

Each agent, including newly developed agents, must maintain their own
requirements. The execution requirements for an agent are located in a
file in the individual agent directory, called *exereqs.json*.

For example, the execution requirements for the Listener Agent are
located at *volttron/examples/ListenerAgent/exereqs.json*

Soft requirements
~~~~~~~~~~~~~~~~~

Soft requirements are considered *soft* on the platform because they
change depending on the number of agents and other services are running
on the system. They may also be negotiated on the fly in a future
release. A list of the current resources which may be reserved follows:

-  **cpu.bogomips** - The CPU requirements of an agent indicated as
   either an exact integer (N >= 1) in MIPS (millions of instructions
   per second) or a floating-point percentage (0.0 < N < 1.0) of the
   total available bogo-MIPS on a system. Bogomips is a rough
   calculation performed at system boot indicating the likely number of
   calculations a system may perform each second.
-  **memory.soft\_limit\_in\_bytes** - The maximum amount of random
   access memory (RAM) an agent requires to perform its tasks measured
   in bytes and given as an integer.
   Additional resources may be added in a future release.

Hard requirements
~~~~~~~~~~~~~~~~~

Hard requirements are based on system attributes that are very unlikely
to change except after a system reboot. It is rare that an agent would
need to set hard requirements and is usually only necessary for
architecture-specific code. Each hard requirement is tested for a match.

-  **kernel.name** - Kernel name as given by ``uname``.
-  **kernel.release** - Kernel release as given by ``uname``.
-  **kernel.version** - Kernel version as given by ``uname``.
-  **architecture** - Kernel architecture as given by ``uname``.
-  **os** - Always 'GNU/Linux'
-  **platform.version** - Version of VOLTTRON in use.
-  **memory.total** - Total amount of memory on the system in bytes.
-  **bogomips.total** - Total of all bogomips reported for all
   processors on the system.

Example using requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~

In this example we modify the execution requirements for the Listener
Agent.

#. | Open a terminal and type the following command:
   |  ``cat /proc/meminfo | grep MemTotal``
   | The output will be the total memory available on the system. Save
   this number.

#. In a text editor, open *volttron/examples/ListenerAgent/exereqs.json*
#. Replace the requirements with the following text:

   .. code:: JSON

       {
           "requirements": {
               "cpu.bogomips": 100,
               "memory.soft_limit_in_bytes": 2000000
           },
           "hard_requirements": {
               "os": "GNU/Linux",
               "memory.total": 2064328
           }
       }

#. Replace the number for "memory.total" with the number from step 1, so
   that the requirement matches the memory for your system.
#. Save and close the file. Now, if the total memory on the system is
   changed, such as with a hardware update, the requirement will fail.
   Note that the hard requirements are separate, and follow the same
   format as the soft requirements.


