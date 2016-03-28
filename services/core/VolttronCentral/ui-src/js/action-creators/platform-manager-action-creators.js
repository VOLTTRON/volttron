'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var platformActionCreators = require('../action-creators/platform-action-creators');
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
            .catch(rpc.Error, handle401);
    },
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
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: platforms,
                });

                platforms.forEach(function (platform, i) {
                    if (platform.name === null || platform.name === "")
                    {
                        platform.name = "vc" + (i + 1);
                    }
                    
                    // platformActionCreators.loadPlatform(platform);
                    platformActionCreators.initializeAgents(platform);
                });
            })
            .catch(rpc.Error, handle401);
    },
    registerPlatform: function (name, address) {
        var authorization = authorizationStore.getAuthorization();

        dispatcher.dispatch({
            type: ACTION_TYPES.CLOSE_MODAL,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.OPEN_STATUS,
            message: "Registering platform " + name + "...",
            status: "success"
        });

        new rpc.Exchange({
            method: 'register_platform',
            authorization: authorization,
            params: {
                identity: 'platform.agent',
                agentId: name,
                address: address,
            },
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_STATUS,
                });

                platformManagerActionCreators.loadPlatforms();
            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REGISTER_PLATFORM_ERROR,
                    error: error,
                });

                handle401(error);
            });

            // dispatcher.dispatch({
            //     type: ACTION_TYPES.CLOSE_STATUS,
            // });
    },
    registerInstance: function (name, address) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'register_instance',
            authorization: authorization,
            params: {
                display_name: name,
                discovery_address: address,
            },
        }).promise
            .then(function () {
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                platformManagerActionCreators.loadPlatforms();
            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REGISTER_PLATFORM_ERROR,
                    error: error,
                });

                handle401(error);
            });
    },
    deregisterPlatform: function (platform) {
        var authorization = authorizationStore.getAuthorization();

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

                platformManagerActionCreators.loadPlatforms();
            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.DEREGISTER_PLATFORM_ERROR,
                    error: error,
                });

                handle401(error);
            });
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
}

module.exports = platformManagerActionCreators;
