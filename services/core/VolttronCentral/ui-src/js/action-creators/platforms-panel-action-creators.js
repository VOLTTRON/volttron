'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformsPanelActionCreators = {    
    togglePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL,
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

                    for (var key in result)
                    {
                        var device = JSON.parse(JSON.stringify(result[key]));
                        device.path = key;

                        devicesList.push(device);
                    }

                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
                        platform: platform,
                        devices: devicesList
                    });

                    loadPanelAgents(platform);
                    
                })                     
                .catch(rpc.Error, function (error) {
                    endLoadingData(platform);
                    handle401(error, "Unable to load devices for platform " + platform.name + " in side panel: " + error.message);
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
                    handle401(error, "Unable to load agents for platform " + platform.name + " in side panel: " + error.message);
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

                            if (platformPerformance)
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
                            handle401(error, message);
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

function handle401(error, message) {
    if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
    else
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message);
    }
};

module.exports = platformsPanelActionCreators;
