'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var devicesStore = require('../stores/devices-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');
var wsapi = require('../lib/wspubsub');

var platformsPanelActionCreators = {    
    togglePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL,
        });
    },

    addNewDevice: function(device_props){
        /*
        device_props example (NOTE: this is an invalid json object because of the '
        {
            'device_address': '10.10.1.15',
            'device_id': 500,
            'path': 'devices/pnnl/foo/2',
            'points': ['ReturnAirTemperature', 'CoolingValveOutputCommand', 'ReturnAirHumidity'],
            'health': {
                'status': 'UNKNOWN',
                'last_updated': '2016-12-21T17:54:28.855561+00:00',
                'context': 'Unpublished'
            }
        }
        */

        // The passed device_props is a string because it comes from a larger
        // object.  We need to replace the ' with " so that the JSON parser
        // will work correctly
        device_props = JSON.parse(device_props.replace(/'/g, '"'))

        var platform = devicesStore.getPlatform();
        
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
            fromWebsocket: true,
            platform: platform,
            devices: [device_props]
        });
    },

    loadChildren: function(type, parent)
    {
        if (type === "platform")
        {
            dispatcher.dispatch({
                type: ACTION_TYPES.START_LOADING_DATA,
                panelItem: parent 
            });

            loadPanelDevices(parent);
        } 

        function loadPanelDevices(platform) {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.get_devices',
                authorization: authorization,
            }).promise
                .then(function (result) {
                    
                    var devicesList = [];
                    var errorKeys = [];

                    for (var key in result)
                    {
                        // Handle if the topic doesn't have enough entities
                        // Should be devices/campus/building/unit
                        // or if devices is not the root we can handle
                        // campus/building/unit
                        // in each case we should be able to deal with sub
                        // devices as well.
                        var splitkey=key.split("/");
                        // Protect against not having devices as the first element
                        // in the array.
                        if (splitkey.length > 0) {
                            if (splitkey[0] != "devices") {
                                splitkey.unshift("devices");
                            }
                        }

                        var path = splitkey.join("/");

                        if (splitkey.length > 3) {
                            var device = JSON.parse(JSON.stringify(result[key]));
                            device.path = path;

                            devicesList.push(device);
                        }
                        else {
                            errorKeys.push(key);
                        }
                    }

                    if (errorKeys.length)
                    {
                        var errorKeysStr = errorKeys.join(", ");
                        var message = "The following device topics were invalid and " +
                            "could not be added to the tree: " + errorKeysStr;

                        statusIndicatorActionCreators.openStatusIndicator("error", message, errorKeysStr);
                    }

                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
                        fromWebsocket: false,
                        platform: platform,
                        devices: devicesList
                    });

                    loadPanelAgents(platform);
                    
                })                     
                .catch(rpc.Error, function (error) {
                    endLoadingData(platform);
                    handle401(error, "Unable to load devices for platform " + platform.name + " in side panel: " + error.message, platform.name);
                });    

        }

        function loadPanelAgents(platform) {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.list_agents',
                authorization: authorization,
            }).promise
                .then(function (agentsList) {
                    
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                        platform: platform,
                        agents: agentsList
                    });

                    loadPerformanceStats(platform);
                })                     
                .catch(rpc.Error, function (error) {
                    endLoadingData(platform);
                    handle401(error, "Unable to load agents for platform " + platform.name + " in side panel: " + error.message, platform.name);
                });    
        }       

        function loadPerformanceStats(parent) {

            if (parent.type === "platform")
            {
                var authorization = authorizationStore.getAuthorization();

                //TODO: use service to get performance for a single platform

                new rpc.Exchange({
                    method: 'list_performance',
                    authorization: authorization,
                    }).promise
                        .then(function (result) {
                            
                            var platformPerformance = result.find(function (item) {
                                return item["platform.uuid"] === parent.uuid;
                            });

                            var pointsList = [];

                            if (platformPerformance && platformPerformance.performance.hasOwnProperty("points"))
                            {
                                var points = platformPerformance.performance.points;

                                points.forEach(function (point) {

                                    var pointName = (point === "percent" ? "cpu / percent" : point.replace("/", " / "));

                                    pointsList.push({
                                        "topic": platformPerformance.performance.topic + "/" + point,
                                        "name": pointName
                                    });
                                });                                
                            }

                            dispatcher.dispatch({
                                type: ACTION_TYPES.RECEIVE_PERFORMANCE_STATS,
                                parent: parent,
                                points: pointsList
                            });

                            endLoadingData(parent);
                        })
                        .catch(rpc.Error, function (error) {
                            
                            var message = error.message;

                            if (error.code === -32602)
                            {
                                if (error.message === "historian unavailable")
                                {
                                    message = "Data could not be fetched for platform " + parent.name + ". The historian agent is unavailable."
                                }
                            }

                            endLoadingData(parent);
                            handle401(error, message, parent.name, "center");
                        });   
            } 
        }

        function endLoadingData(panelItem)
        {
            dispatcher.dispatch({
                type: ACTION_TYPES.END_LOADING_DATA,
                panelItem: panelItem
            });
        }    
    },

    loadFilteredItems: function (filterTerm, filterStatus)
    {
        dispatcher.dispatch({
            type: ACTION_TYPES.FILTER_ITEMS,
            filterTerm: filterTerm,
            filterStatus: filterStatus
        });
    },

    expandAll: function (itemPath) {

        dispatcher.dispatch({
            type: ACTION_TYPES.EXPAND_ALL,
            itemPath: itemPath
        });
    },

    toggleItem: function (itemPath) {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_ITEM,
            itemPath: itemPath
        });
    },

    checkItem: function (itemPath, checked) {

        dispatcher.dispatch({
            type: ACTION_TYPES.CHECK_ITEM,
            itemPath: itemPath,
            checked: checked
        });
    }    
}

function handle401(error, message, highlight, orientation) {
    if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
    else if (message)
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformsPanelActionCreators;
