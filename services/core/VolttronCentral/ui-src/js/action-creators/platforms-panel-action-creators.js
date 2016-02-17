'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformsPanelActionCreators = {    
    togglePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL,
        });
    },

    loadPanelPlatforms: function () {
        if (!authorizationStore.getAuthorization()) { return; }

        

        var authorization = authorizationStore.getAuthorization();

        return new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
                    platforms: platforms,
                });

                // platforms.forEach(function (platform) {
                //     platformActionCreators.loadPlatform(platform);
                // });
            })
            .catch(rpc.Error, handle401);
        
    },

    loadChildren: function(type, parent)
    {
        switch (type)
        {
            case "platform":
                loadPanelAgents(parent);
                loadPanelBuildings(parent);
                loadPanelPoints(parent);
                break;
            case "building":
                loadPanelDevices(parent);
                loadPanelPoints(parent);
                break;
            case "device":
                loadPanelPoints(parent);
                loadPanelDevices(parent);
                break;
            // case "type":

            //     for (var i = 0; i < parent.children.length; i++)
            //     {
            //         platformsPanelActionCreators.loadChildren(parent[parent.children[i]].type, parent[parent.children[i]]);
            //     }
                
            //     break;
            default:

                loadPanelChildren(parent);

                break;

        }


        function loadPanelChildren(parent) {
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PANEL_CHILDREN,
                platform: parent
            });    
        }

        function loadPanelPoints(parent) {

            var pointsList = [];

            if (parent.type === "platform")
            {
                pointsList = [

                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/guest_nice",
                        "name": "times_percent / guest_nice"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/system",
                        "name": "times_percent / system"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/percent",
                        "name": "cpu / percent"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/irq",
                        "name": "times_percent / irq"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/steal",
                        "name": "times_percent / steal"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/user",
                        "name": "times_percent / user"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/nice",
                        "name": "times_percent / nice"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/iowait",
                        "name": "times_percent / iowait"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/idle",
                        "name": "times_percent / idle"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/guest",
                        "name": "times_percent / guest"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/softirq",
                        "name": "times_percent / softirq"
                    }
                ]
            }

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_POINT_STATUSES,
                parent: parent,
                points: pointsList
            });    
        }

        function loadPanelDevices(parent) {
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
                platform: parent
            });    
        }

        function loadPanelBuildings(parent) {
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_BUILDING_STATUSES,
                platform: parent
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

                    
                })
                .catch(rpc.Error, handle401);    
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

    addToChart: function(panelItem) {

        if (panelItem.parentType === "platform")
        {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + panelItem.parentUuid + '.historian.query',
                params: {
                    topic: panelItem.topic,
                    count: 20,
                    order: 'LAST_TO_FIRST',
                },
                authorization: authorization,
            }).promise
                .then(function (result) {
                    panelItem.data = result.values;

                    panelItem.data.forEach(function (datum) {
                        datum.name = panelItem.name;
                        datum.parent = panelItem.parentPath;
                        datum.uuid = panelItem.uuid;
                    });
                    dispatcher.dispatch({
                        type: ACTION_TYPES.ADD_TO_CHART,
                        panelItem: panelItem
                    });
                })
                .catch(rpc.Error, handle401);
        }  
        else
        {
            dispatcher.dispatch({
                type: ACTION_TYPES.ADD_TO_CHART,
                panelItem: panelItem
            });
        }

    },

    removeFromChart: function(panelItem) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_CHART,
            panelItem: panelItem
        });  

    }
}




function handle401(error) {
    if (error.code && error.code === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformManagerActionCreators.clearAuthorization();
    }
};

module.exports = platformsPanelActionCreators;
