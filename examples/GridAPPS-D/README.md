# GridAPPSD Simulation Example Agent

This is an example agent that demonstrates how to integrate with GridAPPSD platform, 
run power system simulations and send/receive messages back and forth between VOLTTRON and
GridAPPSD environment. 

## GridAPPSD installation
For installing setup in Ubuntu based systems, follow the steps described in 
https://gridappsd.readthedocs.io/en/master/installing_gridappsd/index.html

## GridAPPSD Agent Configuration

In activated VOLTTRON environment, install all the GridAPPSD dependent python packages

```
cd examples/GridAPPS-D/
pip install -r requirements.txt
```

You can specify the configuration in either json or yaml format.  The json format is specified
below. 

```` json
{
    "power_system_config": {
        "GeographicalRegion_name": "_73C512BD-7249-4F50-50DA-D93849B89C43",
        "SubGeographicalRegion_name": "_ABEB635F-729D-24BF-B8A4-E2EF268D8B9E",
        "Line_name": "_49AD8E07-3BF9-A4E2-CB8F-C3722F837B62"
    },
    "application_config": {
        "applications": []
    },
    "simulation_config": {
        "start_time": "1595361226",
        "duration": "120",
        "simulator": "GridLAB-D",
        "timestep_frequency": "1000",
        "timestep_increment": "1000",
        "run_realtime": true,
        "simulation_name": "ieee13nodeckt",
        "power_flow_solver_method": "NR",
        "model_creation_config": {
            "load_scaling_factor": "1",
            "schedule_name": "ieeezipload",
            "z_fraction": "0",
            "i_fraction": "1",
            "p_fraction": "0",
            "randomize_zipload_fractions": false,
            "use_houses": false
        }
    },
    "test_config": {
        "events": [],
        "appId": ""
    },
    "service_configs": []
}
````

## Running GridAPPSD Simulation Example agent

1. In a new terminal, navigate to 'gridappsd-docker' directory. Start container services needed by GridAPPSD.
    ````
    ./run.sh
    ````

2. Start GridAPPSD within the docker environment
   ````
   ./run-docker.sh
   ````

3. In another terminal, start VOLTTRON and run a listener agent
   ````
   ./start-volttron
   ```` 

4. Start GridAPPSD simulation example agent 
    ````
    source env/bin/activate
    python scripts/install-agent.py -s examples/GridAPPS-D/ -c examples/GridAPPS-D/test_gridappsd.json -i gappsd --start --force
    ````
   
5. You will see that GridAPPSD simulation starts and sends measurement data to VOLTTRON which is then republished
   on VOLTTRON message bus
   
   ````
    04 17:51:14,642 (listeneragent-3.3 27855) __main__ INFO: Peer: pubsub, Sender: gappsd:, Bus: , Topic: gridappsd/measurement, Headers: {'Date': '2020-08-04T21:51:14.596162+00:00', 'Content-Type': 'application/json', 'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message: 
    {'data': {'_00ff72f5-628c-462b-bdd1-2dcc1bd519b5': {'measurement_mrid': '_00ff72f5-628c-462b-bdd1-2dcc1bd519b5',
                                                    'value': 1},
          '_017f359e-77e5-48ca-9a02-eaa59d14a941': {'angle': 86.21660957775951,
                                                    'magnitude': 2560.0286365239986,
                                                    'measurement_mrid': '_017f359e-77e5-48ca-9a02-eaa59d14a941'},
          '_04d9f780-ad0c-4205-b94d-531e66087f2d': {'measurement_mrid': '_04d9f780-ad0c-4205-b94d-531e66087f2d',
                                                    'value': 1},
          '_0769c269-2a4f-4e30-a5ae-fa30f7dc271b': {'angle': 82.74673304218659,
                                                    'magnitude': 2519.580420609152,
                                                    'measurement_mrid': '_0769c269-2a4f-4e30-a5ae-fa30f7dc271b'},
          '_0793bcc6-eab5-45d1-891a-973379c5cdec': {'angle': 82.74673304218659,
                                                    'magnitude': 2519.580420609152,
                                                    'measurement_mrid': '_0793bcc6-eab5-45d1-891a-973379c5cdec'},
          '_0c2e8ddb-6043-4721-a276-27fc19e86c04': {'angle': -15.330435576009576,
                                                    'magnitude': 569290.5754298957,
                                                    'measurement_mrid': '_0c2e8ddb-6043-4721-a276-27fc19e86c04'},
         }
    }
    ````

