'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsStore = require('../stores/platforms-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
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
                        handle401(error);
                    });
            })            
            .catch(rpc.Error, function (error) {
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
                handle401(error, "Unable to start agent " + agent.name + ": " + error.message, agent.name);
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
                handle401(error, "Unable to stop agent " + agent.name + ": " + error.message, agent.name);
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
                
                if (result.error) 
                {
                    statusIndicatorActionCreators.openStatusIndicator("error", "Unable to remove agent " + agent.name + ": " + result.error, agent.name);
                }
                else
                {
                    platformActionCreators.loadPlatform(platform);
                }
            })                      
            .catch(rpc.Error, function (error) {
                handle401(error, "Unable to remove agent " + agent.name + ": " + error.message, agent.name);
            });
    },
    installAgents: function (platform, files) {

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

                if (errors.length) 
                {
                    statusIndicatorActionCreators.openStatusIndicator("error", "Unable to install agents for platform " + platform.name + ": " + errors.join('\n'), platform.name);
                }

                if (errors.length !== files.length) {
                    platformActionCreators.loadPlatform(platform);
                }
            })                      
            .catch(rpc.Error, function (error) {
                handle401(error, "Unable to install agents for platform " + platform.name + ": " + error.message, platform.name);
            });
    },    
    handleChartsForUser: function (callback) {
        var authorization = authorizationStore.getAuthorization();
        var user = authorizationStore.getUsername();

        if (user)
        {
            callback(authorization, user);
        }
    },
    loadChartTopics: function () {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'historian.get_topic_list',
            authorization: authorization,
        }).promise
            .then(function (topics) {

                var filteredTopics = [];

                topics.forEach(function (topic, index) {

                    if (topic.indexOf("datalogger/platform/status") < 0) // ignore -- they're local platform topics that are in
                    {                                                      // the list twice, also at datalogger/platform/<uuid>
                        var item = {};
                        var topicParts = topic.split("/");

                        if (topicParts.length > 2)
                        {
                            var name;
                            var parentPath;
                            var label;

                            if (topic.indexOf("datalogger/platforms") > -1) // if a platform instance
                            {
                                var platformUuid = topicParts[2];
                                var topicPlatform = platformsStore.getPlatform(platformUuid);
                                parentPath = (topicPlatform ? topicPlatform.name : "Unknown Platform");
                                label = topicParts[topicParts.length - 2] + "/" + topicParts[topicParts.length - 1] + " (" + parentPath + ")";
                                name = topicParts[topicParts.length - 2] + " / " + topicParts[topicParts.length - 1]; // the name is the
                                                                                                                    // last two path parts
                            }                                                                                      // ex.: times_percent / idle
                            else // else a device point
                            {
                                parentPath = topicParts[0];

                                for (var i = 1; i < topicParts.length - 1; i++)
                                {
                                    parentPath = parentPath + " > " + topicParts[i];
                                }

                                label = topicParts[topicParts.length - 1] + " (" + parentPath + ")";
                                name = topicParts[topicParts.length - 1]; // the name is the column name

                                item.path = platformsPanelItemsStore.findTopicInTree(topic);
                            }

                            item.value = topic;
                            item.label = label;
                            item.key = index;
                            item.name = name;
                            item.parentPath = parentPath;

                            filteredTopics.push(item);
                        }
                    }
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_CHART_TOPICS,
                    topics: filteredTopics
                });
            })
            .catch(rpc.Error, function (error) {

                var message = error.message;

                if (error.code === -32602)
                {
                    if (error.message === "historian unavailable")
                    {
                        message = "Charts can't be added. The VOLTTRON Central historian is unavailable."
                    }
                }
                else
                {
                    message = "Chart topics can't be loaded. " + error.message;
                }

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_CHART_TOPICS,
                    topics: []
                });

                statusIndicatorActionCreators.openStatusIndicator("error", message);
                handle401(error);
            });
    },
    loadCharts: function (platform) {
        
        var doLoadCharts = function (authorization, user)
        {
            new rpc.Exchange({
                method: 'get_setting_keys',
                authorization: authorization,
            }).promise
                .then(function (valid_keys) {
                
                    if (valid_keys.indexOf(user) > -1)
                    {                    
                        new rpc.Exchange({
                            method: 'get_setting',
                            params: { key: user },
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
                                handle401(error);
                            });                            
                        }
                })
                .catch(rpc.Error, function (error) {
                    handle401(error);
                });
        }.bind(platform);

        platformActionCreators.handleChartsForUser(doLoadCharts);
    },
    saveCharts: function (chartsToSave) {
        
        var doSaveCharts = function (authorization, user) { 
            var savedCharts = (this ? this : platformChartStore.getPinnedCharts());

            new rpc.Exchange({
                method: 'set_setting',
                params: { key: user, value: savedCharts },
                authorization: authorization,
            }).promise
                .then(function () {

                })
                .catch(rpc.Error, function (error) {
                    handle401(error, "Unable to save charts: " + error.message);
                });
        }.bind(chartsToSave);

        platformActionCreators.handleChartsForUser(doSaveCharts);
    },
    saveChart: function (newChart) {
        
        var doSaveChart = function (authorization, user) { 
            var newCharts = [this];

            new rpc.Exchange({
                method: 'set_setting',
                params: { key: user, value: newCharts },
                authorization: authorization,
            }).promise
                .then(function () {

                })
                .catch(rpc.Error, function (error) {
                    handle401(error, "Unable to save chart: " + error.message);
                });
        }.bind(newChart);

        platformActionCreators.handleChartsForUser(doSaveChart);
    },
    deleteChart: function (chartToDelete) {
        
        var doDeleteChart = function (authorization, user) {

            var savedCharts = platformChartStore.getPinnedCharts();

            var newCharts = savedCharts.filter(function (chart) {
                return (chart.chartKey !== this);
            });

            new rpc.Exchange({
                method: 'set_setting',
                params: { key: user, value: newCharts },
                authorization: authorization,
            }).promise
                .then(function () {

                })
                .catch(rpc.Error, function (error) {
                    handle401(error, "Unable to delete chart: " + error.message);
                });
        }.find(chartToDelete);

        platformActionCreators.handleChartsForUser(doDeleteChart);
    },
    removeSavedPlatformCharts: function (platform) {

        var authorization = authorizationStore.getAuthorization();

        // first get all the keys (i.e., users) that charts are saved under
        new rpc.Exchange({
            method: 'get_setting_keys',
            authorization: authorization,
        }).promise
            .then(function (valid_keys) {
            
                // then get the charts for each user
                valid_keys.forEach(function (key) {

                    new rpc.Exchange({
                        method: 'get_setting',
                        params: { key: key },
                        authorization: authorization,
                    }).promise
                        .then(function (charts) {

                            // for each saved chart, keep the chart if it has any series that don't belong
                            // to the deregistered platform
                            var filteredCharts = charts.filter(function (chart) {

                                var keeper = true;
                                var seriesToRemove;

                                var filteredSeries = chart.series.filter(function (series) {
                                    var seriesToKeep = (series.path.indexOf(this.uuid) < 0);

                                    // also have to remove any data associated with the removed series
                                    if (!seriesToKeep)
                                    {
                                        var filteredData = chart.data.filter(function (datum) {
                                            return (datum.uuid !== this.uuid);
                                        }, series);

                                        chart.data = filteredData;
                                    }

                                    return seriesToKeep;
                                }, this);

                                // keep the chart if there are any series that don't belong to the deregistered platform,
                                // but leave out the series that do belong to the deregistered platform
                                if (filteredSeries.length !== 0)
                                {
                                    chart.series = filteredSeries;
                                }
                                else
                                {
                                    keeper = false;
                                }

                                return keeper;
                            }, platform);
                        
                            // now save the remaining charts. Even if there are none, do the save, because that's what deletes 
                            // the rejects.
                            new rpc.Exchange({
                                method: 'set_setting',
                                params: { key: key, value: filteredCharts },
                                authorization: authorization,
                            }).promise
                                .then(function () {
                                    
                                })
                                .catch(rpc.Error, function (error) {
                                    handle401(error, "Error removing deregistered platform's charts from saved charts (e0): " + error.message);
                                });
                        })
                        .catch(rpc.Error, function (error) {
                            handle401(error, "Error removing deregistered platform's charts from saved charts (e1): " + error.message);
                        });
                        
                    
                });
            })
            .catch(rpc.Error, function (error) {
                handle401(error, "Error removing deregistered platform's charts from saved charts (e2): " + error.message);
            });
    },

};

function handle401(error, message, highlight, orientation) {
    if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
    else if (message)
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformActionCreators;
