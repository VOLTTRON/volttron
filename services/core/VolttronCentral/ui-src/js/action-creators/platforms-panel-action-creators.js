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
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_POINT_STATUSES,
                platform: parent
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

        dispatcher.dispatch({
            type: ACTION_TYPES.ADD_TO_CHART,
            panelItem: panelItem
        });  

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
