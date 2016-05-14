'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsStore = require('../stores/platforms-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

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
    loadChartTopics: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'historian.get_topic_list',
            authorization: authorization,
        }).promise
            .then(function (topics) {
                
                // var topicsList = topics.map(function (topic, index) {
                //     return { path: topic, label: getLabelFromTopic(topic), key: index};
                // });

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
                            // var name;

                            if (topic.indexOf("datalogger/platform") > -1) // if a platform instance
                            {
                                var platformUuid = topicParts[2];
                                var platform = platformsStore.getPlatform(platformUuid);
                                parentPath = (platform ? platform.name : "Unknown Platform");
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
                            }
                            
                            item.path = topic;
                            item.label = label;
                            item.key = index;
                            item.name = name;
                            // item.uuid = this.state.selectedTopic;
                            // item.topic = this.state.selectedTopic;
                            // item.pinned = (this.state.pin ? true : false);
                            item.parentPath = parentPath;
                            // item.parentUuid = this.props.platform.uuid;

                            filteredTopics.push(item);
                        }
                    }                
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_CHART_TOPICS,
                    platform: platform,
                    topics: filteredTopics
                });
            })
            .catch(rpc.Error, function (error) {
                
                var message = error.message;

                if (error.code === -32602)
                {
                    if (error.message === "historian unavailable")
                    {
                        message = "Charts can't be added. The historian agent is unavailable."
                    }
                }

                statusIndicatorActionCreators.openStatusIndicator("error", message);
                handle401(error);
            });     
    },
    loadCharts: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.get_setting',
            params: { key: 'charts' },
            authorization: authorization,
        }).promise
            .then(function (charts) {

                var notifyRouter = false;

                charts.forEach(function (chart) {
                    platformChartActionCreators.addToChart(chart, notifyRouter);
                });

                // if (charts && charts.length) {
                //     platform.charts = charts;
                // } else {
                //     platform.charts = [];
                // }

                // dispatcher.dispatch({
                //     type: ACTION_TYPES.RECEIVE_PLATFORM,
                //     platform: platform,
                // });



                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    chart: charts,
                });
            })
            .catch(rpc.Error, function (error) {

                statusIndicatorActionCreators.openStatusIndicator("error", error.message + ": Unable to load charts.");

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
            .catch(rpc.Error, handle401);
    },
    saveChart: function (platform, oldChart, newChart) {
        var authorization = authorizationStore.getAuthorization();
        var newCharts;

        if (!oldChart) {
            // newCharts = platform.charts.concat([newChart]);
            newCharts = [newChart];
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

                // platform.charts = newCharts;

                // dispatcher.dispatch({
                //     type: ACTION_TYPES.CLOSE_MODAL,
                // });

                // dispatcher.dispatch({
                //     type: ACTION_TYPES.RECEIVE_PLATFORM,
                //     platform: platform,
                // });
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
