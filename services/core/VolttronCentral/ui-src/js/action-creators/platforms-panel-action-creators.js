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
            case "type":

                for (var i = 0; i < parent.children.length; i++)
                {
                    platformsPanelActionCreators.loadChildren(parent[parent.children[i]].type, parent[parent.children[i]]);
                }
                
                break;
            default:

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

    addToGraph: function(panelItem) {

        dispatcher.dispatch({
            type: ACTION_TYPES.ADD_TO_GRAPH,
            panelItem: panelItem
        });  

    },

    removeFromGraph: function(panelItem) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_GRAPH,
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
