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
                platformsPanelActionCreators.loadPanelAgents(parent);
                platformsPanelActionCreators.loadPanelBuildings(parent);
                platformsPanelActionCreators.loadPanelPoints(parent);
                break;
            case "building":
                platformsPanelActionCreators.loadPanelDevices(parent);
                platformsPanelActionCreators.loadPanelPoints(parent);
                break;
            case "device":
                platformsPanelActionCreators.loadPanelPoints(parent);
                platformsPanelActionCreators.loadPanelDevices(parent);
                break;
            case "type":

                for (var i = 0; i < parent.children.length; i++)
                {
                    platformsPanelActionCreators.loadChildren(parent[parent.children[i]].type, parent[parent.children[i]]);
                }

                // for (var i = 0; i < parent.children.length; i++)
                // {
                //     platformsPanelActionCreators.loadChildren(parent.children[i], parent[parent.children[i]]);
                // }
                break;
            default:

        }
    },
    loadPanelPoints: function (parent) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_POINT_STATUSES,
            platform: parent
        });
    },
    loadPanelDevices: function (parent) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
            platform: parent
        });
    },
    loadPanelBuildings: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_BUILDING_STATUSES,
            platform: platform
        });
    },
    loadPanelAgents: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.list_agents',
            authorization: authorization,
        }).promise
            .then(function (agentsList) {
                // platform.agents = agentsList;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                    platform: platform,
                    agents: agentsList
                });

                // if (!agentsList.length) { return; }

                // new rpc.Exchange({
                //     method: 'platforms.uuid.' + platform.uuid + '.status_agents',
                //     authorization: authorization,
                // }).promise
                //     .then(function (agentStatuses) {
                //         platform.agents.forEach(function (agent) {
                //             if (!agentStatuses.some(function (status) {
                //                 if (agent.uuid === status.uuid) {
                //                     agent.actionPending = false;
                //                     agent.process_id = status.process_id;
                //                     agent.return_code = status.return_code;

                //                     return true;
                //                 }
                //             })) {
                //                 agent.actionPending = false;
                //                 agent.process_id = null;
                //                 agent.return_code = null;
                //             }

                //         });

                //         dispatcher.dispatch({
                //             type: ACTION_TYPES.RECEIVE_PLATFORM,
                //             platform: platform,
                //         });
                //     });
            })
            .catch(rpc.Error, handle401);
    },
};


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
