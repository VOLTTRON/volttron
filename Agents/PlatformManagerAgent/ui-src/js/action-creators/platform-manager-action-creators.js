'use strict';

var Promise = require('bluebird');

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    requestAuthorization: function (username, password) {
        new rpc.Request({
            method: 'getAuthorization',
            params: {
                username: username,
                password: password,
            },
        })
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AUTHORIZATION,
                    authorization: result,
                });
            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
                    error: error,
                });
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

        new rpc.Request({
            method: 'listPlatforms',
            authorization: authorization,
        })
            .then(function (platforms) {
                return Promise.all(platforms.map(function (platform) {
                    return new rpc.Request({
                        method: 'platforms.uuid.' + platform.uuid + '.listAgents',
                        authorization: authorization,
                    })
                        .then(function (agents) {
                            return Promise.all(agents.map(function (agent) {
                                return new rpc.Request({
                                    method: 'platforms.uuid.' + platform.uuid + '.agents.uuid.' + agent.uuid + '.listMethods',
                                    authorization: authorization,
                                })
                                    .then(function (methods) {
                                        agent.methods = methods;
                                        return agent;
                                    });
                                }));
                        })
                        .then(function (agents) {
                            platform.agents = agents;
                            return platform;
                        });
                }));
            })
            .then(function (platforms) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: platforms,
                });
            });
    },
};

module.exports = platformManagerActionCreators;
