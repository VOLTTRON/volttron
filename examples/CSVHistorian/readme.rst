.. CSV Example Historian Agent:

===========================
CSV Example Historian Agent
===========================

This example implementation of the base historian stores data into csv files
using the crate table schema.

Setup
-----

**If you haven't already:**

 1. Navigate into your Volttron project directory
 2. Boot strap the platform by typing "python bootstrap.py"
 3. Activate the environment by typing ". env/bin/activate"
 4. Start the platform with "./start-volttron"

**Then:**

 1. Install the agent: "python scripts/install-agent.py -s examples/CSVHistorian -t csvhistorian"
 2. Start the agent: "vctl start --tag csvhistorian"
 3. Check that the agent is running: "vctl status"

::

    AGENT                    IDENTITY                   TAG                STATUS          HEALTH
    685 csv_historianagent-1.0.1 csv_historianagent-1.0.1_2 csvhistorian       running [8565]  GOOD

The begining of the agent's UUID can be found in the leftmost column (685 in the
example above).

**Verify the data:**

The data files can be found at "<volttron home
directory>/agents/<id>/csv_historianagent-1.0.1/csv-historianagent-1.0.1
.agent-data/", where <id> is is the UUID of the agent.
