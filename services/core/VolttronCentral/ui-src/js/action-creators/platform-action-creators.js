'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsStore = require('../stores/platforms-store');
var platformChartStore = require('../stores/platform-chart-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

var platformActionCreators = {
    loadPlatform: function (platform) {
        platformActionCreators.loadAgents(platform);
        platformActionCreators.loadCharts(platform);
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
                        handle401(error, "Unable to load agents for platform " + platform.name + ": " + error.message);
                    });
            })            
            .catch(rpc.Error, function (error) {
                handle401(error, "Unable to load agents for platform " + platform.name + ": " + error.message);
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
                handle401(error, "Unable to start agent " + agent.name + ": " + error.message);
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
                handle401(error, "Unable to stop agent " + agent.name + ": " + error.message);
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
                    statusIndicatorActionCreators.openStatusIndicator("error", "Unable to remove agent " + agent.name + ": " + result.error);
                }
                else
                {
                    platformActionCreators.loadPlatform(platform);
                }
            })                      
            .catch(rpc.Error, function (error) {
                handle401(error, "Unable to remove agent " + agent.name + ": " + error.message);
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
                    statusIndicatorActionCreators.openStatusIndicator("error", "Unable to install agents for platform " + platform.name + ": " + errors.join('\n'));
                }

                if (errors.length !== files.length) {
                    platformActionCreators.loadPlatform(platform);
                }
            })                      
            .catch(rpc.Error, function (error) {
                handle401(error, "Unable to install agents for platform " + platform.name + ": " + error.message);
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
                            handle401(error, "Unable to load charts for platform " + platform.name + ": " + error.message);
                        });
                        
                    }
            })
            .catch(rpc.Error, function (error) {
                handle401(error, "Unable to load charts for platform " + platform.name + ": " + error.message);
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
                handle401(error, "Unable to save charts: " + error.message);
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
                handle401(error, "Unable to save chart: " + error.message);
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
                handle401(error, "Unable to delete chart: " + error.message);
            });
    },
};

function handle401(error, message) {
    if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
    else
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message);
    }
}

module.exports = platformActionCreators;
