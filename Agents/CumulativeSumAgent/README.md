## Installation

Start by getting the Volttron platform platform up and running: [RTUNetwork build 
instructions](https://svn.pnl.gov/RTUNetwork/wiki/BuildingTheProject).

You can find the [Volttron platform source here](https://bitbucket.org/berkeleylab/rtunetwork/overview).

The Agents contained in this repo can be built just like normal Volttron agents. Aside from Volttron, the only dependency required by these agents is the loadshape module. Within each Agent, this dependency is declared both in setup.py as well as requirements.txt.

For installation instructions related to the loadshape module, please see the loadshape module documentation:

[Loadshape module documentation](https://bitbucket.org/berkeleylab/eetd-loadshape)

## Cumulative Sum Agent Usage
To request a cumulative sum calculation from the Cumulative Sum Agent, a requesting agent should publish a message to the **cumulativesum/request** topic using the publish_json method.

An example message is shown below:
```python
example_message = {
    "load_data": [(1379487600, 5), (1379488500, 5), ... (1379491200, 5)],
    "temp_data": [(1379487600, 72), (1379488500, 72), ... (1379491200, 72)],
    "timezone": 'America/Los_Angeles',
    "temp_units": "F",
    "sq_ft": 5600,
    "step_size": 900
    }
```

Except for "load_data" all keys are optional.

The contents of this message will be passed directly to the loadshape module and a cumulative sum will be calculated using the arguments provided. Once the cumulative sum calculation has completed, the Cumulative Sum Agent will publish a message to the **cumulativesum/responses/[requesting-AgentID]** topic. The message published to this topic will contain a time series of kWh difference between the provided load data and the calculated baseline.
