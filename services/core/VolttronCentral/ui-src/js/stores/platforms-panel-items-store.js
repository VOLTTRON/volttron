'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _items = {
    "platforms": {

        "4687fedc-65ba-43fe-21dc-098765bafedc":
        {
            "uuid": "4687fedc-65ba-43fe-21dc-098765bafedc",
            "name": "PNNL",
            "status": "GOOD",
            "children": ["buildings"],
            "path": ["platforms"],
            "buildings": {
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "ISB1",
                    "status": "GOOD",
                    "children": ["agents", "devices"],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                    "agents": {
                        "2461fedc-65ba-43fe-21dc-098765bafede":
                        {
                            "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                            "name": "Platform Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        },
                        "7897fedc-65ba-43fe-21dc-098765bafedf":
                        {
                            "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                            "name": "SqlHistorian",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        }
                    },
                    "devices": {
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "5461fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MinimumSupplyFanSpeed",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                },
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                }
                            }
                        },
                        "4567fedc-65ba-43fe-21dc-098765bafedm":
                        {
                            "uuid": "4567fedc-65ba-43fe-21dc-098765bafedm",
                            "name": "RTU2",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "7681fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "7681fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "4567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                },
                                "8671fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "8671fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "4567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                }
                            }
                        }
                    }
                },
                "2221fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2221fedc-65ba-43fe-21dc-098765bafede",
                    "name": "ISB2",
                    "status": "GOOD",
                    "children": ["agents", "devices"],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                    "agents": {
                        "3331fedc-65ba-43fe-21dc-098765bafede":
                        {
                            "uuid": "3331fedc-65ba-43fe-21dc-098765bafede",
                            "name": "Platform Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        },
                        "4447fedc-65ba-43fe-21dc-098765bafedf":
                        {
                            "uuid": "4447fedc-65ba-43fe-21dc-098765bafedf",
                            "name": "SqlHistorian",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        }
                    },
                    "devices": {
                        "5551fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5551fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "7771fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "7771fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MinimumSupplyFanSpeed",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "5551fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                },
                                "8881fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "8881fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "5551fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                }
                            }
                        },
                        "6567fedc-65ba-43fe-21dc-098765bafedm":
                        {
                            "uuid": "6567fedc-65ba-43fe-21dc-098765bafedm",
                            "name": "RTU2",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "9991fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "9991fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "6567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                },
                                "1000fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "1000fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "6567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                }
                            }
                        }
                    }
                }
            }
        },
        "6801fedc-65ba-43fe-21dc-098765bafedc":
        {
            "uuid": "6801fedc-65ba-43fe-21dc-098765bafedc",
            "name": "UW",
            "status": "BAD",
            "children": ["buildings"],
            "path": ["platforms"],
            "buildings": {
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "HUB",
                    "status": "GOOD",
                    "children": ["agents", "devices"],
                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                    "agents": {
                        "2461fedc-65ba-43fe-21dc-098765bafede":
                        {
                            "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                            "name": "Platform Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        },
                        "7897fedc-65ba-43fe-21dc-098765bafedf":
                        {
                            "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                            "name": "SqlHistorian",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        }
                    },
                    "devices": {
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "status": "GOOD",
                            "children": "points",
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "5461fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MinimumSupplyFanSpeed",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                },
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                }
                            }
                        },
                        "4567fedc-65ba-43fe-21dc-098765bafedm":
                        {
                            "uuid": "4567fedc-65ba-43fe-21dc-098765bafedm",
                            "name": "RTU2",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "7681fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "7681fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "4567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                },
                                "8671fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "8671fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "4567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                }
                            }
                        }
                    }
                },
                "2221fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2221fedc-65ba-43fe-21dc-098765bafede",
                    "name": "FAC",
                    "status": "BAD",
                    "children": ["agents", "devices"],
                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                    "agents": {
                        "1357fedc-65ba-43fe-21dc-098765bafedg":
                        {
                            "uuid": "1357fedc-65ba-43fe-21dc-098765bafedg",
                            "name": "Husky Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        },
                        "3571fedc-65ba-43fe-21dc-098765bafedh":
                        {
                            "uuid": "3571fedc-65ba-43fe-21dc-098765bafedh",
                            "name": "Listener Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        },
                        "5797fedc-65ba-43fe-21dc-098765bafedi":
                        {
                            "uuid": "5797fedc-65ba-43fe-21dc-098765bafedi",
                            "name": "SqlLiteHistorian",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        }
                    },
                    "devices": {
                        "1451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "HVAC1",
                            "status": "BAD",
                            "children": ["points"],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "0371fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "0371fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "BAD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "1451fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                },
                                "7301fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "7301fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "1451fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                }
                            }
                        },
                        "2567fedc-65ba-43fe-21dc-098765bafedm":
                        {
                            "uuid": "2567fedc-65ba-43fe-21dc-098765bafedm",
                            "name": "HVAC2",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "4891fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4891fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "2567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                },
                                "9841fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "9841fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "6801fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2221fedc-65ba-43fe-21dc-098765bafede", "devices", "2567fedc-65ba-43fe-21dc-098765bafedm", "points"]
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
            "status": "UNKNOWN",
            "children": ["buildings"],
            "path": ["platforms"],
            "buildings": {
                "1101fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1101fedc-65ba-43fe-21dc-098765bafede",
                    "name": "CIC",
                    "status": "GOOD",
                    "children": ["agents", "devices"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                    "agents": {
                        "2461fedc-65ba-43fe-21dc-098765bafede":
                        {
                            "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                            "name": "Platform Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "agents"] 
                        },
                        "7897fedc-65ba-43fe-21dc-098765bafedf":
                        {
                            "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                            "name": "SqlHistorian",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "agents"] 
                        }
                    },
                    "devices": {
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "5461fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MinimumSupplyFanSpeed",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                },
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                }
                            }
                        },
                        "4567fedc-65ba-43fe-21dc-098765bafedm":
                        {
                            "uuid": "4567fedc-65ba-43fe-21dc-098765bafedm",
                            "name": "RTU2",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "7681fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "7681fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "devices", "4567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                },
                                "8671fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "8671fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1101fedc-65ba-43fe-21dc-098765bafede", "devices", "4567fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                }
                            }
                        }
                    }
                },
                "2211fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2211fedc-65ba-43fe-21dc-098765bafede",
                    "name": "BESL",
                    "status": "UNKNOWN",
                    "children": ["agents", "devices"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                    "agents": {
                        "7531fedc-65ba-43fe-21dc-098765bafedk":
                        {
                            "uuid": "7531fedc-65ba-43fe-21dc-098765bafedk",
                            "name": "Platform Agent",
                            "status": "GOOD",
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        },
                        "5317fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5317fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "SqlLiteHistorian",
                            "status": "UNKNOWN",
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "agents"]
                        }
                    },
                    "devices": {
                        "3671fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "3671fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "HVAC1",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "3101fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "3101fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "devices", "3671fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                },
                                "0131fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "0131fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "devices", "3671fedc-65ba-43fe-21dc-098765bafedl", "points"]
                                }
                            }
                        },
                        "4787fedc-65ba-43fe-21dc-098765bafedm":
                        {
                            "uuid": "4787fedc-65ba-43fe-21dc-098765bafedm",
                            "name": "HVAC2",
                            "status": "GOOD",
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "devices"],
                            "points": {
                                "4281fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4281fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingValvePosition",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "devices", "4787fedc-65ba-43fe-21dc-098765bafedm", "points"]
                                },
                                "8241fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "8241fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "MixedAirTemperature",
                                    "status": "GOOD",
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "2211fedc-65ba-43fe-21dc-098765bafede", "devices", "4787fedc-65ba-43fe-21dc-098765bafedm", "points"]
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

var platformsPanelItemsStore = new Store();

function buildItemsList(parent, child)
{
    var itemsList = [];
    var items = _items;

    //First find the parent item according to its path
    for (var i = 0; i < parent.path.length; i++)
    {
        if (items.hasOwnProperty(parent.path[i]))
        {
            items = items[parent.path[i]];
        }
    }

    //Then create a list of the children
    if (items[parent.uuid].hasOwnProperty(child))
    {
        for (var key in items[parent.uuid][child])
        {
            itemsList.push(items[parent.uuid][child][key]);
        }
    }

    return itemsList;
}

platformsPanelItemsStore.getItems = function (parent) {

    var itemsList = [];

    if (parent === "platforms")
    {
        for (var key in _items[parent])
        {
            itemsList.push(_items[parent][key]);
        }
    }
    else
    {
        var notAgentsOrDevices = true;

        if (parent.children.indexOf("agents") !== -1)
        {
            var agentsList = buildItemsList(parent, "agents");
            itemsList.push({"agents": agentsList});
            notAgentsOrDevices = false;
        }

        if (parent.children.indexOf("devices") !== -1)
        {
            var devicesList = buildItemsList(parent, "devices");
            itemsList.push({"devices": devicesList});
            notAgentsOrDevices = false;
        }

        if (notAgentsOrDevices)
        {
            itemsList = buildItemsList(parent, parent.children[0]);
        }
    }

    return itemsList;
};

platformsPanelItemsStore.getExpanded = function () {
    return _expanded;
};

platformsPanelItemsStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            _items["platforms"] = action.platforms;

            for (var key in _items["platforms"])
            {
                _items["platforms"][key]["children"] = ["buildings"];                
                _items["platforms"][key]["path"] = ["platforms"];
            }
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_BUILDING_STATUSES:
            _items["platforms"][action.platform.uuid]["buildings"] = action.buildings;

            for (var key in _items["platforms"][action.platform.uuid]["buildings"])
            {
                _items["platforms"][action.platform.uuid]["buildings"][key]["children"] = ["agents", "devices"];                
                _items["platforms"][action.platform.uuid]["buildings"][key]["path"] = ["platforms", action.platform.uuid, "buildings"];
            }
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:
            _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["agents"] = action.agents;

            for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["agents"])
            {
                _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["agents"][key]["children"] = [];                
                _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["agents"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "agents"];
            }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:
            _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"] = action.devices;

            for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"])
            {
                _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][key]["children"] = ["points"];                
                _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices"];
            }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_DATAPOINT_STATUSES:
            _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"] = action.points;

            for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"])
            {
                _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["children"] = [];
                _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices", action.device.uuid, "points"];
            }

            platformsPanelItemsStore.emitChange();
            break;
    }
});

module.exports = platformsPanelItemsStore;
