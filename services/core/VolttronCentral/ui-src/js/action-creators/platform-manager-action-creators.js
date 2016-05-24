'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
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

                statusIndicatorActionCreators.openStatusIndicator("error", message);
                handle401(error, error.message);
            })
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

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + name + " was deregistered.");

            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REGISTER_PLATFORM_ERROR,
                    error: error,
                });

                modalActionCreators.closeModal();

                var message = error.message;

                switch (error.code)
                {
                    case -32600:
                        message = "The platform was not registered: Invalid address."
                        break;
                }

                handle401(error, message);
            });
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

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + name + " was registered.");

                platformManagerActionCreators.loadPlatforms();
                platformsPanelActionCreators.loadPanelPlatforms();


            })
            .catch(rpc.Error, function (error) {

                dispatcher.dispatch({
                    type: ACTION_TYPES.REGISTER_PLATFORM_ERROR,
                    error: error,
                });

                modalActionCreators.closeModal();

                var message = error.message;

                switch (error.code)
                {
                    case -32600:
                        message = "The platform was not registered: Invalid address."
                        break;
                    case -32002:
                        message = "The platform was not registered: " + error.message;
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
                platformsPanelActionCreators.loadPanelPlatforms();
            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.DEREGISTER_PLATFORM_ERROR,
                    error: error,
                });
                handle401(error, error.message);
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
