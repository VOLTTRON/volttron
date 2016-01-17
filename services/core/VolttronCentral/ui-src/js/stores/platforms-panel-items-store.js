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
                "children": ["5461fedc-65ba-43fe-21dc-098765bafedl"],                    
                "5461fedc-65ba-43fe-21dc-098765bafedl":
                {
                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                    "name": "OutdoorAirTemperature",
                    "status": "GOOD",
                    "type": "point",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
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
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "OutdoorAirTemperature",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingPower",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
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
                                "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                "5461fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingCall",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                                },
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CondenserFanPower",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
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
            return (parent.status !== filterStatus);
        }

        compareTerm = filterStatus;
    }
    else if (filterStatus === "")
    {
        compareFunct = function (parent, filterTerm)
        {
            return (parent.name.indexOf(filterTerm) < 0);
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
