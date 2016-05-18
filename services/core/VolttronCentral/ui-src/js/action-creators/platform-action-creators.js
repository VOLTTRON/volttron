'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsStore = require('../stores/platforms-store');
var platformChartStore = require('../stores/platform-chart-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');

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
                    })            
                    .catch(rpc.Error, function (error) {

                        statusIndicatorActionCreators.openStatusIndicator("error", "Error loading agents: " + error.message);

                        handle401(error);
                    });
            })            
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error loading agents: " + error.message);

                handle401(error);
            });
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
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error starting agent: " + error.message);

                handle401(error);
            })
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
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error stopping agent: " + error.message);

                handle401(error);
            })
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
                    // dispatcher.dispatch({
                    //     type: ACTION_TYPES.RECEIVE_PLATFORM_ERROR,
                    //     platform: platform,
                    //     error: result.error,
                    // });
                    statusIndicatorActionCreators.openStatusIndicator("error", "Error removing agent: " + result.error);
                }
                else
                {
                    platformActionCreators.loadPlatform(platform);
                }
            })                      
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error removing agent: " + error.message);

                handle401(error);
            });
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
                    // dispatcher.dispatch({
                    //     type: ACTION_TYPES.RECEIVE_PLATFORM_ERROR,
                    //     platform: platform,
                    //     error: errors.join('\n'),
                    // });
                    statusIndicatorActionCreators.openStatusIndicator("error", "Error installing agents: " + errors.join('\n'));
                }

                if (errors.length !== files.length) {
                    platformActionCreators.loadPlatform(platform);
                }
            })                      
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error installing agents: " + error.message);

                handle401(error);
            });
    },    
    loadCharts: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'get_setting_keys',
            params: { key: 'charts' },
            authorization: authorization,
        }).promise
            .then(function (valid_keys) {
            
                if (valid_keys.indexOf("charts") > -1)
                {                    
                    new rpc.Exchange({
                        method: 'get_setting',
                        params: { key: 'charts' },
                        authorization: authorization,
                    }).promise
                        .then(function (charts) {
                        
                            var notifyRouter = false;

                            dispatcher.dispatch({
                                type: ACTION_TYPES.LOAD_CHARTS,
                                charts: charts,
                            });
                        })
                        .catch(rpc.Error, function (error) {

                            statusIndicatorActionCreators.openStatusIndicator("error", "Error loading charts: " + error.message);

                            handle401(error);
                        });
                        
                    }
            })
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error loading charts: " + error.message);

                handle401(error);
            });


        
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
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error getting topic: " + error.message);

                handle401(error);
            });
    },
    saveCharts: function (chartsToSave) {
        var authorization = authorizationStore.getAuthorization();

        var savedCharts = (chartsToSave ? chartsToSave : platformChartStore.getPinnedCharts());

        new rpc.Exchange({
            method: 'set_setting',
            params: { key: 'charts', value: savedCharts },
            authorization: authorization,
        }).promise
            .then(function () {

            })
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error saving charts: " + error.message);

                handle401(error);
            });
    },
    saveChart: function (newChart) {
        var authorization = authorizationStore.getAuthorization();

        var newCharts = [newChart];

        new rpc.Exchange({
            method: 'set_setting',
            params: { key: 'charts', value: newCharts },
            authorization: authorization,
        }).promise
            .then(function () {

            })
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error saving chart: " + error.message);

                handle401(error);
            });
    },
    deleteChart: function (chartToDelete) {
        var authorization = authorizationStore.getAuthorization();

        var savedCharts = platformChartStore.getPinnedCharts();

        var newCharts = savedCharts.filter(function (chart) {

            return (chart.chartKey !== chartToDelete);
        });

        new rpc.Exchange({
            method: 'set_setting',
            params: { key: 'charts', value: newCharts },
            authorization: authorization,
        }).promise
            .then(function () {

            })
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", "Error deleting chart: " + error.message);

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

        platformActionCreators.clearAuthorization();
    }
}

module.exports = platformActionCreators;
