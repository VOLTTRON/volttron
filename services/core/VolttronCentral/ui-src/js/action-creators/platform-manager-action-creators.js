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

        var reload = false;
        platformManagerActionCreators.loadPlatforms(reload);
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
                    name: username
                });
            })
            .then(platformManagerActionCreators.initialize)
            .catch(rpc.Error, function (error) {

                var message = error.message;

                if (error.response.status === 401)
                {
                    message = "Invalid username/password specified.";
                }

                statusIndicatorActionCreators.openStatusIndicator("error", message, null, "center"); //This is needed because the 401 status  
                handle401(error, error.message);                                    // will keep the statusindicator from being shown. This is 
            })                                                                      // the one time we show bad status for not authorized. Other 
    },                                                                              // times, we just log them out.
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    },
    loadPlatforms: function (reload) {
        var authorization = authorizationStore.getAuthorization();

        return new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {

                platforms = platforms.map(function (platform, index) {

                    if (platform.name === null || platform.name === "" || typeof platform.name === undefined)
                    {
                        platform.name = "Unnamed Platform " + (index + 1);
                    }

                    return platform;
                });

                var managerPlatforms = JSON.parse(JSON.stringify(platforms));
                var panelPlatforms = JSON.parse(JSON.stringify(platforms));

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: managerPlatforms,
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
                    platforms: panelPlatforms,
                    reload: reload
                });

                managerPlatforms.forEach(function (platform, i) {
                    platformActionCreators.loadAgents(platform);

                    if (!reload)
                    {
                        platformActionCreators.loadCharts(platform);
                    }
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

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + name + " was registered.", name, "center");        

                var reload = true;
                platformManagerActionCreators.loadPlatforms(reload);

            })
            .catch(rpc.Error, function (error) {
                
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                var message = "Platform " + name + " was not registered: " + error.message;
                var orientation;

                switch (error.code)
                {
                    case -32600:
                        message = "Platform " + name + " was not registered: Invalid address.";
                        orientation = "center"
                        break;
                    case -32000:
                        message = "Platform " + name + " was not registered: An unknown error occurred.";
                        orientation = "center"
                        break;
                }

                handle401(error, message, name, orientation);
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
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                platformActionCreators.removeSavedPlatformCharts(platform);

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + platformName + " was deregistered.", platformName, "center");
                dispatcher.dispatch({
                    type: ACTION_TYPES.REMOVE_PLATFORM_CHARTS,
                    platform: platform
                });

                var reload = true;
                platformManagerActionCreators.loadPlatforms(reload);
            })
            .catch(rpc.Error, function (error) { 
                var message = "Platform " + platformName + " was not deregistered: " + error.message;

                handle401(error, message, platformName);
            });
    },
};

function handle401(error, message, highlight, orientation) {
   if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformManagerActionCreators.clearAuthorization();
    }
    else if (message)
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformManagerActionCreators;
