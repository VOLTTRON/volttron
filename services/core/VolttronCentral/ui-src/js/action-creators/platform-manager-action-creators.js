'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var platformActionCreators = require('../action-creators/platform-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var rpc = require('../lib/rpc');

var initializing = false;

var platformManagerActionCreators = {
    initialize: function () {
        if (!authorizationStore.getAuthorization()) { return; }

        platformManagerActionCreators.loadPlatforms();
    },
    requestAuthorization: function (username, password) {
        new rpc.Exchange({
            method: 'get_authorization',
            params: {
                username: username,
                password: password,
            },
        }, ['password']).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AUTHORIZATION,
                    authorization: result,
                });
            })
            .then(platformManagerActionCreators.initialize)
            .catch(rpc.Error, function (error) {

                var message = error.message;

                if (error.response.status === 401)
                {
                    message = "Invalid username/password specified.";
                }

                statusIndicatorActionCreators.openStatusIndicator("error", message); //This is needed because the 401 status will keep the status 
                handle401(error, error.message);                                    // indicator from being shown. This is the one time we
            })                                                                      // show bad status for not authorized. Other times, we
    },                                                                              // just log them out.
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    },
    loadPlatforms: function () {
        var authorization = authorizationStore.getAuthorization();

        return new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {

                var managerPlatforms = JSON.parse(JSON.stringify(platforms));
                var panelPlatforms = JSON.parse(JSON.stringify(platforms));

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: managerPlatforms,
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
                    platforms: panelPlatforms,
                });

                managerPlatforms.forEach(function (platform, i) {
                    platformActionCreators.loadAgents(platform);

                    platformActionCreators.loadCharts(platform);
                });
            })
            .catch(rpc.Error, function (error) {
                handle401(error, error.message);
            });
    },
    registerPlatform: function (name, address, method) {
        var authorization = authorizationStore.getAuthorization();

        var rpcMethod;
        var params = {};

        switch (method)
        {
            case "discovery":
                rpcMethod = 'register_instance';
                params = {
                    display_name: name,
                    discovery_address: address
                }
                break;
            case "advanced":
                rpcMethod = 'register_platform';
                params = {
                    identity: 'platform.agent',
                    agentId: name,
                    address: address
                }
                break;
        }

        new rpc.Exchange({
            method: rpcMethod,
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + name + " was registered.");
        
                platformManagerActionCreators.loadPlatforms();                

            })
            .catch(rpc.Error, function (error) {
                
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                var message = error.message;

                switch (error.code)
                {
                    case -32600:
                        message = "Platform " + name + " was not registered: Invalid address."
                        break;
                    case -32002:
                        message = "Platform " + name + " was not registered: " + error.message;
                        break;
                    case -32000:
                        message = "Platform " + name + " was not registered: An unknown error occurred.";
                        break;
                }

                handle401(error, message);
            });
    },
    deregisterPlatform: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        var platformName = platform.name;

        new rpc.Exchange({
            method: 'unregister_platform',
            authorization: authorization,
            params: {
                platform_uuid: platform.uuid
            },
        }).promise
            .then(function (platform) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + platformName + " was deregistered.");

                platformManagerActionCreators.loadPlatforms();
            })
            .catch(rpc.Error, function (error) { 
                var message = "Platform " + platformName + " was not deregistered: " + error.message;

                handle401(error, message);
            });
    },
};

function handle401(error, message) {
    if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformManagerActionCreators.clearAuthorization();
    }
    else
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message);
    }
}

module.exports = platformManagerActionCreators;
