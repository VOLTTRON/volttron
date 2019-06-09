The tests/ subdirectory of DNP3Agent contains several types of tests:

# MesaAgent Regression Tests

**test_mesa_agent.py** contains MesaAgent pytest regression tests as follows:

1. Load point and function definitions.
2. Start a MesaAgent process.
3. Test routing of DNP3 output:
    - Send point values from a simulated Master.
    - Verify that MesaAgent has published them correctly on the VOLTTRON message bus.
4. Test routing of DNP3 input:
    - Use RPC calls to set point values.
    - Verify that the simulated Master has received them correctly.

# DNP3Agent Regression Tests

**test_dnp3_agent.py** contains DNP3Agent pytest regression tests as follows:

1. Load point definitions.
2. Start a DNP3Agent process.
3. Test routing of DNP3 output, similar to the MesaAgent tests above.
4. Test routing of DNP3 input, similar to the MesaAgent tests above.

# Data Regression Tests

**test_mesa_data.py** contains pytest regression tests of MesaAgent data.

The test strategy in test_mesa_data.py is similar to the other pytest strategies,
but rather than working with a small, controlled set of data, this module's tests
use "production" point and function definitions.

# Ad-Hoc Unit Test Support

**unit_test_point_definitions.py** contains a mix of standalone non-pytest
methods that test and validate various types of data and behavior.

**MesaTestAgent** is a VOLTTRON agent that interacts with MesaAgent, sending
RPC calls and subscribing to MesaAgent publication of data.

**mesa_master_cmd.py** is a standalone command-line utility (built on the Python
Cmd library) that sends point and function values from the master to 
the (MesaAgent) DNP3 outstation.
