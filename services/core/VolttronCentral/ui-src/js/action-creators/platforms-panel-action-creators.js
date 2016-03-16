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

    closePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.CLOSE_PLATFORMS_PANEL,
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

                platforms.forEach(function (platform, i) {
                    if (platform.name === null || platform.name === "")
                    {
                        platform.name = "vc" + (i + 1);
                    }
                });

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
                // loadPanelAgents(parent);
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
        //     var authorization = authorizationStore.getAuthorization();

        //     new rpc.Exchange({
        //         method: 'platforms.uuid.' + platform.uuid + '.list_agents',
        //         authorization: authorization,
        //     }).promise
        //         .then(function (agentsList) {
                    
        //             dispatcher.dispatch({
        //                 type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
        //                 platform: platform,
        //                 agents: agentsList
        //             });

                    
        //         })
        //         .catch(rpc.Error, handle401);    
        // }
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                platform: platform
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
            if (panelItem.uuid === "5461fedc-65ba-43fe-21dc-098765bafedl")
            {
                panelItem.data = [['2016-02-19T01:00:31.630626',31.4],['2016-02-19T01:00:16.632151',23],['2016-02-19T01:00:01.627188',16.5],['2016-02-19T00:59:46.641500',42.8],['2016-02-19T00:59:31.643573',21.2],['2016-02-19T00:59:16.643254',9.3],['2016-02-19T00:59:01.639104',8.5],['2016-02-19T00:58:46.638238',16],['2016-02-19T00:58:31.633733',12.4],['2016-02-19T00:58:16.632418',23],['2016-02-19T00:58:01.630463',16.7],['2016-02-19T00:57:46.648439',9.1],['2016-02-19T00:57:31.640824',10.5],['2016-02-19T00:57:16.636578',8.2],['2016-02-19T00:57:01.644842',2.2],['2016-02-19T00:56:46.635059',2.5],['2016-02-19T00:56:31.639332',2.4],['2016-02-19T00:56:16.647604',2.3],['2016-02-19T00:56:01.643571',11.2],['2016-02-19T00:55:46.644522',9.8]];
                panelItem.data.forEach(function (datum) {
                    datum.name = panelItem.name;
                    datum.parent = panelItem.parentPath;
                    datum.uuid = panelItem.uuid;
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });
            }
            else if (panelItem.uuid === "5461fedc-65ba-43fe-21dc-111765bafedl")
            {
                panelItem.data = [['2016-02-19T01:01:46.625663',73.6],['2016-02-19T01:01:31.633847',71],['2016-02-19T01:01:16.627160',69.4],['2016-02-19T01:01:01.639623',60],['2016-02-19T01:00:46.626307',67],['2016-02-19T01:00:31.630768',68.6],['2016-02-19T01:00:16.632203',77],['2016-02-19T01:00:01.627241',83.5],['2016-02-19T00:59:46.641688',57.2],['2016-02-19T00:59:31.643709',78.7],['2016-02-19T00:59:16.643448',90.7],['2016-02-19T00:59:01.640538',91.5],['2016-02-19T00:58:46.638353',84],['2016-02-19T00:58:31.633809',87.6],['2016-02-19T00:58:16.632515',77],['2016-02-19T00:58:01.630531',83.3],['2016-02-19T00:57:46.648567',90.9],['2016-02-19T00:57:31.640947',89.5],['2016-02-19T00:57:16.636686',91.8],['2016-02-19T00:57:01.645023',97.7]];
                panelItem.data.forEach(function (datum) {
                    datum.name = panelItem.name;
                    datum.parent = panelItem.parentPath;
                    datum.uuid = panelItem.uuid;
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });
            }
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
