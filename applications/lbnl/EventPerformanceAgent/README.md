## Installation

Start by getting the Volttron platform platform up and running: [RTUNetwork build 
instructions](https://svn.pnl.gov/RTUNetwork/wiki/BuildingTheProject).

You can find the [Volttron platform source here](https://bitbucket.org/berkeleylab/rtunetwork/overview).

The Agents contained in this repo can be built just like normal Volttron agents. Aside from Volttron, the only dependency required by these agents is the loadshape module. Within each Agent, this dependency is declared both in setup.py as well as requirements.txt.

For installation instructions related to the loadshape module, please see the loadshape module documentation:

[Loadshape module documentation](https://bitbucket.org/berkeleylab/eetd-loadshape)


## Event Performance Agent Usage
To request an event performance calculation from the Event Performance Agent, a requesting agent should publish a message to the **eventperformance/request** topic using the publish_json method.

An example message is shown below:
```python
example_message = {
    "load_data": [(1379487600, 5), (1379488500, 5), ... (1379491200, 5)],
    "temp_data": [(1379487600, 72), (1379488500, 72), ... (1379491200, 72)],
    "timezone": 'America/Los_Angeles',
    "temp_units": "F",
    "sq_ft": 5600,
    "start_at": "09-27-2013 00:00:00",
    "end_at": "09-28-2013 00:00:00"
    }
```

Except for "load_data" all keys are optional, but in nearly all cases "start_at" and "end_at" times should be provided.

The contents of this message will be passed directly to the loadshape module and a set of event performance statistics will be calculated using the arguments provided. Once the event statistics calculations have completed, the Event Performance Agent will publish a message to the **eventperformance/responses/[requesting-AgentID]** topic. The message published to this topic will contain a set of event performance statistics that characterize the performance of the actual load relative to the calculated baseline during the time period provided.
