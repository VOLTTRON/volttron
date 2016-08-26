.. _Analytics-Historian:

Analytics Historian
===================

An Analytics Historian (OpenEIS) has been developed to integrate real
time data ingestion into the OpenEIS platform. In order for the OpenEIS
historian to be able to communicate with an OpenEIS server a datasource
must be created on the OpenEIS server. The process of creating a dataset
is documented in the `OpenEIS User's
Guide <https://github.com/VOLTTRON/openeis/raw/2.x/guides/PNNL-24065%20-%20OpenEIS%20Users%20Guide.pdf>`__
under *Creating a Dataset* heading. Once a dataset is created you will
be able to add datasets through the configuration file. An example
configuration for the historian is as follows:

::

    {
        # The agent id is used for display in volttron central.
        "agentid": "openeishistorian",
        # The vip identity to use with this historian.
        # should not be a platform.historian!
        #
        # Default value is un referenced because it listens specifically to the bus.
        #"identity": "openeis.historian",
            
        # Require connection section for all historians.  The openeis historian
        # requires a url for the openis server and login credentials for publishing
        # to the correct user's dataset.
        "connection": {
            "type": "openeis",
            "params": {
                # The server that is running openeis
                # the rest path for the dataset is dataset/append/{id}
                # and will be populated from the topic_dataset list below.  
                "uri": "http://localhost:8000",
                
                # Openeis requires a username/password combination in order to
                # login to the site via rest or the ui.
                # 
                "login": "volttron",
                "password": "volttron"
            }
        },
        
        # All datasets that are going to be recorded by this historian need to be
        # defined here.
        # 
        # A dataset definition consists of the following parts
        #    "ds1": {
        #
        #        The dataset id that was created in openeis.
        #        "dataset_id": 1,
        #
        #        Setting to 1 allows only the caching of data that actually meets
        #        the mapped point criteria for this dataset.
        #        Defaults to 0
        #        "ignore_unmapped_points": 0,
        #   
        #        An ordered list of points that are to be posted to openeis. The 
        #        points must contain a key specifying the incoming topic with the
        #        value an openeis schema point:  
        #        [
        #            {"rtu4/OutsideAirTemp": "campus1/building1/rtu4/OutdoorAirTemperature"}
        #        ]
        #    },
        "dataset_definitions": {
            "ds1": {
                "dataset_id": 1,
                "ignore_unmapped_points": 0,
                "points": [
                    {"campus1/building1/OutsideAirTemp": "campus1/building1/OutdoorAirTemperature"},
                    {"campus1/building1/HVACStatus": "campus1/building1/HVACStatus"},
                    {"campus1/building1/CompressorStatus": "campus1/building1/LightingStatus"}
                ]
            }
    #,
    #"ds2": {
    #    "id": 2,
    #    "points": [
    #        "rtu4/OutsideAirTemp",
    #        "rtu4/MixedAirTemp"    
    #    ]
    #        }
        }
    }

