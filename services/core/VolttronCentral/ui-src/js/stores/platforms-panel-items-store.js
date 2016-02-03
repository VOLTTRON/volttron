'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _pointsOrder = 0;
var _devicesOrder = 1;
var _buildingsOrder = 2;
var _agentsOrder = 3;

var _items = {
    "platforms": {

        "4687fedc-65ba-43fe-21dc-098765bafedc": {
            "uuid": "4687fedc-65ba-43fe-21dc-098765bafedc",
            "name": "PNNL",
            "status": "GOOD",
            "type": "platform",
            "sortOrder": 0,
            "children": ["agents", "buildings", "points"],
            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc"],
            "points": {
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points"],
                "name": "Points",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _pointsOrder,
                "children": ["5461fedc-65ba-43fe-21dc-000765bafedl"],                    
                "5461fedc-65ba-43fe-21dc-000765bafedl":
                {
                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                    "name": "OutdoorAirTemperature",
                    "status": "GOOD",
                    "type": "point",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points", "5461fedc-65ba-43fe-21dc-000765bafedl"],
                    "data": [
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 1,
                                    "avg_max_temp_f": 46.83,
                                    "avg_min_temp_f": 28.1,
                                    "avg_temp_f": 37.47,
                                    "total_percipitation_in": 2.35,
                                    "total_snowfall_in": 9.6
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 2,
                                    "avg_max_temp_f": 47.58,
                                    "avg_min_temp_f": 26.35,
                                    "avg_temp_f": 36.96,
                                    "total_percipitation_in": 7.61,
                                    "total_snowfall_in": 25.5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 3,
                                    "avg_max_temp_f": 51.45,
                                    "avg_min_temp_f": 31.39,
                                    "avg_temp_f": 41.42,
                                    "total_percipitation_in": 11.74,
                                    "total_snowfall_in": 39.6
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 4,
                                    "avg_max_temp_f": 61.5,
                                    "avg_min_temp_f": 35.13,
                                    "avg_temp_f": 48.32,
                                    "total_percipitation_in": 1.44,
                                    "total_snowfall_in": 2.3
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 5,
                                    "avg_max_temp_f": 64.9,
                                    "avg_min_temp_f": 40.68,
                                    "avg_temp_f": 52.79,
                                    "total_percipitation_in": 2.17,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 6,
                                    "avg_max_temp_f": 73.79,
                                    "avg_min_temp_f": 48.18,
                                    "avg_temp_f": 60.98,
                                    "total_percipitation_in": 2.06,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 7,
                                    "avg_max_temp_f": 85.07,
                                    "avg_min_temp_f": 56.1,
                                    "avg_temp_f": 70.58,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 8,
                                    "avg_max_temp_f": 88.1,
                                    "avg_min_temp_f": 56.45,
                                    "avg_temp_f": 72.28,
                                    "total_percipitation_in": 0.15,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 9,
                                    "avg_max_temp_f": 84.47,
                                    "avg_min_temp_f": 54.13,
                                    "avg_temp_f": 69.3,
                                    "total_percipitation_in": 3.42,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 10,
                                    "avg_max_temp_f": 71.14,
                                    "avg_min_temp_f": 43.54,
                                    "avg_temp_f": 57.34,
                                    "total_percipitation_in": 2.8,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 11,
                                    "avg_max_temp_f": 53.62,
                                    "avg_min_temp_f": 32.07,
                                    "avg_temp_f": 42.62,
                                    "total_percipitation_in": 1.07,
                                    "total_snowfall_in": 5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 12,
                                    "avg_max_temp_f": 48.97,
                                    "avg_min_temp_f": 25.42,
                                    "avg_temp_f": 37.19,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                }
                            ]
                }
            },
            "agents": {                
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents"],
                "name": "Agents",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _agentsOrder,
                "children": ["2461fedc-65ba-43fe-21dc-098765bafede", "7897fedc-65ba-43fe-21dc-098765bafedf"], 
                "2461fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                    "name": "Platform Agent",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents", "2461fedc-65ba-43fe-21dc-098765bafede"]
                },
                "7897fedc-65ba-43fe-21dc-098765bafedf":
                {
                    "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                    "name": "SqlHistorian",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents", "7897fedc-65ba-43fe-21dc-098765bafedf"]
                }
            },
            "buildings": {             
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                "name": "Buildings",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _buildingsOrder,
                "children": ["1111fedc-65ba-43fe-21dc-098765bafede"],
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "ISB1",
                    "status": "GOOD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-111765bafedl", "6451fedc-65ba-43fe-21dc-000765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-111765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                            "name": "OutdoorAirTemperature",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-111765bafedl"],
                            "data": [
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 1,
                                    "avg_max_temp_f": 51.5,
                                    "avg_min_temp_f": 28.2,
                                    "avg_temp_f": 39.85,
                                    "total_percipitation_in": 4.98,
                                    "total_snowfall_in": 1.1
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 2,
                                    "avg_max_temp_f": 54.32,
                                    "avg_min_temp_f": 29.86,
                                    "avg_temp_f": 42.09,
                                    "total_percipitation_in": 0.9,
                                    "total_snowfall_in": 11
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 3,
                                    "avg_max_temp_f": 54.45,
                                    "avg_min_temp_f": 32.62,
                                    "avg_temp_f": 43.53,
                                    "total_percipitation_in": 5.76,
                                    "total_snowfall_in": 24.5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 4,
                                    "avg_max_temp_f": 63.69,
                                    "avg_min_temp_f": 38.83,
                                    "avg_temp_f": 51.12,
                                    "total_percipitation_in": 4.45,
                                    "total_snowfall_in": 5.5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 5,
                                    "avg_max_temp_f": 75.45,
                                    "avg_min_temp_f": 46.57,
                                    "avg_temp_f": 61.16,
                                    "total_percipitation_in": 0.33,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 6,
                                    "avg_max_temp_f": 82.21,
                                    "avg_min_temp_f": 51.36,
                                    "avg_temp_f": 66.79,
                                    "total_percipitation_in": 0.67,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 7,
                                    "avg_max_temp_f": 89.3,
                                    "avg_min_temp_f": 57.4,
                                    "avg_temp_f": 73.35,
                                    "total_percipitation_in": 0.01,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 8,
                                    "avg_max_temp_f": 93.14,
                                    "avg_min_temp_f": 60.62,
                                    "avg_temp_f": 76.88,
                                    "total_percipitation_in": 0.06,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 9,
                                    "avg_max_temp_f": 87.41,
                                    "avg_min_temp_f": 56.1,
                                    "avg_temp_f": 71.76,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 10,
                                    "avg_max_temp_f": 72.04,
                                    "avg_min_temp_f": 44.89,
                                    "avg_temp_f": 58.46,
                                    "total_percipitation_in": 1.47,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 11,
                                    "avg_max_temp_f": 56.04,
                                    "avg_min_temp_f": 35.39,
                                    "avg_temp_f": 45.71,
                                    "total_percipitation_in": 5.06,
                                    "total_snowfall_in": 6.5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "month": 12,
                                    "avg_max_temp_f": 42.64,
                                    "avg_min_temp_f": 29.93,
                                    "avg_temp_f": 36.29,
                                    "total_percipitation_in": 11.91,
                                    "total_snowfall_in": 18.5
                                }
                            ]
                        },
                        "6451fedc-65ba-43fe-21dc-000765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                            "name": "WholeBuildingPower",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-000765bafedl"],
                            "data": [
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 1,
                                    "avg_max_temp_f": 44.25,
                                    "avg_min_temp_f": 23.25,
                                    "avg_temp_f": 33.75,
                                    "total_percipitation_in": 0.91,
                                    "total_snowfall_in": 2
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 2,
                                    "avg_max_temp_f": 53.14,
                                    "avg_min_temp_f": 27.9,
                                    "avg_temp_f": 40.52,
                                    "total_percipitation_in": 0.5,
                                    "total_snowfall_in": 1.1
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 3,
                                    "avg_max_temp_f": 61.18,
                                    "avg_min_temp_f": 36.18,
                                    "avg_temp_f": 48.68,
                                    "total_percipitation_in": 2.99,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 4,
                                    "avg_max_temp_f": 67.76,
                                    "avg_min_temp_f": 41.24,
                                    "avg_temp_f": 54.5,
                                    "total_percipitation_in": 1.64,
                                    "total_snowfall_in": 0.5
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 5,
                                    "avg_max_temp_f": 73.55,
                                    "avg_min_temp_f": 47.86,
                                    "avg_temp_f": 60.7,
                                    "total_percipitation_in": 2.96,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 6,
                                    "avg_max_temp_f": 84.77,
                                    "avg_min_temp_f": 55.1,
                                    "avg_temp_f": 69.93,
                                    "total_percipitation_in": 0.16,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 7,
                                    "avg_max_temp_f": 93.69,
                                    "avg_min_temp_f": 61.81,
                                    "avg_temp_f": 77.75,
                                    "total_percipitation_in": 0.02,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 8,
                                    "avg_max_temp_f": 89.25,
                                    "avg_min_temp_f": 55.89,
                                    "avg_temp_f": 72.57,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 9,
                                    "avg_max_temp_f": 82,
                                    "avg_min_temp_f": 50.78,
                                    "avg_temp_f": 66.39,
                                    "total_percipitation_in": 0.92,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 10,
                                    "avg_max_temp_f": 69.5,
                                    "avg_min_temp_f": 39.5,
                                    "avg_temp_f": 54.5,
                                    "total_percipitation_in": 0.94,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 11,
                                    "avg_max_temp_f": 60.32,
                                    "avg_min_temp_f": 33.63,
                                    "avg_temp_f": 46.97,
                                    "total_percipitation_in": 0.73,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "month": 12,
                                    "avg_max_temp_f": 48.81,
                                    "avg_min_temp_f": 24.95,
                                    "avg_temp_f": 36.88,
                                    "total_percipitation_in": 1.53,
                                    "total_snowfall_in": 10.5
                                }
                            ]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "status": "GOOD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["devices", "points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["5461fedc-65ba-43fe-21dc-222765bafedl", "6451fedc-65ba-43fe-21dc-11165bafedl"],
                                "5461fedc-65ba-43fe-21dc-222765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                    "name": "CoolingCall",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-222765bafedl"],
                                    "data": [
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 1,
                                            "avg_max_temp_f": 57.13,
                                            "avg_min_temp_f": 31.32,
                                            "avg_temp_f": 44.23,
                                            "total_percipitation_in": 1.01,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 2,
                                            "avg_max_temp_f": 54.64,
                                            "avg_min_temp_f": 34.82,
                                            "avg_temp_f": 44.73,
                                            "total_percipitation_in": 5.47,
                                            "total_snowfall_in": 2
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 3,
                                            "avg_max_temp_f": 62.48,
                                            "avg_min_temp_f": 37.44,
                                            "avg_temp_f": 49.96,
                                            "total_percipitation_in": 3.89,
                                            "total_snowfall_in": 1
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 4,
                                            "avg_max_temp_f": 66.56,
                                            "avg_min_temp_f": 40.5,
                                            "avg_temp_f": 53.53,
                                            "total_percipitation_in": 2.81,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 5,
                                            "avg_max_temp_f": 75.83,
                                            "avg_min_temp_f": 46.83,
                                            "avg_temp_f": 61.33,
                                            "total_percipitation_in": 0.73,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 6,
                                            "avg_max_temp_f": 85.28,
                                            "avg_min_temp_f": 53.39,
                                            "avg_temp_f": 69.33,
                                            "total_percipitation_in": 0.2,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 7,
                                            "avg_max_temp_f": 91,
                                            "avg_min_temp_f": 60.93,
                                            "avg_temp_f": 75.97,
                                            "total_percipitation_in": 0.28,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 8,
                                            "avg_max_temp_f": 88.85,
                                            "avg_min_temp_f": 57.8,
                                            "avg_temp_f": 73.33,
                                            "total_percipitation_in": 0.15,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 9,
                                            "avg_max_temp_f": 85.04,
                                            "avg_min_temp_f": 53.5,
                                            "avg_temp_f": 69.27,
                                            "total_percipitation_in": 0.54,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 10,
                                            "avg_max_temp_f": 76.79,
                                            "avg_min_temp_f": 36.18,
                                            "avg_temp_f": 56.48,
                                            "total_percipitation_in": 0,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 11,
                                            "avg_max_temp_f": 59.27,
                                            "avg_min_temp_f": 33.53,
                                            "avg_temp_f": 46.4,
                                            "total_percipitation_in": 2.98,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "month": 12,
                                            "avg_max_temp_f": 48.86,
                                            "avg_min_temp_f": 32.79,
                                            "avg_temp_f": 40.82,
                                            "total_percipitation_in": 4.71,
                                            "total_snowfall_in": 1.2
                                        }
                                    ]
                                },
                                "6451fedc-65ba-43fe-21dc-11165bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                    "name": "CondenserFanPower",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-11165bafedl"],
                                    "data": [
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 1,
                                            "avg_max_temp_f": 56.96,
                                            "avg_min_temp_f": 30.39,
                                            "avg_temp_f": 43.68,
                                            "total_percipitation_in": 0.1,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 2,
                                            "avg_max_temp_f": 64.82,
                                            "avg_min_temp_f": 36,
                                            "avg_temp_f": 50.3,
                                            "total_percipitation_in": 1.63,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 3,
                                            "avg_max_temp_f": 67.29,
                                            "avg_min_temp_f": 38.33,
                                            "avg_temp_f": 52.81,
                                            "total_percipitation_in": 0.43,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 4,
                                            "avg_max_temp_f": 66.35,
                                            "avg_min_temp_f": 37.73,
                                            "avg_temp_f": 52.04,
                                            "total_percipitation_in": 3.15,
                                            "total_snowfall_in": 4.5
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 5,
                                            "avg_max_temp_f": 68.81,
                                            "avg_min_temp_f": 43.96,
                                            "avg_temp_f": 56.38,
                                            "total_percipitation_in": 1.97,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 6,
                                            "avg_max_temp_f": 87.97,
                                            "avg_min_temp_f": 57.23,
                                            "avg_temp_f": 72.6,
                                            "total_percipitation_in": 0.79,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 7,
                                            "avg_max_temp_f": 87.68,
                                            "avg_min_temp_f": 59.71,
                                            "avg_temp_f": 73.69,
                                            "total_percipitation_in": 2.58,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 8,
                                            "avg_max_temp_f": 91.39,
                                            "avg_min_temp_f": 58.68,
                                            "avg_temp_f": 75.03,
                                            "total_percipitation_in": 0.04,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 9,
                                            "avg_max_temp_f": 85.07,
                                            "avg_min_temp_f": 55.86,
                                            "avg_temp_f": 70.41,
                                            "total_percipitation_in": 0.15,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 10,
                                            "avg_max_temp_f": 73.26,
                                            "avg_min_temp_f": 46.17,
                                            "avg_temp_f": 59.93,
                                            "total_percipitation_in": 3.37,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 11,
                                            "avg_max_temp_f": 50.5,
                                            "avg_min_temp_f": 29.36,
                                            "avg_temp_f": 39.93,
                                            "total_percipitation_in": 3.74,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "month": 12,
                                            "avg_max_temp_f": 43.42,
                                            "avg_min_temp_f": 24.65,
                                            "avg_temp_f": 34.03,
                                            "total_percipitation_in": 5.18,
                                            "total_snowfall_in": 0
                                        }]
                                }
                            },
                            "devices": {    
                                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices"],
                                "name": "Devices",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _devicesOrder,
                                "children": ["4488fedc-65ba-43fe-21dc-098765bafedl"],
                                "4488fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4488fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "Zone",
                                    "status": "GOOD",
                                    "type": "device",
                                    "sortOrder": 0,
                                    "children": ["points"],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl"],
                                    "points": {  
                                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                        "name": "Points",
                                        "status": "GOOD",
                                        "type": "type",
                                        "sortOrder": _pointsOrder,
                                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "FirstStageAuxilaryHeat",
                                            "status": "GOOD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                                        },
                                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "SecondStageAuxilaryHeat",
                                            "status": "GOOD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                        }
                                    }
                                }
                            }
                        }
                    }   
                }
            }
        },
        "9757fedc-65ba-43fe-21dc-098765bafedc":
        {
            "uuid": "9757fedc-65ba-43fe-21dc-098765bafedc",
            "name": "WSU",
            "status": "BAD",
            "type": "platform",
            "sortOrder": 0,
            "children": ["agents", "buildings"],
            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc"],
            "agents": {                
                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents"],
                "name": "Agents",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _agentsOrder,
                "children": ["2461fedc-65ba-43fe-21dc-098765bafede", "7897fedc-65ba-43fe-21dc-098765bafedf"], 
                "2461fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                    "name": "Platform Agent",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents", "2461fedc-65ba-43fe-21dc-098765bafede"]
                },
                "7897fedc-65ba-43fe-21dc-098765bafedf":
                {
                    "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                    "name": "SqlHistorian",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents", "7897fedc-65ba-43fe-21dc-098765bafedf"]
                }
            },
            "buildings": {             
                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                "name": "Buildings",
                "status": "BAD",
                "type": "type",
                "sortOrder": _buildingsOrder,
                "children": ["1111fedc-65ba-43fe-21dc-098765bafede", "1333fedc-65ba-43fe-21dc-098765bafede"],
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "BSEL",
                    "status": "BAD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "status": "UNKNOWN",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingElectricity",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "LightingStatus",
                            "status": "UNKNOWN",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "status": "BAD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "AHU",
                            "status": "BAD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["devices", "points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["6451fedc-65ba-43fe-21dc-098765bafedl"],                                
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "DuctStaticPressureSetPoint",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                }
                            },
                            "devices": {    
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices"],
                                "name": "Devices",
                                "status": "BAD",
                                "type": "type",
                                "sortOrder": _devicesOrder,
                                "children": ["4488fedc-65ba-43fe-21dc-098765bafedl"],
                                "4488fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4488fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "Zone",
                                    "status": "BAD",
                                    "type": "device",
                                    "sortOrder": 0,
                                    "children": ["points"],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl"],
                                    "points": {  
                                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                        "name": "Points",
                                        "status": "BAD",
                                        "type": "type",
                                        "sortOrder": _pointsOrder,
                                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "TerminalBoxDamperCommand",
                                            "status": "BAD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                                        },
                                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "ZoneTemperature",
                                            "status": "GOOD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                        }
                                    }
                                }
                            }
                        }
                    }   
                },
                "1333fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1333fedc-65ba-43fe-21dc-098765bafede",
                    "name": "CIC",
                    "status": "GOOD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingGas",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "OutdoorAirRelativeHumidity",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "Chilled_Water_Distribution_System",
                            "status": "GOOD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["6451fedc-65ba-43fe-21dc-098765bafedl"],                                
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "NaturalGasEnergy",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                }
                            }
                        }
                    }   
                }
            }
        }
    }
};

var _expanded = false;
var _itemTypes = ["platforms", "buildings", "agents", "devices", "points"];

var platformsPanelItemsStore = new Store();


platformsPanelItemsStore.getItems = function (parent, parentPath) {

    var itemsList = [];
    var item = _items;

    if (parentPath !== null) // for everything but the top level, drill down to the parent
    {
        for (var i = 0; i < parentPath.length; i++)
        {
            if (item.hasOwnProperty(parentPath[i]))
            {
                item = item[parentPath[i]];
            }
        }
    
          
        for (var i = 0; i < item.children.length; i++)
        {           
            itemsList.push(item[item.children[i]]);
        }
            
    }
    else
    {
        for (var key in item[parent])
        {
            itemsList.push(item[parent][key]);
        }
    } 

    return itemsList;
};

platformsPanelItemsStore.getTreeCopy = function() {

    return JSON.parse(JSON.stringify(_items));
}

platformsPanelItemsStore.getFilteredItems = function (parent, filterTerm, filterStatus) {

    var compareFunct;
    var compareTerm;

    if (filterTerm === "")
    {
        compareFunct = function (parent, filterStatus)
        {
            if (parent.hasOwnProperty("status"))
            {
                return (parent.status !== filterStatus);                
            }
            else
            {
                return (filterStatus !== "UNKNOWN");
            }
        }

        compareTerm = filterStatus;
    }
    else if (filterStatus === "")
    {
        compareFunct = function (parent, filterTerm)
        {
            var upperParent = parent.name.toUpperCase();

            return (upperParent.indexOf(filterTerm.toUpperCase()) < 0);
        }

        compareTerm = filterTerm;
    }

    if (parent.children.length === 0)
    {
        if (compareFunct(parent, compareTerm))
        {
            return null;
        }
        else
        {
            return parent;
        }
    }
    else
    {
        var childrenToDelete = [];

        for (var i = 0; i < parent.children.length; i++)
        {
            var childString = parent.children[i];
            var filteredChild = platformsPanelItemsStore.getFilteredItems(parent[childString], filterTerm, filterStatus);

            if (filteredChild === null)
            {
                delete parent[childString];

                childrenToDelete.push(childString);
            }
        }
        
        for (var i = 0; i < childrenToDelete.length; i++)
        {
            var index = parent.children.indexOf(childrenToDelete[i]);
            parent.children.splice(index, 1);
        }

        if ((parent.children.length === 0) && (compareFunct(parent, compareTerm)))
        {
            parent = null;
        }
        else
        {
            if (parent.children.length > 0)
            {
                parent.expanded = true;
            }
        }

        return parent;
    }
};

platformsPanelItemsStore.getExpandedChildren = function (expandedOn, parent) {

    if (parent.children.length === 0)
    {
        return parent;
    }
    else
    {
        for (var i = 0; i < parent.children.length; i++)
        {
            var childString = parent.children[i];
            var expandedChild = platformsPanelItemsStore.getExpandedChildren(expandedOn, parent[childString]);
        }
        
        parent.expanded = expandedOn;

        return parent;
    }
};


platformsPanelItemsStore.getExpanded = function () {
    return _expanded;
};

platformsPanelItemsStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            
            var platforms = action.platforms;

            platforms.forEach(function (platform)
            {
                _items["platforms"][platform.uuid] = platform; 
                
                var platformItem = _items["platforms"][platform.uuid];
                platformItem.path = ["platforms", platform.uuid];
                // platformItem.status = "GOOD";
                platformItem.children = [];
                platformItem.type = "platform";
            });
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_BUILDING_STATUSES:
            // _items["platforms"][action.platform.uuid]["buildings"] = action.buildings;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][key]["children"] = ["agents", "devices"];                
            //     _items["platforms"][action.platform.uuid]["buildings"][key]["path"] = ["platforms", action.platform.uuid, "buildings"];
            // }
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.agents.length > 0)
            {
                platform.agents = {};
                platform.agents.path = platform.path.slice(0);
                platform.agents.path.push("agents");
                platform.agents.name = "Agents";
                platform.agents.children = [];
                platform.agents.type = "type";
                platform.agents.sortOrder = _agentsOrder;

                if (platform.children.indexOf("agents") < 0)
                {
                    platform.children.push("agents");
                }

                action.agents.forEach(function (agent)
                {
                    var agentProps = agent;
                    agentProps.path = platform.agents.path.slice(0);
                    agentProps.path.push(agent.uuid);
                    // agent.status = "GOOD";
                    agentProps.children = [];
                    agentProps.type = "agent";
                    agentProps.sortOrder = 0;
                    platform.agents.children.push(agent.uuid); 
                    platform.agents[agent.uuid] = agentProps;
                });

            }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:
            // _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"] = action.devices;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][key]["children"] = ["points"];                
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices"];
            // }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_POINT_STATUSES:
            // _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"] = action.points;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["children"] = [];
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices", action.device.uuid, "points"];
            // }

            platformsPanelItemsStore.emitChange();
            break;
    }
});

module.exports = platformsPanelItemsStore;
