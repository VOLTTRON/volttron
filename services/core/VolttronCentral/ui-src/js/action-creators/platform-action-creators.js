'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformActionCreators = {
    loadPlatform: function (platform) {
        platformActionCreators.loadAgents(platform);
        platformActionCreators.loadCharts(platform);
    },
    clearPlatformError: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_PLATFORM_ERROR,
            platform: platform,
        });
    },
    loadAgents: function (platform) {
        var authorization = authorizationStore.getAuthorization();

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
            })
            .catch(rpc.Error, handle401);
    },
    initializeAgents: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        if (platform.agents.length > 0)
        {
            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.status_agents',
                authorization: authorization,
            }).promise
                .then(function (agentStatuses) {
                    platform.agents.forEach(function (agent) {
                        if (!agentStatuses.some(function (status) {
                            if (agent.uuid === status.uuid) {
                                agent.actionPending = false;
                                console.log("PIDs match: " + (agent.process_id === status.process_id));
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
        }
    },
    startAgent: function (platform, agent) {
        var authorization = authorizationStore.getAuthorization();

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
                agent.process_id = status.process_id;
                agent.return_code = status.return_code;
            })
            .catch(rpc.Error, handle401)
            .finally(function () {
                agent.actionPending = false;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            });
    },
    stopAgent: function (platform, agent) {
        var authorization = authorizationStore.getAuthorization();

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
                agent.process_id = status.process_id;
                agent.return_code = status.return_code;
            })
            .catch(rpc.Error, handle401)
            .finally(function () {
                agent.actionPending = false;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            });
    },
    removeAgent: function (platform, agent) {
        var authorization = authorizationStore.getAuthorization();

        agent.actionPending = true;
        

        dispatcher.dispatch({
            type: ACTION_TYPES.CLOSE_MODAL,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_PLATFORM,
            platform: platform,
        });

        var methodStr = 'platforms.uuid.' + platform.uuid + '.remove_agent';
        var agentId = [agent.uuid];
        
        new rpc.Exchange({
            method: methodStr,
            params: agentId,
            authorization: authorization,
        }).promise
            .then(function (result) {
                
                if (result.error) {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_PLATFORM_ERROR,
                        platform: platform,
                        error: result.error,
                    });
                }
                else
                {
                    platformActionCreators.loadPlatform(platform);
                }
            })
            .catch(rpc.Error, handle401);
    },
    installAgents: function (platform, files) {
        platformActionCreators.clearPlatformError(platform);

        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.install',
            params: { files: files },
            authorization: authorization,
        }).promise
            .then(function (results) {
                var errors = [];

                results.forEach(function (result) {
                    if (result.error) {
                        errors.push(result.error);
                    }
                });

                if (errors.length) {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_PLATFORM_ERROR,
                        platform: platform,
                        error: errors.join('\n'),
                    });
                }

                if (errors.length !== files.length) {
                    platformActionCreators.loadPlatform(platform);
                }
            })
            .catch(rpc.Error, handle401);
    },
    loadCharts: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.get_setting',
            params: { key: 'charts' },
            authorization: authorization,
        }).promise
            .then(function (charts) {
                if (charts && charts.length) {
                    platform.charts = charts;
                } else {
                    // Provide default set of charts if none are configured
                    platform.charts = [
//                        {
//                          "topic": "datalogger/log/platform/status/cpu/percent",
//                          "refreshInterval": 15000,
//                          "type": "line",
//                          "min": 0,
//                          "max": 100
//                        },
//                        {
//                          "topic": "datalogger/log/platform/status/cpu/times_percent/idle",
//                          "refreshInterval": 15000,
//                          "type": "line",
//                          "min": 0,
//                          "max": 100
//                        },
//                        {
//                          "topic": "datalogger/log/platform/status/cpu/times_percent/nice",
//                          "refreshInterval": 15000,
//                          "type": "line",
//                          "min": 0,
//                          "max": 100
//                        },
//                        {
//                          "topic": "datalogger/log/platform/status/cpu/times_percent/system",
//                          "refreshInterval": 15000,
//                          "type": "line",
//                          "min": 0,
//                          "max": 100
//                        },
//                        {
//                          "topic": "datalogger/log/platform/status/cpu/times_percent/user",
//                          "refreshInterval": 15000,
//                          "type": "line",
//                          "min": 0,
//                          "max": 100
//                        },
                    ];
                }

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            })
            .catch(rpc.Error, handle401);
    },
    getTopicData: function (platform, topic) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.historian.query',
            params: {
                topic: topic,
                count: 20,
                order: 'LAST_TO_FIRST',
            },
            authorization: authorization,
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM_TOPIC_DATA,
                    platform: platform,
                    topic: topic,
                    data: result.values,
                });
            })
            .catch(rpc.Error, handle401);
    },
    saveChart: function (platform, oldChart, newChart) {
        var authorization = authorizationStore.getAuthorization();
        var newCharts;

        if (!oldChart) {
            newCharts = platform.charts.concat([newChart]);
        } else {
            newCharts = platform.charts.map(function (chart) {
                if (chart === oldChart) {
                    return newChart;
                }

                return chart;
            });
        }

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.set_setting',
            params: { key: 'charts', value: newCharts },
            authorization: authorization,
        }).promise
            .then(function () {
                platform.charts = newCharts;

                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            });
    },
    deleteChart: function (platform, chartToDelete) {
        var authorization = authorizationStore.getAuthorization();

        var newCharts = platform.charts.filter(function (chart) {
            return (chart !== chartToDelete);
        });

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.set_setting',
            params: { key: 'charts', value: newCharts },
            authorization: authorization,
        }).promise
            .then(function () {
                platform.charts = newCharts;

                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            });
    },
};

function handle401(error) {
    if (error.code && error.code === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformActionCreators.clearAuthorization();
    }
}

module.exports = platformActionCreators;
