'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    requestAuthorization: function (username, password) {
        new rpc.Exchange({
            method: 'get_authorization',
            params: {
                username: username,
                password: password,
            },
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AUTHORIZATION,
                    authorization: result,
                });
            })
            .catch(rpc.Error, function (error) {
                if (error.code && error.code === 401) {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
                        error: error,
                    });
                } else {
                    throw error;
                }
            });
    },
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    },
    goToPage: function (page) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_PAGE,
            page: page,
        });
    },
    loadPlatforms: function () {
        var authorization = platformManagerStore.getAuthorization();

        new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: platforms,
                });

                platforms.forEach(function (platform) {
                    new rpc.Exchange({
                        method: 'platforms.uuid.' + platform.uuid + '.list_agents',
                        authorization: authorization,
                    }).promise
                        .then(function (agentsList) {
                            platform.agents = agentsList;

                            dispatcher.dispatch({
                                type: ACTION_TYPES.RECEIVE_PLATFORM,
                                platform: platform,
                            });

                            if (!agentsList.length) { return; }

                            new rpc.Exchange({
                                method: 'platforms.uuid.' + platform.uuid + '.status_agents',
                                authorization: authorization,
                            }).promise
                                .then(function (agentStatuses) {
                                    platform.agents.forEach(function (agent) {
                                        if (!agentStatuses.some(function (status) {
                                            if (agent.uuid === status.uuid) {
                                                agent.actionPending = false;
                                                agent.process_id = status.process_id;
                                                agent.return_code = status.return_code;

                                                return true;
                                            }
                                        })) {
                                            agent.actionPending = false;
                                            agent.process_id = null;
                                            agent.return_code = null;
                                        }

                                    });

                                    dispatcher.dispatch({
                                        type: ACTION_TYPES.RECEIVE_PLATFORM,
                                        platform: platform,
                                    });
                                });
                        });
                });
            })
            .catch(function (error) {
                if (error.code && error.code === 401) {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
                        error: error,
                    });
                } else {
                    throw error;
                }
            });
    },
    startAgent: function (platform, agent) {
        var authorization = platformManagerStore.getAuthorization();

        agent.actionPending = true;

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_PLATFORM,
            platform: platform,
        });

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.start_agent',
            params: [agent.uuid],
            authorization: authorization,
        }).promise
            .then(function (status) {
                agent.actionPending = false;
                agent.process_id = status.process_id;
                agent.return_code = status.return_code;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            });
    },
    stopAgent: function (platform, agent) {
        var authorization = platformManagerStore.getAuthorization();

        agent.actionPending = true;

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_PLATFORM,
            platform: platform,
        });

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.stop_agent',
            params: [agent.uuid],
            authorization: authorization,
        }).promise
            .then(function (status) {
                agent.actionPending = false;
                agent.process_id = status.process_id;
                agent.return_code = status.return_code;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            });
    },
};

window.onhashchange = function () {
    platformManagerActionCreators.goToPage(location.hash.substr(1));
};

module.exports = platformManagerActionCreators;
