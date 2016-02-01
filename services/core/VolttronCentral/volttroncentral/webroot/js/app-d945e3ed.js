(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var authorizationStore = require('./stores/authorization-store');
var Dashboard = require('./components/dashboard');
var LoginForm = require('./components/login-form');
var PageNotFound = require('./components/page-not-found');
var Platform = require('./components/platform');
var PlatformManager = require('./components/platform-manager');
var Platforms = require('./components/platforms');
var Graphs = require('./components/graphs');

var _afterLoginPath = '/dashboard';

function checkAuth(Component) {
    return React.createClass({
        statics: {
            willTransitionTo: function (transition) {
                if (transition.path !== '/login') {
                    _afterLoginPath = transition.path;

                    if (!authorizationStore.getAuthorization()) {
                        transition.redirect('/login');
                    }
                } else if (transition.path === '/login' && authorizationStore.getAuthorization()) {
                    transition.redirect(_afterLoginPath);
                }
            },
        },
        render: function () {
            return (
                React.createElement(Component, React.__spread({},  this.props))
            );
        },
    });
}

var AfterLogin = React.createClass({displayName: "AfterLogin",
    statics: {
        willTransitionTo: function (transition) {
            transition.redirect(_afterLoginPath);
        },
    },
    render: function () {},
});

var routes = (
    React.createElement(Router.Route, {path: "/", handler: PlatformManager}, 
        React.createElement(Router.Route, {name: "login", path: "login", handler: checkAuth(LoginForm)}), 
        React.createElement(Router.Route, {name: "dashboard", path: "dashboard", handler: checkAuth(Dashboard)}), 
        React.createElement(Router.Route, {name: "platforms", path: "platforms", handler: checkAuth(Platforms)}), 
        React.createElement(Router.Route, {name: "platform", path: "platforms/:uuid", handler: checkAuth(Platform)}), 
        React.createElement(Router.Route, {name: "graphs", path: "graphs", handler: checkAuth(Graphs)}), 
        React.createElement(Router.NotFoundRoute, {handler: checkAuth(PageNotFound)}), 
        React.createElement(Router.DefaultRoute, {handler: AfterLogin})
    )
);

var router = Router.create(routes);

router.run(function (Handler) {
    React.render(
        React.createElement(Handler, null),
        document.getElementById('app')
    );

    authorizationStore.addChangeListener(function () {
        if (authorizationStore.getAuthorization() && router.isActive('/login')) {
            router.replaceWith(_afterLoginPath);
        } else if (!authorizationStore.getAuthorization() && !router.isActive('/login')) {
            router.replaceWith('/login');
        }
    });
});


},{"./components/dashboard":13,"./components/graphs":18,"./components/login-form":20,"./components/page-not-found":23,"./components/platform":25,"./components/platform-manager":24,"./components/platforms":28,"./stores/authorization-store":40,"react":undefined,"react-router":undefined}],2:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var RpcExchange = require('../lib/rpc/exchange');

var consoleActionCreators = {
    toggleConsole: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_CONSOLE,
        });
    },
    updateComposerValue: function (value) {
        dispatcher.dispatch({
            type: ACTION_TYPES.UPDATE_COMPOSER_VALUE,
            value: value,
        });
    },
    makeRequest: function (opts) {
        new RpcExchange(opts).promise.catch(function ignore() {});
    }
};

module.exports = consoleActionCreators;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/rpc/exchange":34}],3:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var modalActionCreators = {
	openModal: function (content) {
		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_MODAL,
			content: content,
		});
	},
	closeModal: function () {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_MODAL,
		});
	},
};

module.exports = modalActionCreators;


},{"../constants/action-types":31,"../dispatcher":32}],4:[function(require,module,exports){
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


},{"../constants/action-types":31,"../dispatcher":32,"../lib/rpc":35,"../stores/authorization-store":40}],5:[function(require,module,exports){
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

                platforms.forEach(function (platform) {
                    platformActionCreators.loadPlatform(platform);
                });
            })
            .catch(rpc.Error, handle401);
    },
    registerPlatform: function (name, address) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'register_platform',
            authorization: authorization,
            params: {
                identity: 'platform.agent',
                agentid: name,
                address: address,
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


},{"../action-creators/platform-action-creators":4,"../constants/action-types":31,"../dispatcher":32,"../lib/rpc":35,"../stores/authorization-store":40}],6:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformsPanelActionCreators = {    
    togglePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL,
        });
    },

    loadPanelPlatforms: function () {
        if (!authorizationStore.getAuthorization()) { return; }

        

        var authorization = authorizationStore.getAuthorization();

        return new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
                    platforms: platforms,
                });

                // platforms.forEach(function (platform) {
                //     platformActionCreators.loadPlatform(platform);
                // });
            })
            .catch(rpc.Error, handle401);
        
    },

    loadChildren: function(type, parent)
    {
        switch (type)
        {
            case "platform":
                platformsPanelActionCreators.loadPanelAgents(parent);
                platformsPanelActionCreators.loadPanelBuildings(parent);
                platformsPanelActionCreators.loadPanelPoints(parent);
                break;
            case "building":
                platformsPanelActionCreators.loadPanelDevices(parent);
                platformsPanelActionCreators.loadPanelPoints(parent);
                break;
            case "device":
                platformsPanelActionCreators.loadPanelPoints(parent);
                platformsPanelActionCreators.loadPanelDevices(parent);
                break;
            case "type":

                for (var i = 0; i < parent.children.length; i++)
                {
                    platformsPanelActionCreators.loadChildren(parent[parent.children[i]].type, parent[parent.children[i]]);
                }

                // for (var i = 0; i < parent.children.length; i++)
                // {
                //     platformsPanelActionCreators.loadChildren(parent.children[i], parent[parent.children[i]]);
                // }
                break;
            default:

        }
    },
    loadPanelPoints: function (parent) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_POINT_STATUSES,
            platform: parent
        });
    },
    loadPanelDevices: function (parent) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
            platform: parent
        });
    },
    loadPanelBuildings: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_BUILDING_STATUSES,
            platform: platform
        });
    },
    loadPanelAgents: function (platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.list_agents',
            authorization: authorization,
        }).promise
            .then(function (agentsList) {
                // platform.agents = agentsList;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                    platform: platform,
                    agents: agentsList
                });

                // if (!agentsList.length) { return; }

                // new rpc.Exchange({
                //     method: 'platforms.uuid.' + platform.uuid + '.status_agents',
                //     authorization: authorization,
                // }).promise
                //     .then(function (agentStatuses) {
                //         platform.agents.forEach(function (agent) {
                //             if (!agentStatuses.some(function (status) {
                //                 if (agent.uuid === status.uuid) {
                //                     agent.actionPending = false;
                //                     agent.process_id = status.process_id;
                //                     agent.return_code = status.return_code;

                //                     return true;
                //                 }
                //             })) {
                //                 agent.actionPending = false;
                //                 agent.process_id = null;
                //                 agent.return_code = null;
                //             }

                //         });

                //         dispatcher.dispatch({
                //             type: ACTION_TYPES.RECEIVE_PLATFORM,
                //             platform: platform,
                //         });
                //     });
            })
            .catch(rpc.Error, handle401);
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
};

module.exports = platformsPanelActionCreators;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/rpc":35,"../stores/authorization-store":40}],7:[function(require,module,exports){
'use strict';

var React = require('react');

var platformActionCreators = require('../action-creators/platform-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');

var RemoveAgentForm = require('./remove-agent-form');

var AgentRow = React.createClass({displayName: "AgentRow",
    _onStop: function () {
        platformActionCreators.stopAgent(this.props.platform, this.props.agent);
    },
    _onStart: function () {
        platformActionCreators.startAgent(this.props.platform, this.props.agent);
    },
    _onRemove: function () {
        modalActionCreators.openModal(React.createElement(RemoveAgentForm, {platform: this.props.platform, agent: this.props.agent}));
    },
    render: function () {
        var agent = this.props.agent, status, action, remove;

        if (agent.actionPending === undefined) {
            status = 'Retrieving status...';
        } else if (agent.actionPending) {
            if (agent.process_id === null || agent.return_code !== null) {
                status = 'Starting...';
                action = (
                    React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", disabled: true})
                );
            } else {
                status = 'Stopping...';
                action = (
                    React.createElement("input", {className: "button button--agent-action", type: "button", value: "Stop", disabled: true})
                );
            }
        } else {
            if (agent.process_id === null) {
                status = 'Never started';
                action = (
                    React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", onClick: this._onStart})
                );
            } else if (agent.return_code === null) {
                status = 'Running (PID ' + agent.process_id + ')';
                action = (
                    React.createElement("input", {className: "button button--agent-action", type: "button", value: "Stop", onClick: this._onStop})
                );
            } else {
                status = 'Stopped (returned ' + agent.return_code + ')';
                action = (
                    React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", onClick: this._onStart})
                );
            }
        }

        remove = ( React.createElement("input", {className: "button button--agent-action", type: "button", value: "Remove", onClick: this._onRemove}) );

        return (
            React.createElement("tr", null, 
                React.createElement("td", null, agent.name), 
                React.createElement("td", null, agent.uuid), 
                React.createElement("td", null, status), 
                React.createElement("td", null, action, " ", remove)
            )
        );
    },
});

module.exports = AgentRow;


},{"../action-creators/modal-action-creators":3,"../action-creators/platform-action-creators":4,"./remove-agent-form":30,"react":undefined}],8:[function(require,module,exports){
'use strict';

var React = require('react');

var topicDataStore = require('../stores/topic-data-store');
var platformActionCreators = require('../action-creators/platform-action-creators');
var LineChart = require('./line-chart');

var chartTypes = {
    'line': LineChart,
};

var Chart = React.createClass({displayName: "Chart",
    getInitialState: function () {
        return getStateFromStores(this.props.platform, this.props.chart);
    },
    componentDidMount: function () {
        topicDataStore.addChangeListener(this._onStoreChange);

        if (!this._getTopicDataTimeout) {
            this._getTopicDataTimeout = setTimeout(this._getTopicData, 0);
        }
    },
    componentWillUnmount: function () {
        topicDataStore.removeChangeListener(this._onStoreChange);
        clearTimeout(this._getTopicDataTimeout);
    },
    _initTopicData: function () {

    },
    _onStoreChange: function () {
        this.setState(getStateFromStores(this.props.platform, this.props.chart));
    },
    _getTopicData: function () {
        platformActionCreators.getTopicData(
            this.props.platform,
            this.props.chart.topic
        );

        if (this.props.chart.refreshInterval) {
            this._getTopicDataTimeout = setTimeout(this._getTopicData, this.props.chart.refreshInterval);
        }
    },
    render: function () {
        var ChartClass = chartTypes[this.props.chart.type];

        return (
            React.createElement(ChartClass, {
                className: "chart", 
                chart: this.props.chart, 
                data: this.state.data || []}
            )
        );
    },
});

function getStateFromStores(platform, chart) {
    return { data: topicDataStore.getTopicData(platform, chart.topic) };
}

module.exports = Chart;


},{"../action-creators/platform-action-creators":4,"../stores/topic-data-store":49,"./line-chart":19,"react":undefined}],9:[function(require,module,exports){
'use strict';

var React = require('react');

var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');

var Composer = React.createClass({displayName: "Composer",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        consoleStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        consoleStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.replaceState(getStateFromStores());
    },
    _onSendClick: function () {
        consoleActionCreators.makeRequest(JSON.parse(this.state.composerValue));
    },
    _onTextareaChange: function (e) {
        consoleActionCreators.updateComposerValue(e.target.value);
    },
    render: function () {
        return (
            React.createElement("div", {className: "composer"}, 
                React.createElement("textarea", {
                    key: this.state.composerId, 
                    onChange: this._onTextareaChange, 
                    defaultValue: this.state.composerValue}
                ), 
                React.createElement("input", {
                    className: "button", 
                    ref: "send", 
                    type: "button", 
                    value: "Send", 
                    disabled: !this.state.valid, 
                    onClick: this._onSendClick}
                )
            )
        );
    },
});

function getStateFromStores() {
    var composerValue = consoleStore.getComposerValue();
    var valid = true;

    try {
        JSON.parse(composerValue);
    } catch (ex) {
        if (ex instanceof SyntaxError) {
            valid = false;
        } else {
            throw ex;
        }
    }

    return {
        composerId: consoleStore.getComposerId(),
        composerValue: composerValue,
        valid: valid,
    };
}

module.exports = Composer;


},{"../action-creators/console-action-creators":2,"../stores/console-store":41,"react":undefined}],10:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var ConfirmForm = React.createClass({displayName: "ConfirmForm",
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        this.props.onConfirm();
    },
    render: function () {
        return (
            React.createElement("form", {className: "confirmation-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, this.props.promptTitle), 
                React.createElement("p", null, 
                    this.props.promptText
                ), 
                React.createElement("div", {className: "form__actions"}, 
                    React.createElement("button", {
                        className: "button button--secondary", 
                        type: "button", 
                        onClick: this._onCancelClick, 
                        autoFocus: true
                    }, 
                        "Cancel"
                    ), 
                    React.createElement("button", {className: "button"}, this.props.confirmText)
                )
            )
        );
    },
});

module.exports = ConfirmForm;


},{"../action-creators/modal-action-creators":3,"react":undefined}],11:[function(require,module,exports){
'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');

var Console = React.createClass({displayName: "Console",
    render: function () {
        return (
            React.createElement("div", {className: "console"}, 
                React.createElement(Conversation, null), 
                React.createElement(Composer, null)
            )
        );
    }
});

module.exports = Console;


},{"./composer":9,"./conversation":12,"react":undefined}],12:[function(require,module,exports){
'use strict';

var $ = require('jquery');
var React = require('react');

var Exchange = require('./exchange');
var consoleStore = require('../stores/console-store');

var Conversation = React.createClass({displayName: "Conversation",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }

        consoleStore.addChangeListener(this._onChange);
    },
    componentDidUpdate: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    componentWillUnmount: function () {
        consoleStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        return (
            React.createElement("div", {ref: "conversation", className: "conversation"}, 
                this.state.exchanges.map(function (exchange, index) {
                    return (
                        React.createElement(Exchange, {key: index, exchange: exchange})
                    );
                })
            )
        );
    }
});

function getStateFromStores() {
    return { exchanges: consoleStore.getExchanges() };
}

module.exports = Conversation;


},{"../stores/console-store":41,"./exchange":16,"jquery":undefined,"react":undefined}],13:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var Chart = require('./chart');
var EditChartForm = require('./edit-chart-form');
var modalActionCreators = require('../action-creators/modal-action-creators');

var Dashboard = React.createClass({displayName: "Dashboard",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onEditChartClick: function (platform, chart) {
        modalActionCreators.openModal(React.createElement(EditChartForm, {platform: platform, chart: chart}));
    },
    render: function () {
        var charts;

        if (!this.state.platforms) {
            charts = (
                React.createElement("p", null, "Loading charts...")
            );
        } else {
            charts = [];

            this.state.platforms
                .sort(function (a, b) {
                    return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
                })
                .forEach(function (platform) {
                    if (!platform.charts) { return; }

                    platform.charts
                        .filter(function (chart) { return chart.pin; })
                        .forEach(function (chart) {
                            var key = [
                                platform.uuid,
                                chart.topic,
                                chart.type,
                            ].join('::');

                            charts.push(
                                React.createElement("div", {key: key, className: "view__item view__item--tile chart"}, 
                                    React.createElement("h3", {className: "chart__title"}, 
                                        React.createElement(Router.Link, {
                                            to: "platform", 
                                            params: {uuid: platform.uuid}
                                        }, 
                                            platform.name
                                        ), 
                                        ": ", chart.topic
                                    ), 
                                    React.createElement(Chart, {
                                        platform: platform, 
                                        chart: chart}
                                    ), 
                                    React.createElement("div", {className: "chart__actions"}, 
                                        React.createElement("a", {
                                            className: "chart__edit", 
                                            onClick: this._onEditChartClick.bind(this, platform, chart)
                                        }, 
                                            "Edit"
                                        )
                                    )
                                )
                            );
                        }, this);
                }, this);

            if (!charts.length) {
                charts = (
                    React.createElement("p", {className: "empty-help"}, 
                        "Pin a platform chart to have it appear on the dashboard"
                    )
                );
            }
        }

        return (
            React.createElement("div", {className: "view"}, 
                React.createElement("h2", null, "Dashboard"), 
                charts
            )
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformsStore.getPlatforms(),
    };
}

module.exports = Dashboard;


},{"../action-creators/modal-action-creators":3,"../stores/platforms-store":48,"./chart":8,"./edit-chart-form":15,"react":undefined,"react-router":undefined}],14:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformRegistrationStore = require('../stores/platform-registration-store');

var RegisterPlatformForm = React.createClass({displayName: "RegisterPlatformForm",
    getInitialState: function () {
        return getStateFromStores(this);
    },
    componentDidMount: function () {
        platformRegistrationStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformRegistrationStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        platformManagerActionCreators.deregisterPlatform(this.props.platform);
    },
    render: function () {
        return (
            React.createElement("form", {className: "register-platform-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, "Deregister platform"), 
                React.createElement("p", null, 
                    "Deregister ", React.createElement("strong", null, this.props.platform.name), "?"
                ), 
                React.createElement("div", {className: "form__actions"}, 
                    React.createElement("button", {
                        className: "button button--secondary", 
                        type: "button", 
                        onClick: this._onCancelClick, 
                        autoFocus: true
                    }, 
                        "Cancel"
                    ), 
                    React.createElement("button", {className: "button"}, "Deregister")
                )
            )
        );
    },
});

function getStateFromStores() {
    return { error: platformRegistrationStore.getLastDeregisterError() };
}

module.exports = RegisterPlatformForm;


},{"../action-creators/modal-action-creators":3,"../action-creators/platform-manager-action-creators":5,"../stores/platform-registration-store":45,"react":undefined}],15:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');

var EditChartForm = React.createClass({displayName: "EditChartForm",
    getInitialState: function () {
        var state = {};

        for (var prop in this.props.chart) {
            state[prop] = this.props.chart[prop];
        }

        return state;
    },
    _onPropChange: function (e) {
        var state = {};

        switch (e.target.type) {
        case 'checkbox':
            state[e.target.id] = e.target.checked;
            break;
        case 'number':
            state[e.target.id] = parseFloat(e.target.value);
            break;
        default:
            state[e.target.id] = e.target.value;
        }

        this.setState(state);
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        platformActionCreators.saveChart(this.props.platform, this.props.chart, this.state);
    },
    render: function () {
        var typeOptions;

        switch (this.state.type) {
        case 'line':
            typeOptions = (
                React.createElement("div", {className: "form__control-group"}, 
                    React.createElement("label", null, "Y-axis range"), 
                    React.createElement("label", {htmlFor: "min"}, "Min:"), " ", 
                    React.createElement("input", {
                        className: "form__control form__control--inline", 
                        type: "number", 
                        id: "min", 
                        onChange: this._onPropChange, 
                        value: this.state.min, 
                        placeholder: "auto"}
                    ), " ", 
                    React.createElement("label", {htmlFor: "max"}, "Max:"), " ", 
                    React.createElement("input", {
                        className: "form__control form__control--inline", 
                        type: "number", 
                        id: "max", 
                        onChange: this._onPropChange, 
                        value: this.state.max, 
                        placeholder: "auto"}
                    ), React.createElement("br", null), 
                    React.createElement("span", {className: "form__control-help"}, 
                        "Omit either to determine from data"
                    )
                )
            );
        }

        return (
            React.createElement("form", {className: "edit-chart-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, this.props.chart ? 'Edit' : 'Add', " chart"), 
                this.state.error && (
                    React.createElement("div", {className: "error"}, this.state.error.message)
                ), 
                React.createElement("div", {className: "form__control-group"}, 
                    React.createElement("label", {htmlFor: "topic"}, "Platform"), 
                    this.props.platform.name, " (", this.props.platform.uuid, ")"
                ), 
                React.createElement("div", {className: "form__control-group"}, 
                    React.createElement("label", {htmlFor: "topic"}, "Topic"), 
                    React.createElement("input", {
                        className: "form__control form__control--block", 
                        type: "text", 
                        id: "topic", 
                        onChange: this._onPropChange, 
                        value: this.state.topic, 
                        placeholder: "e.g. some/published/topic", 
                        required: true}
                    )
                ), 
                React.createElement("div", {className: "form__control-group"}, 
                    React.createElement("label", null, "Dashboard"), 
                    React.createElement("input", {
                        className: "form__control form__control--inline", 
                        type: "checkbox", 
                        id: "pin", 
                        onChange: this._onPropChange, 
                        checked: this.state.pin}
                    ), " ", 
                    React.createElement("label", {htmlFor: "pin"}, "Pin to dashboard")
                ), 
                React.createElement("div", {className: "form__control-group"}, 
                    React.createElement("label", {htmlFor: "refreshInterval"}, "Refresh interval (ms)"), 
                    React.createElement("input", {
                        className: "form__control form__control--inline", 
                        type: "number", 
                        id: "refreshInterval", 
                        onChange: this._onPropChange, 
                        value: this.state.refreshInterval, 
                        min: "250", 
                        step: "1", 
                        placeholder: "disabled"}
                    ), 
                    React.createElement("span", {className: "form__control-help"}, 
                        "Omit to disable"
                    )
                ), 
                React.createElement("div", {className: "form__control-group"}, 
                    React.createElement("label", {htmlFor: "type"}, "Chart type"), 
                    React.createElement("select", {
                        id: "type", 
                        onChange: this._onPropChange, 
                        value: this.state.type, 
                        autoFocus: true, 
                        required: true
                    }, 
                        React.createElement("option", {value: ""}, "-- Select type --"), 
                        React.createElement("option", {value: "line"}, "Line")
                    )
                ), 
                typeOptions, 
                React.createElement("div", {className: "form__actions"}, 
                    React.createElement("button", {
                        className: "button button--secondary", 
                        type: "button", 
                        onClick: this._onCancelClick
                    }, 
                        "Cancel"
                    ), 
                    React.createElement("button", {
                        className: "button", 
                        disabled: !this.state.topic || !this.state.type
                    }, 
                        "Save"
                    )
                )
            )
        );
    },
});

module.exports = EditChartForm;


},{"../action-creators/modal-action-creators":3,"../action-creators/platform-action-creators":4,"react":undefined}],16:[function(require,module,exports){
'use strict';

var React = require('react');

var Exchange = React.createClass({displayName: "Exchange",
    _formatTime: function (time) {
        var d = new Date();

        d.setTime(time);

        return d.toLocaleString();
    },
    _formatMessage: function (message) {
        return JSON.stringify(message, null, '    ');
    },
    render: function () {
        var exchange = this.props.exchange;
        var classes = ['response'];
        var responseText;

        if (!exchange.completed) {
            classes.push('response--pending');
            responseText = 'Waiting for response...';
        } else if (exchange.error) {
            classes.push('response--error');
            responseText = exchange.error.message;
        } else {
            if (exchange.response.error) {
                classes.push('response--error');
            }

            responseText = this._formatMessage(exchange.response);
        }

        return (
            React.createElement("div", {className: "exchange"}, 
                React.createElement("div", {className: "request"}, 
                    React.createElement("div", {className: "time"}, this._formatTime(exchange.initiated)), 
                    React.createElement("pre", null, this._formatMessage(exchange.request))
                ), 
                React.createElement("div", {className: classes.join(' ')}, 
                    exchange.completed && React.createElement("div", {className: "time"}, this._formatTime(exchange.completed)), 
                    React.createElement("pre", null, responseText)
                )
            )
        );
    }
});

module.exports = Exchange;


},{"react":undefined}],17:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');


var graphStore = require('../stores/graph-store');

var lineChart;

var Header = React.createClass({displayName: "Header",
  render: function() {
    return (
      React.createElement("div", {className: "row text-center"}, 
        React.createElement("div", {className: "col-md-12"}, 
          React.createElement("h3", null, "2011 to 2015")
        )
      )
    );
  }
});

var UserSelect = React.createClass({displayName: "UserSelect",
  render: function() {
    return (
      React.createElement("div", {className: "row text-center"}, 
        React.createElement("div", {className: "col-md-12"}, 
          React.createElement("div", {id: "user-select-dropdown", className: "dropdown"}, 
            React.createElement("button", {className: "btn btn-default dropdown-toggle", type: "button", id: "user-select", "data-toggle": "dropdown", "aria-haspopup": "true", "aria-expanded": "true"}, 
              React.createElement("span", {id: "select-text"}, "Avg Temp (ºF)"), " ", React.createElement("span", {className: "caret"})
            ), 
            React.createElement("ul", {onClick: this.props.handleSelect, className: "dropdown-menu", "aria-labelledby": "user-select"}, 
              React.createElement("li", null, React.createElement("a", {href: "javascript:void(0)", className: "select current-selection", id: "avg_temp_f"}, "Avg Temp (ºF)")), 
              React.createElement("li", null, React.createElement("a", {href: "javascript:void(0)", className: "select", id: "avg_min_temp_f"}, "Avg Min Temp (ºF)")), 
              React.createElement("li", null, React.createElement("a", {href: "javascript:void(0)", className: "select", id: "avg_max_temp_f"}, "Avg Max Temp (ºF)")), 
              React.createElement("li", null, React.createElement("a", {href: "javascript:void(0)", className: "select", id: "total_percipitation_in"}, "Total Percipitation (in)")), 
              React.createElement("li", null, React.createElement("a", {href: "javascript:void(0)", className: "select", id: "total_snowfall_in"}, "Total Snowfall (in)"))
            )
          )
        )
      )
    );
  }
});

var BarChart = React.createClass({displayName: "BarChart",
  componentDidMount: function() {
    drawLineChart('line-chart', lineData(this.props.selection, keyToYearThenMonth(this.props.data)));
  },
  componentDidUpdate: function() {
    updateLineChart('line-chart', lineData(this.props.selection, keyToYearThenMonth(this.props.data)));
  },
  render: function() {
    return (
      React.createElement("div", {id: "line-chart"}, 
        React.createElement("svg", null)
      )
    );
  }
});

var Viz = React.createClass({displayName: "Viz",
  getInitialState: function() {
    return {
      data: [],
      selection: 'avg_temp_f'
    };
  },
  // loadData: function () {
  //   d3.csv('/data/018_analytics_chart.csv',function(csv){
  //     this.setState({
  //       data: csv
  //     });
  //   }.bind(this));
  // },
  // componentDidMount: function () {
  //   this.loadData();
  // },
  loadData: function (datum) {
    
    this.setState({ data: datum});
  },
  componentDidMount: function () {
    var datum = graphStore.getGraphData();
    this.loadData(datum);
  },
  handleUserSelect: function (e) {
    var selection = e.target.id;
    $('#select-text').text(e.target.innerHTML);
    $('.select').removeClass('current-selection');
    $('#' + selection).addClass('current-selection');
    this.setState({
      selection: selection
    });
  },
  render: function() {
    return (
      React.createElement("div", {id: "viz"}, 
        React.createElement(Header, null), 
        React.createElement(UserSelect, {selection: this.state.selection, handleSelect: this.handleUserSelect}), 
         this.state.data.length != 0 ? React.createElement(BarChart, {data: this.state.data, selection: this.state.selection}) : null
      )
    );
  }
});


var Graph = React.createClass({displayName: "Graph",
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        
    },
    componentDidMount: function () {
        graphStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        graphStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var graphs  = [];        

        

        return (
                React.createElement("div", {className: "view"}, 
                    React.createElement("div", {id: "chart", class: "with-3d-shadow with-transitions"}, 
                        React.createElement(Viz, null)
                    )

                )
        );
    },
});


function getStateFromStores() {
    return {
        graphs: graphStore.getGraphs(),
    };
}

function testData() {
    return stream_layers(3,128,.1).map(function(data, i) {
        return {
            key: 'Stream' + i,
            area: i === 1,
            values: data
        };
    });
}

function stream_layers(n, m, o) {
    if (arguments.length < 3) o = 0;
    function bump(a) {
    var x = 1 / (.1 + Math.random()),
        y = 2 * Math.random() - .5,
        z = 10 / (.1 + Math.random());
    for (var i = 0; i < m; i++) {
      var w = (i / m - y) * z;
      a[i] += x * Math.exp(-w * w);
    }
    }
    return d3.range(n).map(function() {
      var a = [], i;
      for (i = 0; i < m; i++) a[i] = o + o * Math.random();
      for (i = 0; i < 5; i++) bump(a);
      return a.map(stream_index);
    });
    }

    /* Another layer generator using gamma distributions. */
    function stream_waves(n, m) {
    return d3.range(n).map(function(i) {
    return d3.range(m).map(function(j) {
        var x = 20 * j / m - i / 3;
        return 2 * x * Math.exp(-.5 * x);
      }).map(stream_index);
    });
    }

    function stream_index(d, i) {
    return {x: i, y: Math.max(0, d)};
}


function drawLineChart (elementParent, data) {
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  nv.addGraph(function() {
    lineChart = nv.models.lineChart()
      .margin({left: 25, right: 25})
      .x(function(d) {return d.x})
      .y(function(d) {return d.y})
      .useInteractiveGuideline(true)
      .showYAxis(true)
      .showXAxis(true);
    lineChart.xAxis
      .tickFormat(function (d) { return months[d - 1]; })
      .staggerLabels(false);
    lineChart.yAxis
      .tickFormat(d3.format('.1f'));
    d3.select('#' + elementParent + ' svg')
      .datum(data)
      .call(lineChart);
    nv.utils.windowResize(function() { lineChart.update() });
    return lineChart;
  });
}

function updateLineChart (elementParent, data) {
  d3.select('#' + elementParent + ' svg')
    .datum(data)
    .call(lineChart);
}


//line data
function keyToYearThenMonth (data) {
  var keyYearMonth = d3.nest()
    .key(function(d){return d.year; })
    .key(function(d){return d.month; });
  var keyedData = keyYearMonth.entries(
    data.map(function(d) {
      return d;
    })
  );
  return keyedData;
}

function lineData (selection, data) {
  var colors = ['#ff7f00','#984ea3','#4daf4a','#377eb8','#e41a1c'];
  data = data.sort(function(a,b){ return +a.key - +b.key; });
  var lineDataArr = [];
  for (var i = 0; i <= data.length-1; i++) {
    var lineDataElement = [];
    var currentValues = data[i].values.sort(function(a,b){ return +a.key - +b.key; });
    for (var j = 0; j <= currentValues.length-1; j++) {
      lineDataElement.push({
        'x': +currentValues[j].key,
        'y': +currentValues[j].values[0][selection]
      });
    }
    lineDataArr.push({
      key: +data[i].key,
      color: colors[i],
      values: lineDataElement
    });
  }
  return lineDataArr;
}


module.exports = Graph;


},{"../stores/graph-store":42,"d3":undefined,"nvd3":undefined,"react":undefined,"react-router":undefined}],18:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var Graph = require('./graph');

var graphStore = require('../stores/graph-store');

var Graphs = React.createClass({displayName: "Graphs",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        graphStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        graphStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var graphs  = [];

        var graph = React.createElement(Graph, null)

        return (
                React.createElement("div", null, 
                    React.createElement("div", {className: "view"}, 
                        React.createElement("h2", null, "Graphs"), 
                        graph
                    )
                )
        );
    },
});

function getStateFromStores() {
    return {
        graphs: graphStore.getGraphs(),
    };
}

module.exports = Graphs;


},{"../stores/graph-store":42,"./graph":17,"react":undefined,"react-router":undefined}],19:[function(require,module,exports){
'use strict';

var d3 = require('d3');
var moment = require('moment');
var React = require('react');

var LineChart = React.createClass({displayName: "LineChart",
    getInitialState: function () {
        var initialState = {
            data: this.props.data,
            xDates: false,
        };

        if (this.props.data.length &&
            typeof this.props.data[0][0] === 'string' &&
            Date.parse(this.props.data[0][0] + 'Z')) {
            initialState.data = this.props.data.map(function (value) {
                return[Date.parse(value[0] + 'Z'), value[1]];
            });
            initialState.xDates = true;
        }

        return initialState;
    },
    componentDidMount: function () {
        this._updateSize();
        window.addEventListener('resize', this._onResize);
    },
    componentWillReceiveProps: function (newProps) {
        var newState = {
            data: newProps.data,
            xDates: false,
        };

        if (newProps.data.length &&
            typeof newProps.data[0][0] === 'string' &&
            Date.parse(newProps.data[0][0] + 'Z')) {
            newState.data = newProps.data.map(function (value) {
                return[Date.parse(value[0] + 'Z'), value[1]];
            });
            newState.xDates = true;
        }

        this.setState(newState);
    },
    componentWillUpdate: function () {
        this._updateSize();
    },
    componentWillUnmount: function () {
        window.removeEventListener('resize', this._onResize);
    },
    _onResize: function () {
        this.forceUpdate();
    },
    _updateSize: function () {
        var computedStyles = window.getComputedStyle(React.findDOMNode(this.refs.svg));
        this._width = parseInt(computedStyles.width, 10);
        this._height = parseInt(computedStyles.height, 10);
    },
    render: function () {
        var contents = [];

        if (this._width && this._height) {
            contents.push(
                React.createElement("path", {
                    key: "xAxis", 
                    className: "axis", 
                    strokeLinecap: "square", 
                    d: 'M3,' + (this._height - 19) + 'L' + (this._width - 3) + ',' + (this._height - 19)}
                )
            );

            contents.push(
                React.createElement("path", {
                    key: "yAxis", 
                    className: "axis", 
                    strokeLinecap: "square", 
                    d: 'M3,17L3,' + (this._height - 19)}
                )
            );

            if (!this.state.data.length) {
                contents.push(
                    React.createElement("text", {
                        key: "noData", 
                        className: "no-data-text", 
                        x: this._width / 2, 
                        y: this._height / 2, 
                        textAnchor: "middle"
                    }, 
                        "No data available"
                    )
                );
            } else {
                var xRange = d3.extent(this.state.data, function (d) { return d[0]; });
                var yMin = (this.props.chart.min === 0 || this.props.chart.min) ?
                    this.props.chart.min : d3.min(this.state.data, function (d) { return d[1]; });
                var yMax = (this.props.chart.max === 0 || this.props.chart.max) ?
                    this.props.chart.max : d3.max(this.state.data, function (d) { return d[1]; });

                var x = d3.scale.linear()
                    .range([4, this._width - 4])
                    .domain(xRange);
                var y = d3.scale.linear()
                    .range([this._height - 20, 18])
                    .domain([yMin, yMax]);

                var line = d3.svg.line()
                    .x(function (d) { return x(d[0]); })
                    .y(function (d) { return y(d[1]); });

                contents.push(
                    React.createElement("text", {
                        key: "xMinLabel", 
                        className: "label", 
                        x: "2", 
                        y: this._height - 4
                    }, 
                        this.state.xDates ? moment(xRange[0]).fromNow() : xRange[0]
                    )
                );

                contents.push(
                    React.createElement("text", {
                        key: "xMaxLabel", 
                        className: "label", 
                        x: this._width - 2, 
                        y: this._height - 4, 
                        textAnchor: "end"
                    }, 
                        this.state.xDates ? moment(xRange[1]).fromNow() : xRange[1]
                    )
                );

                contents.push(
                    React.createElement("text", {
                        key: "yMaxLabel", 
                        className: "label", x: "2", y: "10"}, 
                        yMax
                    )
                );

                contents.push(
                    React.createElement("path", {
                        key: "line", 
                        className: "line", 
                        strokeLinecap: "round", 
                        d: line(this.state.data)}
                    )
                );

                this.state.data.forEach(function (d, index) {
                    var text;

                    if (this.state.xDates) {
                        text = d[1]  + ' @ ' + moment(d[0]).format('MMM D, YYYY h:mm:ss A');
                    } else {
                        text = d.join(', ');
                    }

                    contents.push(
                        React.createElement("g", {key: 'point' + index, className: "dot"}, 
                            React.createElement("circle", {className: "outer", cx: x(d[0]), cy: y(d[1]), r: "4"}), 
                            React.createElement("circle", {className: "inner", cx: x(d[0]), cy: y(d[1]), r: "2"}), 
                            React.createElement("text", {
                                x: this._width / 2, 
                                y: "10", 
                                textAnchor: "middle"
                            }, 
                                text
                            )
                        )
                    );
                }, this);
            }
        }

        return (
            React.createElement("svg", {className: "chart__svg chart__svg--line", ref: "svg"}, 
                contents
            )
        );
    },
});

module.exports = LineChart;


},{"d3":undefined,"moment":undefined,"react":undefined}],20:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var loginFormStore = require('../stores/login-form-store');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LoginForm = React.createClass({displayName: "LoginForm",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        loginFormStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        loginFormStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onUsernameChange: function (e) {
        this.setState({
            username: e.target.value,
            error: null,
        });
    },
    _onPasswordChange: function (e) {
        this.setState({
            password: e.target.value,
            error: null,
        });
    },
    _onSubmit: function (e) {
        e.preventDefault();
        platformManagerActionCreators.requestAuthorization(
            this.state.username,
            this.state.password
        );
    },
    render: function () {
        return (
            React.createElement("form", {className: "login-form", onSubmit: this._onSubmit}, 
                React.createElement("input", {
                    className: "login-form__field", 
                    type: "text", 
                    placeholder: "Username", 
                    autoFocus: true, 
                    onChange: this._onUsernameChange}
                ), 
                React.createElement("input", {
                    className: "login-form__field", 
                    type: "password", 
                    placeholder: "Password", 
                    onChange: this._onPasswordChange}
                ), 
                React.createElement("input", {
                    className: "button login-form__submit", 
                    type: "submit", 
                    value: "Log in", 
                    disabled: !this.state.username || !this.state.password}
                ), 
                this.state.error ? (
                    React.createElement("span", {className: "login-form__error error"}, 
                        this.state.error.message, " (", this.state.error.code, ")"
                    )
                ) : null
            )
        );
    }
});

function getStateFromStores() {
    return { error: loginFormStore.getLastError() };
}

module.exports = LoginForm;


},{"../action-creators/platform-manager-action-creators":5,"../stores/login-form-store":43,"react":undefined,"react-router":undefined}],21:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var Modal = React.createClass({displayName: "Modal",
	_onClick: function (e) {
		if (e.target === e.currentTarget) {
			modalActionCreators.closeModal();
		}
	},
	render: function () {
		return (
			React.createElement("div", {className: "modal__overlay", onClick: this._onClick}, 
				React.createElement("div", {className: "modal__dialog"}, 
					this.props.children
				)
			)
		);
	},
});

module.exports = Modal;


},{"../action-creators/modal-action-creators":3,"react":undefined}],22:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var authorizationStore = require('../stores/authorization-store');

var Navigation = React.createClass({displayName: "Navigation",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        authorizationStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        authorizationStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onLogOutClick: function () {
        platformManagerActionCreators.clearAuthorization();
    },
    render: function () {
        var navItems;

        if (this.state.loggedIn) {
            navItems = ['Dashboard', 'Platforms'].map(function (navItem) {
                var route = navItem.toLowerCase();

                return (
                    React.createElement(Router.Link, {
                        key: route, 
                        to: route, 
                        className: "navigation__item", 
                        activeClassName: "navigation__item--active"
                    }, 
                        navItem
                    )
                );
            });

            navItems.push(
                React.createElement("a", {
                    key: "logout", 
                    className: "navigation__item", 
                    tabIndex: "0", 
                    onClick: this._onLogOutClick
                }, 
                    "Log out"
                )
            );
        }

        return (
            React.createElement("nav", {className: "navigation"}, 
                React.createElement("h1", {className: "logo"}, 
                    React.createElement("span", {className: "logo__name"}, "VOLTTRON"), 
                    React.createElement("span", {className: "logo__tm"}, "™"), 
                    React.createElement("span", {className: "logo__central"}, " Central"), 
                    React.createElement("span", {className: "logo__beta"}, "BETA")
                ), 
                navItems
            )
        );
    }
});

function getStateFromStores() {
    return {
        loggedIn: !!authorizationStore.getAuthorization(),
    };
}

module.exports = Navigation;


},{"../action-creators/platform-manager-action-creators":5,"../stores/authorization-store":40,"react":undefined,"react-router":undefined}],23:[function(require,module,exports){
'use strict';

var React = require('react');

var PageNotFound = React.createClass({displayName: "PageNotFound",
    render: function () {
        return (
            React.createElement("div", {className: "view"}, 
                React.createElement("h2", null, "Page not found")
            )
        );
    },
});

module.exports = PageNotFound;


},{"react":undefined}],24:[function(require,module,exports){
'use strict';

var $ = require('jquery');
var React = require('react');
var Router = require('react-router');

var authorizationStore = require('../stores/authorization-store');
var Console = require('./console');
var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');
var Modal = require('./modal');
var modalActionCreators = require('../action-creators/modal-action-creators');
var modalStore = require('../stores/modal-store');
var Navigation = require('./navigation');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var PlatformsPanel = require('./platforms-panel');
var platformsPanelStore = require('../stores/platforms-panel-store');

var PlatformManager = React.createClass({displayName: "PlatformManager",
    mixins: [Router.Navigation, Router.State],
    getInitialState: function () {
        var state = getStateFromStores(); 
        // state.expanded = false;

        return state;
    },
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        authorizationStore.addChangeListener(this._onStoreChange);
        consoleStore.addChangeListener(this._onStoreChange);
        modalStore.addChangeListener(this._onStoreChange);
        platformsPanelStore.addChangeListener(this._onStoreChange);
        this._doModalBindings();
    },
    componentDidUpdate: function () {
        this._doModalBindings();
    },
    _doModalBindings: function () {
        if (this.state.modalContent) {
            window.addEventListener('keydown', this._closeModal);
            this._focusDisabled = $('input,select,textarea,button,a', React.findDOMNode(this.refs.main)).attr('tabIndex', -1);
        } else {
            window.removeEventListener('keydown', this._closeModal);
            if (this._focusDisabled) {
                this._focusDisabled.removeAttr('tabIndex');
                delete this._focusDisabled;
            }
        }
    },
    componentWillUnmount: function () {
        authorizationStore.removeChangeListener(this._onStoreChange);
        consoleStore.removeChangeListener(this._onStoreChange);
        modalStore.removeChangeListener(this._onStoreChange);
        this._modalCleanup();
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onToggleClick: function () {
        consoleActionCreators.toggleConsole();
    },
    _closeModal: function (e) {
        if (e.keyCode === 27) {
            modalActionCreators.closeModal();
        }
    },
    render: function () {
        var classes = ['platform-manager'];
        var modal;
        var exteriorClasses = ["panel-exterior"];

        if (this.state.expanded === true)
        {
            exteriorClasses.push("narrow-exterior");
            exteriorClasses.push("slow-narrow");
        }
        else if (this.state.expanded === false)
        {
            exteriorClasses.push("wide-exterior");
            exteriorClasses.push("slow-wide");
        }
        else if (this.state.expanded === null)
        {
            exteriorClasses.push("wide-exterior");
        }

        if (this.state.consoleShown) {
            classes.push('platform-manager--console-open');
        }

        classes.push(this.state.loggedIn ?
            'platform-manager--logged-in' : 'platform-manager--not-logged-in');

        if (this.state.modalContent) {
            classes.push('platform-manager--modal-open');
            modal = (
                React.createElement(Modal, null, this.state.modalContent)
            );
        }

        return (
            React.createElement("div", {className: classes.join(' ')}, 
                modal, 
                React.createElement("div", {ref: "main", className: "main"}, 
                    React.createElement(Navigation, null), 
                    React.createElement(PlatformsPanel, null), 
                    React.createElement("div", {className: exteriorClasses.join(' ')}, 
                        React.createElement(Router.RouteHandler, null)
                    )
                ), 
                React.createElement("input", {
                    className: "toggle", 
                    type: "button", 
                    value: 'Console ' + (this.state.consoleShown ? '\u25bc' : '\u25b2'), 
                    onClick: this._onToggleClick}
                ), 
                this.state.consoleShown && React.createElement(Console, {className: "console"})
            )
        );
    },
});

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!authorizationStore.getAuthorization(),
        modalContent: modalStore.getModalContent(),
        expanded: platformsPanelStore.getExpanded(),
    };
}

module.exports = PlatformManager;


},{"../action-creators/console-action-creators":2,"../action-creators/modal-action-creators":3,"../action-creators/platform-manager-action-creators":5,"../stores/authorization-store":40,"../stores/console-store":41,"../stores/modal-store":44,"../stores/platforms-panel-store":47,"./console":11,"./modal":21,"./navigation":22,"./platforms-panel":27,"jquery":undefined,"react":undefined,"react-router":undefined}],25:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var Chart = require('./chart');
var EditChartForm = require('./edit-chart-form');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platform = React.createClass({displayName: "Platform",
    mixins: [Router.State],
    getInitialState: function () {
        return getStateFromStores(this);
    },
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
        if (this.state.error) {
            platformActionCreators.clearPlatformError(this.state.platform);
        }
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores(this));
    },
    _onEditChartClick: function (platform, chart) {
        modalActionCreators.openModal(React.createElement(EditChartForm, {platform: platform, chart: chart}));
    },
    _onDeleteChartClick: function (platform, chart) {
        modalActionCreators.openModal(
            React.createElement(ConfirmForm, {
                promptTitle: "Delete chart", 
                promptText: 'Delete ' + chart.type + ' chart for ' + chart.topic + '?', 
                confirmText: "Delete", 
                onConfirm: platformActionCreators.deleteChart.bind(null, platform, chart)}
            )
        );
    },
    _onAddChartClick: function (platform) {
        modalActionCreators.openModal(React.createElement(EditChartForm, {platform: platform}));
    },
    _onFileChange: function (e) {
        if (!e.target.files.length) { return; }

        var reader = new FileReader();
        var platform = this.state.platform;
        var files = e.target.files;
        var parsedFiles = [];

        function doFile(index) {
            if (index === files.length) {
                platformActionCreators.installAgents(platform, parsedFiles);
                return;
            }

            reader.onload = function () {
                parsedFiles.push({
                    file_name: files[index].name,
                    file: reader.result,
                });
                doFile(index + 1);
            };

            reader.readAsDataURL(files[index]);
        }

        doFile(0);
    },
    render: function () {
        var platform = this.state.platform;

        if (!platform) {
            return (
                React.createElement("div", {className: "view"}, 
                    React.createElement("h2", null, 
                        React.createElement(Router.Link, {to: "platforms"}, "Platforms"), 
                        " / ", 
                        this.getParams().uuid
                    ), 
                    React.createElement("p", null, "Platform not found.")
                )
            );
        }

        var charts;
        var agents;

        if (!platform.charts) {
            charts = (
                React.createElement("p", null, "Loading charts...")
            );
        } else {
            charts = platform.charts.map(function (chart) {
                var key = [
                    platform.uuid,
                    chart.topic,
                    chart.type,
                ].join('::');

                return (
                    React.createElement("div", {key: key, className: "view__item view__item--tile chart"}, 
                        React.createElement("h4", {className: "chart__title"}, chart.topic), 
                        React.createElement(Chart, {
                            platform: platform, 
                            chart: chart}
                        ), 
                        React.createElement("div", {className: "chart__actions"}, 
                            React.createElement("a", {onClick: this._onEditChartClick.bind(this, platform, chart)}, 
                                "Edit"
                            ), 
                            React.createElement("a", {onClick: this._onDeleteChartClick.bind(this, platform, chart)}, 
                                "Delete"
                            )
                        )
                    )
                );
            }, this);
        }

        if (!platform.agents) {
            agents = (
                React.createElement("p", null, "Loading agents...")
            );
        } else if (!platform.agents.length) {
            agents = (
                React.createElement("p", null, "No agents installed.")
            );
        } else {
            agents = (
                React.createElement("table", null, 
                    React.createElement("thead", null, 
                        React.createElement("tr", null, 
                            React.createElement("th", null, "Agent"), 
                            React.createElement("th", null, "UUID"), 
                            React.createElement("th", null, "Status"), 
                            React.createElement("th", null, "Action")
                        )
                    ), 
                    React.createElement("tbody", null, 
                        platform.agents
                            .sort(function (a, b) {
                                if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                                if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                                return 0;
                            })
                            .map(function (agent) {
                                return (
                                    React.createElement(AgentRow, {
                                        key: agent.uuid, 
                                        platform: platform, 
                                        agent: agent})
                                );
                            })
                        
                    )
                )
            );
        }

        return (
            React.createElement("div", {className: "platform-view"}, 
                this.state.error && (
                    React.createElement("div", {className: "view__error error"}, this.state.error)
                ), 
                React.createElement("h2", null, 
                    React.createElement(Router.Link, {to: "platforms"}, "Platforms"), 
                    " / ", 
                    platform.name, " (", platform.uuid, ")"
                ), 
                React.createElement("h3", null, "Charts"), 
                charts, 
                React.createElement("div", null, 
                    React.createElement("button", {
                        className: "button", 
                        onClick: this._onAddChartClick.bind(null, this.state.platform)
                    }, 
                        "Add chart"
                    )
                ), 
                React.createElement("h3", null, "Agents"), 
                agents, 
                React.createElement("h3", null, "Install agents"), 
                React.createElement("input", {type: "file", multiple: true, onChange: this._onFileChange})
            )
        );
    },
});

function getStateFromStores(component) {
    return {
        platform: platformsStore.getPlatform(component.getParams().uuid),
        error: platformsStore.getLastError(component.getParams().uuid),
    };
}

module.exports = Platform;


},{"../action-creators/modal-action-creators":3,"../action-creators/platform-action-creators":4,"../stores/platforms-store":48,"./agent-row":7,"./chart":8,"./confirm-form":10,"./edit-chart-form":15,"react":undefined,"react-router":undefined}],26:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var PlatformsPanelItem = React.createClass({displayName: "PlatformsPanelItem",
    getInitialState: function () {
        var state = {};
        
        state.expanded = (this.props.panelItem.hasOwnProperty("expanded") ? this.props.panelItem.expanded : null);

        // state.expanded = null;
        state.showTooltip = false;
        state.tooltipX = null;
        state.tooltipY = null;
        state.keepTooltip = false;
        state.expandedChildren;
        // state.expandedOn = null;

        state.children = getChildrenFromStore(this.props.panelItem, this.props.itemPath);

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillMount: function () {
        if (!this.props.hasOwnProperty("children"))
        { 
            platformsPanelActionCreators.loadChildren(this.props.panelItem.type, this.props.panelItem);
        }
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var children = getChildrenFromStore(this.props.panelItem, this.props.itemPath);

        this.setState({children: children});
    },
    _expandAll : function () {
        var expandedOn = ((this.state.expanded === null) ? true : !this.state.expanded);

        // this.setState({expandedOn: expandedOn});
        this.setState({expanded: expandedOn});
        
        this.setState({expandedChildren: expandAllChildren(expandedOn, this.props.panelItem)});
    },
    _toggleItem: function () {

        if (this.state.children.length > 0)
        {
            this.setState({expanded: !this.state.expanded});
        }
        else
        {
            if (this.props.hasOwnProperty("children"))
            {
                if (this.state.expanded === null)
                {
                    this.setState({expanded: !this.props.panelItem.expanded});
                }
                else
                {
                    this.setState({expanded: !this.state.expanded});
                }
            }
        }
        
    },
    _showTooltip: function (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - 20});
        this.setState({tooltipY: evt.clientY - 70});
    },
    _hideTooltip: function () {
        this.setState({showTooltip: false});
    },
    _moveTooltip: function (evt) {
        this.setState({tooltipX: evt.clientX - 20});
        this.setState({tooltipY: evt.clientY - 70});
    },
    _keepTooltip: function () {
        this.setState({keepTooltip: true});
    },
    _unkeepTooltip: function () {
        this.setState({keepTooltip: false});
    },
    render: function () {
        var panelItem = this.props.panelItem;
        var itemPath = this.props.itemPath;

        var items;
        var children;

        var propChildren = this.state.expandedChildren;

        if (typeof propChildren === "undefined" || propChildren === null)
        {
            propChildren = this.props.children;
        }

        var filterTerm = this.props.filter;

        var itemClasses;
        var arrowClasses = ["arrowButton", "noRotate"];

        var checkboxClass = "panelItemCheckbox";

        var checkboxStyle = {
            display : (["point"].indexOf(panelItem.type) < 0 ? "none" : "block")
        };

        var tooltipStyle = {
            display: (panelItem.type !== "type" ? (this.state.showTooltip || this.state.keepTooltip ? "block" : "none") : "none"),
            position: "absolute",
            top: this.state.tooltipY + "px",
            left: this.state.tooltipX + "px"
        };

        arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) );

        var arrowContent;

        if (panelItem.status === "GOOD")
        {
            arrowContent = React.createElement("span", null, "▶");
        } 
        else if (panelItem.status === "BAD") 
        {
            arrowContent = React.createElement("i", {className: "fa fa-minus-circle"});
        }
        else
        {
            arrowContent = React.createElement("span", null, "▬");
        }
        
        if (typeof propChildren !== "undefined" && propChildren !== null)
        {   
            if (this.state.expanded || this.props.panelItem.expanded === true)
            {
                children = propChildren
                    .sort(function (a, b) {
                        if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                        if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                        return 0;
                    })
                    .sort(function (a, b) {
                        if (a.sortOrder > b.sortOrder) { return 1; }
                        if (a.sortOrder < b.sortOrder) { return -1; }
                        return 0;
                    })
                    .map(function (propChild) {
                        
                        var grandchildren = [];
                        propChild.children.forEach(function (childString) {
                            grandchildren.push(propChild[childString]);
                        });

                        return (
                            React.createElement(PlatformsPanelItem, {panelItem: propChild, itemPath: propChild.path, children: grandchildren})
                        );
                    }); 

                if (children.length > 0)
                {
                    var classIndex = arrowClasses.indexOf("noRotate");
                    
                    if (classIndex > -1)
                    {
                        arrowClasses.splice(classIndex, 1);
                    }

                    arrowClasses.push("rotateDown");
                    itemClasses = "showItems";                    
                }          
            }
        }
        else
        {
            if (this.state.expanded !== null)
            {                   
                if (this.state.expanded)
                {                
                    if (this.state.children !== null)
                    {
                        var childItems = this.state.children;
                        
                        children = childItems
                            .sort(function (a, b) {
                                if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                                if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                                return 0;
                            })
                            .sort(function (a, b) {
                                if (a.sortOrder > b.sortOrder) { return 1; }
                                if (a.sortOrder < b.sortOrder) { return -1; }
                                return 0;
                            })
                            .map(function (child) {                            
                                return (
                                    React.createElement(PlatformsPanelItem, {panelItem: child, itemPath: child.path})
                                );}, this);

                        if (children.length > 0)
                        {
                            itemClasses = "showItems";

                            var classIndex = arrowClasses.indexOf("noRotate");
                            
                            if (classIndex > -1)
                            {
                                arrowClasses.splice(classIndex, 1);
                            }

                            arrowClasses.push("rotateDown");
                        }                            
                    }
                }
                else
                {
                    if (this.state.children) 
                    {
                        itemClasses = "hideItems";

                        arrowClasses.push("rotateRight");
                    }
                }
            }
        }

        var listItem;

        if (!panelItem.hasOwnProperty("uuid"))
        {
            listItem = 
                React.createElement("div", null, 
                    React.createElement("b", null, 
                        panelItem.name
                    )
                );
        }
        else
        {
            listItem = 
                React.createElement("div", {className: "platform-link"}, 
                    React.createElement(Router.Link, {
                        to: "graphs", 
                        params: {uuid: panelItem.uuid}
                    }, 
                    panelItem.name
                    )
                );            
        }

        return (
            React.createElement("li", {
                key: panelItem.uuid, 
                className: "panel-item"
            }, 
                React.createElement("div", {className: "platform-info"}, 
                    React.createElement("div", {className: arrowClasses.join(' '), 
                        onDoubleClick: this._expandAll, 
                        onClick: this._toggleItem}, 
                        arrowContent
                        ), 
                    React.createElement("input", {className: checkboxClass, 
                        style: checkboxStyle, 
                        type: "checkbox", 
                        onClick: this._checkItem}), 
                    React.createElement("div", {className: "tooltip_outer", 
                        style: tooltipStyle}, 
                        React.createElement("div", {className: "tooltip_inner"}, 
                            panelItem.uuid
                        ), 
                        React.createElement("div", {className: "tooltip_point"}, 
                            "▶"
                        )
                    ), 
                    React.createElement("div", {className: "tooltip_target", 
                        onMouseEnter: this._showTooltip, 
                        onMouseLeave: this._hideTooltip, 
                        onMouseMove: this._moveTooltip}, 
                        listItem
                    )
                ), 
                React.createElement("div", {className: itemClasses}, 
                    React.createElement("ul", {className: "platform-panel-list"}, 
                        children
                    )
                )
            )
        );
    },
});

function expandAllChildren(expandOn, parent)
{
    var expandedParent = platformsPanelItemsStore.getExpandedChildren(expandOn, parent);
    var expandedChildren = [];

    expandedParent.children.forEach(function(childString) {
        expandedChildren.push(expandedParent[childString]);
    })

    return expandedChildren;

}

function getChildrenFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getItems(parentItem, parentPath);
}

module.exports = PlatformsPanelItem;


},{"../action-creators/platforms-panel-action-creators":6,"../stores/platforms-panel-items-store":46,"react":undefined,"react-router":undefined}],27:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var PlatformsPanelItem = require('./platforms-panel-item');


var PlatformsPanel = React.createClass({displayName: "PlatformsPanel",
    getInitialState: function () {
        var state = {};
        state.platforms = [];  
        state.filteredPlatforms = null;   
        state.expanded = getExpandedFromStore();
        state.filterValue = "";

        return state;
    },
    componentWillMount: function () {
        platformsPanelActionCreators.loadPanelPlatforms();
    },
    componentDidMount: function () {
        platformsPanelStore.addChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.addChangeListener(this._onPanelItemsStoreChange);
    },
    componentWillUnmount: function () {
        platformsPanelStore.removeChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.removeChangeListener(this._onPanelItemsStoreChange);
    },
    _onPanelStoreChange: function () {
        var expanded = getExpandedFromStore();

        this.setState({expanded: expanded});

        if (expanded !== null)
        {
            this.setState({platforms: getPlatformsFromStore()});
        }
    },
    _onPanelItemsStoreChange: function () {
        if (this.state.expanded !== null)
        {
            this.setState({platforms: getPlatformsFromStore()});
        }
    },
    _onFilterBoxChange: function (e) {
        this.setState({ filterValue: e.target.value });
        this.setState({ filteredPlatforms: getFilteredPlatforms(e.target.value, "") });
    },
    _onFilterGood: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "GOOD") });
    },
    _onFilterBad: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "BAD") });
    },
    _onFilterUnknown: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "UNKNOWN") });
    },
    _onFilterOff: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "") });
    },
    _togglePanel: function () {
        platformsPanelActionCreators.togglePanel();
    },
    render: function () {
        var platforms;
        var filteredPlatforms = this.state.filteredPlatforms;

        var classes = (this.state.expanded === null ? 
                        "platform-statuses platform-collapsed" : 
                        (this.state.expanded ? 
                            "platform-statuses slow-open platform-expanded" :
                            "platform-statuses slow-shut platform-collapsed")
                        );

        var contentsStyle = { 
            display: (this.state.expanded ? "block" : "none"),
            padding: "0px 20px 20px 10px",
            clear: "right",
            width: "100%"
        };

        var filterBoxContainer = {
            textAlign: "left"
        };

        if (!this.state.platforms) {
            platforms = (
                React.createElement("p", null, "Loading platforms panel ...")
            );
        } else if (!this.state.platforms.length) {
            platforms = (
                React.createElement("p", null, "No platforms found.")
            );
        } 
        else 
        {
            if (filteredPlatforms !== null)
            {
                platforms = filteredPlatforms
                    .sort(function (a, b) {
                        if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                        if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                        return 0;
                    })
                    .map(function (filteredPlatform) {
                        
                        var children = [];
                        filteredPlatform.children.forEach(function (childString) {
                            children.push(filteredPlatform[childString]);
                        });

                        return (
                            React.createElement(PlatformsPanelItem, {panelItem: filteredPlatform, itemPath: filteredPlatform.path, children: children})
                        );
                });
            }
            else
            {
                platforms = this.state.platforms
                    .sort(function (a, b) {
                        if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                        if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                        return 0;
                    })
                    .map(function (platform) {
                        return (
                            React.createElement(PlatformsPanelItem, {panelItem: platform, itemPath: platform.path})
                        );
                    });
            }
        }

        return (
            React.createElement("div", {className: classes}, 
                React.createElement("div", {className: "extend-panel", 
                    onClick: this._togglePanel},  this.state.expanded ? '\u25c0' : '\u25b6'), 
                React.createElement("div", {style: contentsStyle}, 
                    React.createElement("br", null), 
                    React.createElement("div", {className: "filter_box", style: filterBoxContainer}, 
                        React.createElement("span", {className: "fa fa-search"}), 
                        React.createElement("input", {
                            type: "search", 
                            onChange: this._onFilterBoxChange, 
                            value:  this.state.filterValue}
                        ), 
                        React.createElement("div", {className: "filter_buttons"}, 
                            React.createElement("div", {className: "filter_button status-good", 
                                onClick: this._onFilterGood}, 
                                React.createElement("div", {className: "centeredDiv"}, 
                                    React.createElement("span", null, "▶")
                                )
                            ), 
                            React.createElement("div", {className: "filter_button status-bad", 
                                onClick: this._onFilterBad}, 
                                React.createElement("div", {className: "centeredDiv"}, 
                                    React.createElement("i", {className: "fa fa-minus-circle"})
                                )
                            ), 
                            React.createElement("div", {className: "filter_button status-unknown", 
                                onClick: this._onFilterUnknown}, 
                                React.createElement("div", {className: "centeredDiv"}, 
                                    React.createElement("span", null, "▬")
                                )
                            ), 
                            React.createElement("div", {className: "filter_button", 
                                onClick: this._onFilterOff}, 
                                React.createElement("div", {className: "centeredDiv"}, 
                                    React.createElement("i", {className: "fa fa-ban"})
                                )
                            )
                        )
                    ), 
                    React.createElement("ul", {className: "platform-panel-list"}, 
                        platforms
                    )
                )
            )
        );
    },
});

function getItemsFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getItems(parentItem, parentPath);
};

function getPlatformsFromStore() {
    return platformsPanelItemsStore.getItems("platforms", null);
};

function getExpandedFromStore() {
    return platformsPanelStore.getExpanded();
};

function getFilteredPlatforms(filterTerm, filterStatus) {

    var platformsList = [];

    if (filterTerm !== "" || filterStatus !== "")
    {
        var treeCopy = platformsPanelItemsStore.getTreeCopy();

        var platforms = treeCopy["platforms"];

        for (var key in platforms)
        {
            var filteredPlatform = platformsPanelItemsStore.getFilteredItems(platforms[key], filterTerm, filterStatus);

            if (filteredPlatform)
            {
                if ((filteredPlatform.children.length === 0) && (filteredPlatform.name.indexOf(filterTerm, filterStatus) < 0))
                {
                    filteredPlatform = null;
                }
            }

            if (filteredPlatform)
            {
                platformsList.push(filteredPlatform);
            }
        }
    }
    else
    {
        platformsList = null;
    }

    return platformsList;
}


// function filteredPlatform(platform, filterTerm) {

//     var treeCopy = platformsPanelItemsStore.getTreeCopy();

//     var filteredPlatform = platformsPanelItemsStore.getFilteredItems(treeCopy["platforms"][platform.uuid], filterTerm);


//     if (filteredPlatform)
//     {
//         if ((filteredPlatform.children.length === 0) && (filteredPlatform.name.indexOf(filterTerm) < 0))
//         {
//             filteredPlatform = null;
//         }
//     }

//     return filteredPlatform;
// };

module.exports = PlatformsPanel;


},{"../action-creators/platforms-panel-action-creators":6,"../stores/platforms-panel-items-store":46,"../stores/platforms-panel-store":47,"./platforms-panel-item":26,"react":undefined,"react-router":undefined}],28:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformsStore = require('../stores/platforms-store');
var RegisterPlatformForm = require('../components/register-platform-form');
var DeregisterPlatformConfirmation = require('../components/deregister-platform-confirmation');

var Platforms = React.createClass({displayName: "Platforms",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onRegisterClick: function () {
        modalActionCreators.openModal(React.createElement(RegisterPlatformForm, null));
    },
    _onDeregisterClick: function (platform) {
        modalActionCreators.openModal(React.createElement(DeregisterPlatformConfirmation, {platform: platform}));
    },
    render: function () {
        var platforms;

        if (!this.state.platforms) {
            platforms = (
                React.createElement("p", null, "Loading platforms...")
            );
        } else if (!this.state.platforms.length) {
            platforms = (
                React.createElement("p", null, "No platforms found.")
            );
        } else {
            platforms = this.state.platforms
                .sort(function (a, b) {
                    if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                    if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                    return 0;
                })
                .map(function (platform) {
                    var status = [platform.uuid];

                    if (platform.agents) {
                        var running = 0;
                        var stopped = 0;

                        platform.agents.forEach(function (agent) {
                            if (agent.process_id !== null) {
                                if (agent.return_code === null) {
                                    running++;
                                } else {
                                    stopped++;
                                }
                            }
                        });

                        status.push('Agents: ' + running + ' running, ' + stopped + ' stopped, ' + platform.agents.length + ' installed');
                    }

                    return (
                        React.createElement("div", {
                            key: platform.uuid, 
                            className: "view__item view__item--list"
                        }, 
                            React.createElement("h3", null, 
                                React.createElement(Router.Link, {
                                    to: "platform", 
                                    params: {uuid: platform.uuid}
                                }, 
                                    platform.name
                                )
                            ), 
                            React.createElement("button", {
                                className: "deregister-platform", 
                                onClick: this._onDeregisterClick.bind(this, platform), 
                                title: "Deregister platform"
                            }, 
                                "×"
                            ), 
                            React.createElement("code", null, status.join(' | '))
                        )
                    );
                }, this);
        }

        return (
            React.createElement("div", {className: "view"}, 
                React.createElement("h2", null, "Platforms"), 
                React.createElement("div", {className: "view__actions"}, 
                    React.createElement("button", {className: "button", onClick: this._onRegisterClick}, 
                        "Register platform"
                    )
                ), 
                platforms
            )
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformsStore.getPlatforms(),
    };
}

module.exports = Platforms;


},{"../action-creators/modal-action-creators":3,"../components/deregister-platform-confirmation":14,"../components/register-platform-form":29,"../stores/platforms-store":48,"react":undefined,"react-router":undefined}],29:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformRegistrationStore = require('../stores/platform-registration-store');

var RegisterPlatformForm = React.createClass({displayName: "RegisterPlatformForm",
    getInitialState: function () {
        var state = getStateFromStores();
        
        state.name = state.ipaddress = state.serverKey = state.publicKey = state.secretKey = '';
        state.protocol = 'tcp';

        return state;
    },
    componentDidMount: function () {
        platformRegistrationStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformRegistrationStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onNameChange: function (e) {
        this.setState({ name: e.target.value });
    },
    _onAddressChange: function (e) {
        this.setState({ ipaddress: e.target.value });
    },
    _onProtocolChange: function (e) {
        this.setState({ protocol: e.target.value });
    },
    _onServerKeyChange: function (e) {
        this.setState({ serverKey: e.target.value });
    },
    _onPublicKeyChange: function (e) {
        this.setState({ publicKey: e.target.value });
    },
    _onSecretKeyChange: function (e) {
        this.setState({ secretKey: e.target.value });
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {

        platformManagerActionCreators.registerPlatform(
            this.state.name, 
            this._formatAddress());
        
    },
    _formatAddress: function () {

        var fullAddress = this.state.protocol + "://" + this.state.ipaddress;

        if (this.state.serverKey)
        {
            fullAddress = fullAddress + "?serverkey=" + this.state.serverKey;
        }

        if (this.state.publicKey)
        {
            fullAddress = fullAddress + "&publickey=" + this.state.publicKey;
        }

        if (this.state.secretKey)
        {
            fullAddress = fullAddress + "&secretkey=" + this.state.secretKey;
        }

        return fullAddress;
    },
    render: function () {
        
        var fullAddress = this._formatAddress();

        return (
            React.createElement("form", {className: "register-platform-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, "Register platform"), 
                this.state.error && (
                    React.createElement("div", {className: "error"}, this.state.error.message)
                ), 
                React.createElement("div", {className: "tableDiv"}, 
                    React.createElement("div", {className: "rowDiv"}, 
                        React.createElement("div", {className: "cellDiv firstCell"}, 
                            React.createElement("label", {className: "formLabel"}, "Name"), 
                            React.createElement("input", {
                                className: "form__control form__control--block", 
                                type: "text", 
                                onChange: this._onNameChange, 
                                value: this.state.name, 
                                autoFocus: true, 
                                required: true}
                            )
                        ), 
                        React.createElement("div", {className: "cellDiv", 
                            width: "10%"}, 
                            React.createElement("label", {className: "formLabel"}, "Protocol"), React.createElement("br", null), 
                            React.createElement("select", {
                                className: "form__control", 
                                onChange: this._onProtocolChange, 
                                value: this.state.protocol, 
                                required: true
                            }, 
                                React.createElement("option", {value: "tcp"}, "TCP"), 
                                React.createElement("option", {value: "ipc"}, "IPC")
                            )
                        ), 
                        React.createElement("div", {className: "cellDiv", 
                            width: "56%"}, 
                            React.createElement("label", {className: "formLabel"}, "VIP address"), 
                            React.createElement("input", {
                                className: "form__control form__control--block", 
                                type: "text", 
                                onChange: this._onAddressChange, 
                                value: this.state.ipaddress, 
                                required: true}
                            )
                        )
                    )
                ), 
                React.createElement("div", {className: "tableDiv"}, 
                    React.createElement("div", {className: "rowDiv"}, 
                        React.createElement("div", {className: "cellDiv", 
                            width: "80%"}, 
                            React.createElement("label", {className: "formLabel"}, "Server Key"), 
                            React.createElement("input", {
                                className: "form__control form__control--block", 
                                type: "text", 
                                onChange: this._onServerKeyChange, 
                                value: this.state.serverKey}
                            )
                        )
                    )
                ), 
                React.createElement("div", {className: "tableDiv"}, 
                    React.createElement("div", {className: "rowDiv"}, 
                        React.createElement("div", {className: "cellDiv", 
                            width: "80%"}, 
                            React.createElement("label", {className: "formLabel"}, "Public Key"), 
                            React.createElement("input", {
                                className: "form__control form__control--block", 
                                type: "text", 
                                onChange: this._onPublicKeyChange, 
                                value: this.state.publicKey}
                            )
                        )
                    )
                ), 
                React.createElement("div", {className: "tableDiv"}, 
                    React.createElement("div", {className: "rowDiv"}, 
                        React.createElement("div", {className: "cellDiv", 
                            width: "80%"}, 
                            React.createElement("label", {className: "formLabel"}, "Secret Key"), 
                            React.createElement("input", {
                                className: "form__control form__control--block", 
                                type: "text", 
                                onChange: this._onSecretKeyChange, 
                                value: this.state.secretKey}
                            )
                        )
                    )
                ), 
                React.createElement("div", {className: "tableDiv"}, 
                    React.createElement("div", {className: "rowDiv"}, 
                        React.createElement("div", {className: "cellDiv", 
                            width: "100%"}, 
                            React.createElement("label", {className: "formLabel"}, "Preview"), 
                            React.createElement("div", {
                                className: "preview"}, 
                                fullAddress
                            )
                        )
                    )
                ), 
                React.createElement("div", {className: "form__actions"}, 
                    React.createElement("button", {
                        className: "button button--secondary", 
                        type: "button", 
                        onClick: this._onCancelClick
                    }, 
                        "Cancel"
                    ), 
                    React.createElement("button", {
                        className: "button", 
                        disabled: !this.state.name || !this.state.protocol || !this.state.ipaddress 
                            || !((this.state.serverKey && this.state.publicKey && this.state.secretKey) 
                                    || (!this.state.publicKey && !this.state.secretKey))
                    }, 
                        "Register"
                    )
                )
            )
        );
    },
});

function getStateFromStores() {
    return { error: platformRegistrationStore.getLastDeregisterError() };
}

module.exports = RegisterPlatformForm;


},{"../action-creators/modal-action-creators":3,"../action-creators/platform-manager-action-creators":5,"../stores/platform-registration-store":45,"react":undefined}],30:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');

var RemoveAgentForm = React.createClass({displayName: "RemoveAgentForm",
    getInitialState: function () {
        var state = {};

        for (var prop in this.props.agent) {
            state[prop] = this.props.agent[prop];
        }

        return state;
    }, 
    _onPropChange: function (e) {
        var state = {};

        this.setState(state);
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        platformActionCreators.removeAgent(this.props.platform, this.props.agent);
    },
    render: function () {

        var removeMsg = 'Remove agent ' + this.props.agent.uuid + ' (' + this.props.agent.name + 
            ', ' + this.props.agent.tag + ')?';

        return (
            React.createElement("form", {className: "remove-agent-form", onSubmit: this._onSubmit}, 
                React.createElement("div", null, removeMsg), 
                React.createElement("div", {className: "form__actions"}, 
                    React.createElement("button", {
                        className: "button button--secondary", 
                        type: "button", 
                        onClick: this._onCancelClick
                    }, 
                        "Cancel"
                    ), 
                    React.createElement("button", {
                        className: "button", 
                        type: "submit", 
                        disabled: !this.props.agent.uuid
                    }, 
                        "Remove"
                    )
                )
            )
        );
    },
});

module.exports = RemoveAgentForm;


},{"../action-creators/modal-action-creators":3,"../action-creators/platform-action-creators":4,"react":undefined}],31:[function(require,module,exports){
'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
    OPEN_MODAL: null,
    CLOSE_MODAL: null,

    TOGGLE_CONSOLE: null,

    UPDATE_COMPOSER_VALUE: null,

    MAKE_REQUEST: null,
    FAIL_REQUEST: null,
    RECEIVE_RESPONSE: null,

    RECEIVE_AUTHORIZATION: null,
    RECEIVE_UNAUTHORIZED: null,
    CLEAR_AUTHORIZATION: null,

    REGISTER_PLATFORM_ERROR: null,
    DEREGISTER_PLATFORM_ERROR: null,

    RECEIVE_PLATFORMS: null,
    RECEIVE_PLATFORM: null,
    RECEIVE_PLATFORM_ERROR: null,
    CLEAR_PLATFORM_ERROR: null,

    RECEIVE_PLATFORM_STATUSES: null,
    TOGGLE_PLATFORMS_PANEL: null,

    RECEIVE_AGENT_STATUSES: null,
    RECEIVE_DEVICE_STATUSES: null,
    RECEIVE_POINT_STATUSES: null,
    RECEIVE_BUILDING_STATUSES: null,

    RECEIVE_PLATFORM_TOPIC_DATA: null,
});


},{"react/lib/keyMirror":undefined}],32:[function(require,module,exports){
'use strict';

var Dispatcher = require('flux').Dispatcher;

var ACTION_TYPES = require('../constants/action-types');

var dispatcher = new Dispatcher();

dispatcher.dispatch = function (action) {
    if (action.type in ACTION_TYPES) {
        return Object.getPrototypeOf(this).dispatch.call(this, action);
    }

    throw 'Dispatch error: invalid action type ' + action.type;
};

module.exports = dispatcher;


},{"../constants/action-types":31,"flux":undefined}],33:[function(require,module,exports){
'use strict';

function RpcError(error) {
    this.name = 'RpcError';
    this.code = error.code;
    this.message = error.message;
    this.data = error.data;
}
RpcError.prototype = Object.create(Error.prototype);
RpcError.prototype.constructor = RpcError;

module.exports = RpcError;


},{}],34:[function(require,module,exports){
'use strict';

var uuid = require('node-uuid');

var ACTION_TYPES = require('../../constants/action-types');
var dispatcher = require('../../dispatcher');
var RpcError = require('./error');
var xhr = require('../xhr');

function RpcExchange(request, redactedParams) {
    if (!(this instanceof RpcExchange)) {
        return new RpcExchange(request);
    }

    var exchange = this;

    // TODO: validate request
    request.jsonrpc = '2.0';
    request.id = uuid.v1();

    // stringify before redacting params
    var data = JSON.stringify(request);

    if (redactedParams && redactedParams.length) {
        redactedParams.forEach(function (paramPath) {
            paramPath = paramPath.split('.');

            var paramParent = request.params;

            while (paramPath.length > 1) {
                paramParent = paramParent[paramPath.shift()];
            }

            paramParent[paramPath[0]] = '[REDACTED]';
        });
    }

    exchange.initiated = Date.now();
    exchange.request = request;

    dispatcher.dispatch({
        type: ACTION_TYPES.MAKE_REQUEST,
        exchange: exchange,
        request: exchange.request,
    });

    exchange.promise = new xhr.Request({
        method: 'POST',
        url: '/jsonrpc',
        contentType: 'application/json',
        data: data,
        timeout: 60000,
    })
        .finally(function () {
            exchange.completed = Date.now();
        })
        .then(function (response) {
            exchange.response = response;

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_RESPONSE,
                exchange: exchange,
                response: response,
            });

            if (response.error) {
                throw new RpcError(response.error);
            }

            return JSON.parse(JSON.stringify(response.result));
        })
        .catch(xhr.Error, function (error) {
            exchange.error = error;

            dispatcher.dispatch({
                type: ACTION_TYPES.FAIL_REQUEST,
                exchange: exchange,
                error: error,
            });

            throw error;
        });
}

module.exports = RpcExchange;


},{"../../constants/action-types":31,"../../dispatcher":32,"../xhr":38,"./error":33,"node-uuid":undefined}],35:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange'),
};


},{"./error":33,"./exchange":34}],36:[function(require,module,exports){
'use strict';

var EventEmitter = require('events').EventEmitter;

var CHANGE_EVENT = 'change';

function Store() {
    EventEmitter.call(this);
    this.setMaxListeners(0);
}
Store.prototype = EventEmitter.prototype;

Store.prototype.emitChange = function() {
    this.emit(CHANGE_EVENT);
};

Store.prototype.addChangeListener = function (callback) {
    this.on(CHANGE_EVENT, callback);
};

Store.prototype.removeChangeListener = function (callback) {
    this.removeListener(CHANGE_EVENT, callback);
};

module.exports = Store;


},{"events":undefined}],37:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;


},{}],38:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":37,"./request":39}],39:[function(require,module,exports){
'use strict';

var jQuery = require('jquery');
var Promise = require('bluebird');

var XhrError = require('./error');

function XhrRequest(opts) {
    return new Promise(function (resolve, reject) {
        opts.success = resolve;
        opts.error = function (response, type) {
            switch (type) {
            case 'error':
                reject(new XhrError('Server returned ' + response.status + ' status', response));
                break;
            case 'timeout':
                reject(new XhrError('Request timed out', response));
                break;
            default:
                reject(new XhrError('Request failed: ' + type, response));
            }
        };

        jQuery.ajax(opts);
    });
}

module.exports = XhrRequest;


},{"./error":37,"bluebird":undefined,"jquery":undefined}],40:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _authorization = sessionStorage.getItem('authorization');

var authorizationStore = new Store();

authorizationStore.getAuthorization = function () {
    return _authorization;
};

authorizationStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _authorization = action.authorization;
            sessionStorage.setItem('authorization', _authorization);
            authorizationStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            authorizationStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _authorization = null;
            sessionStorage.removeItem('authorization');
            authorizationStore.emitChange();
            break;
    }
});

module.exports = authorizationStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36}],41:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var Store = require('../lib/store');

var _composerId = Date.now();
var _composerValue = '';
var _consoleShown = false;
var _exchanges = [];

var consoleStore = new Store();

consoleStore.getComposerId = function () {
    return _composerId;
};

consoleStore.getComposerValue = function () {
    return _composerValue;
};

consoleStore.getConsoleShown = function () {
    return _consoleShown;
};

consoleStore.getExchanges = function () {
    return _exchanges;
};

function _resetComposerValue() {
    var authorization = authorizationStore.getAuthorization();
    var parsed;

    try {
        parsed = JSON.parse(_composerValue);
    } catch (e) {
        parsed = { method: '' };
    }

    if (authorization) {
        parsed.authorization = authorization;
    } else {
        delete parsed.authorization;
    }

    _composerValue = JSON.stringify(parsed, null, '    ');
}

_resetComposerValue();

consoleStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.TOGGLE_CONSOLE:
            _consoleShown = !_consoleShown;
            consoleStore.emitChange();
            break;

        case ACTION_TYPES.UPDATE_COMPOSER_VALUE:
            _composerValue = action.value;
            consoleStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _composerId = Date.now();
            _resetComposerValue();
            consoleStore.emitChange();
            break;

        case ACTION_TYPES.MAKE_REQUEST:
            if (_consoleShown) {
                _exchanges.push(action.exchange);
                consoleStore.emitChange();
            }
            break;

        case ACTION_TYPES.FAIL_REQUEST:
        case ACTION_TYPES.RECEIVE_RESPONSE:
            if (_consoleShown) {
                consoleStore.emitChange();
            }
            break;
    }
});

module.exports = consoleStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36,"../stores/authorization-store":40}],42:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var graphStore = new Store();

graphStore.getGraphs = function (uuid) {
    

    return null;
};

graphStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

graphStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    
});

graphStore.getGraphData = function () {
    var graphJson = [
  {
    "year": 2011,
    "month": 1,
    "avg_max_temp_f": 46.83,
    "avg_min_temp_f": 28.1,
    "avg_temp_f": 37.47,
    "total_percipitation_in": 2.35,
    "total_snowfall_in": 9.6
  },
  {
    "year": 2011,
    "month": 2,
    "avg_max_temp_f": 47.58,
    "avg_min_temp_f": 26.35,
    "avg_temp_f": 36.96,
    "total_percipitation_in": 7.61,
    "total_snowfall_in": 25.5
  },
  {
    "year": 2011,
    "month": 3,
    "avg_max_temp_f": 51.45,
    "avg_min_temp_f": 31.39,
    "avg_temp_f": 41.42,
    "total_percipitation_in": 11.74,
    "total_snowfall_in": 39.6
  },
  {
    "year": 2011,
    "month": 4,
    "avg_max_temp_f": 61.5,
    "avg_min_temp_f": 35.13,
    "avg_temp_f": 48.32,
    "total_percipitation_in": 1.44,
    "total_snowfall_in": 2.3
  },
  {
    "year": 2011,
    "month": 5,
    "avg_max_temp_f": 64.9,
    "avg_min_temp_f": 40.68,
    "avg_temp_f": 52.79,
    "total_percipitation_in": 2.17,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 6,
    "avg_max_temp_f": 73.79,
    "avg_min_temp_f": 48.18,
    "avg_temp_f": 60.98,
    "total_percipitation_in": 2.06,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 7,
    "avg_max_temp_f": 85.07,
    "avg_min_temp_f": 56.1,
    "avg_temp_f": 70.58,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 8,
    "avg_max_temp_f": 88.1,
    "avg_min_temp_f": 56.45,
    "avg_temp_f": 72.28,
    "total_percipitation_in": 0.15,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 9,
    "avg_max_temp_f": 84.47,
    "avg_min_temp_f": 54.13,
    "avg_temp_f": 69.3,
    "total_percipitation_in": 3.42,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 10,
    "avg_max_temp_f": 71.14,
    "avg_min_temp_f": 43.54,
    "avg_temp_f": 57.34,
    "total_percipitation_in": 2.8,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 11,
    "avg_max_temp_f": 53.62,
    "avg_min_temp_f": 32.07,
    "avg_temp_f": 42.62,
    "total_percipitation_in": 1.07,
    "total_snowfall_in": 5
  },
  {
    "year": 2011,
    "month": 12,
    "avg_max_temp_f": 48.97,
    "avg_min_temp_f": 25.42,
    "avg_temp_f": 37.19,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 1,
    "avg_max_temp_f": 51.5,
    "avg_min_temp_f": 28.2,
    "avg_temp_f": 39.85,
    "total_percipitation_in": 4.98,
    "total_snowfall_in": 1.1
  },
  {
    "year": 2012,
    "month": 2,
    "avg_max_temp_f": 54.32,
    "avg_min_temp_f": 29.86,
    "avg_temp_f": 42.09,
    "total_percipitation_in": 0.9,
    "total_snowfall_in": 11
  },
  {
    "year": 2012,
    "month": 3,
    "avg_max_temp_f": 54.45,
    "avg_min_temp_f": 32.62,
    "avg_temp_f": 43.53,
    "total_percipitation_in": 5.76,
    "total_snowfall_in": 24.5
  },
  {
    "year": 2012,
    "month": 4,
    "avg_max_temp_f": 63.69,
    "avg_min_temp_f": 38.83,
    "avg_temp_f": 51.12,
    "total_percipitation_in": 4.45,
    "total_snowfall_in": 5.5
  },
  {
    "year": 2012,
    "month": 5,
    "avg_max_temp_f": 75.45,
    "avg_min_temp_f": 46.57,
    "avg_temp_f": 61.16,
    "total_percipitation_in": 0.33,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 6,
    "avg_max_temp_f": 82.21,
    "avg_min_temp_f": 51.36,
    "avg_temp_f": 66.79,
    "total_percipitation_in": 0.67,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 7,
    "avg_max_temp_f": 89.3,
    "avg_min_temp_f": 57.4,
    "avg_temp_f": 73.35,
    "total_percipitation_in": 0.01,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 8,
    "avg_max_temp_f": 93.14,
    "avg_min_temp_f": 60.62,
    "avg_temp_f": 76.88,
    "total_percipitation_in": 0.06,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 9,
    "avg_max_temp_f": 87.41,
    "avg_min_temp_f": 56.1,
    "avg_temp_f": 71.76,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 10,
    "avg_max_temp_f": 72.04,
    "avg_min_temp_f": 44.89,
    "avg_temp_f": 58.46,
    "total_percipitation_in": 1.47,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 11,
    "avg_max_temp_f": 56.04,
    "avg_min_temp_f": 35.39,
    "avg_temp_f": 45.71,
    "total_percipitation_in": 5.06,
    "total_snowfall_in": 6.5
  },
  {
    "year": 2012,
    "month": 12,
    "avg_max_temp_f": 42.64,
    "avg_min_temp_f": 29.93,
    "avg_temp_f": 36.29,
    "total_percipitation_in": 11.91,
    "total_snowfall_in": 18.5
  },
  {
    "year": 2013,
    "month": 1,
    "avg_max_temp_f": 44.25,
    "avg_min_temp_f": 23.25,
    "avg_temp_f": 33.75,
    "total_percipitation_in": 0.91,
    "total_snowfall_in": 2
  },
  {
    "year": 2013,
    "month": 2,
    "avg_max_temp_f": 53.14,
    "avg_min_temp_f": 27.9,
    "avg_temp_f": 40.52,
    "total_percipitation_in": 0.5,
    "total_snowfall_in": 1.1
  },
  {
    "year": 2013,
    "month": 3,
    "avg_max_temp_f": 61.18,
    "avg_min_temp_f": 36.18,
    "avg_temp_f": 48.68,
    "total_percipitation_in": 2.99,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 4,
    "avg_max_temp_f": 67.76,
    "avg_min_temp_f": 41.24,
    "avg_temp_f": 54.5,
    "total_percipitation_in": 1.64,
    "total_snowfall_in": 0.5
  },
  {
    "year": 2013,
    "month": 5,
    "avg_max_temp_f": 73.55,
    "avg_min_temp_f": 47.86,
    "avg_temp_f": 60.7,
    "total_percipitation_in": 2.96,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 6,
    "avg_max_temp_f": 84.77,
    "avg_min_temp_f": 55.1,
    "avg_temp_f": 69.93,
    "total_percipitation_in": 0.16,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 7,
    "avg_max_temp_f": 93.69,
    "avg_min_temp_f": 61.81,
    "avg_temp_f": 77.75,
    "total_percipitation_in": 0.02,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 8,
    "avg_max_temp_f": 89.25,
    "avg_min_temp_f": 55.89,
    "avg_temp_f": 72.57,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 9,
    "avg_max_temp_f": 82,
    "avg_min_temp_f": 50.78,
    "avg_temp_f": 66.39,
    "total_percipitation_in": 0.92,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 10,
    "avg_max_temp_f": 69.5,
    "avg_min_temp_f": 39.5,
    "avg_temp_f": 54.5,
    "total_percipitation_in": 0.94,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 11,
    "avg_max_temp_f": 60.32,
    "avg_min_temp_f": 33.63,
    "avg_temp_f": 46.97,
    "total_percipitation_in": 0.73,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 12,
    "avg_max_temp_f": 48.81,
    "avg_min_temp_f": 24.95,
    "avg_temp_f": 36.88,
    "total_percipitation_in": 1.53,
    "total_snowfall_in": 10.5
  },
  {
    "year": 2014,
    "month": 1,
    "avg_max_temp_f": 57.13,
    "avg_min_temp_f": 31.32,
    "avg_temp_f": 44.23,
    "total_percipitation_in": 1.01,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 2,
    "avg_max_temp_f": 54.64,
    "avg_min_temp_f": 34.82,
    "avg_temp_f": 44.73,
    "total_percipitation_in": 5.47,
    "total_snowfall_in": 2
  },
  {
    "year": 2014,
    "month": 3,
    "avg_max_temp_f": 62.48,
    "avg_min_temp_f": 37.44,
    "avg_temp_f": 49.96,
    "total_percipitation_in": 3.89,
    "total_snowfall_in": 1
  },
  {
    "year": 2014,
    "month": 4,
    "avg_max_temp_f": 66.56,
    "avg_min_temp_f": 40.5,
    "avg_temp_f": 53.53,
    "total_percipitation_in": 2.81,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 5,
    "avg_max_temp_f": 75.83,
    "avg_min_temp_f": 46.83,
    "avg_temp_f": 61.33,
    "total_percipitation_in": 0.73,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 6,
    "avg_max_temp_f": 85.28,
    "avg_min_temp_f": 53.39,
    "avg_temp_f": 69.33,
    "total_percipitation_in": 0.2,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 7,
    "avg_max_temp_f": 91,
    "avg_min_temp_f": 60.93,
    "avg_temp_f": 75.97,
    "total_percipitation_in": 0.28,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 8,
    "avg_max_temp_f": 88.85,
    "avg_min_temp_f": 57.8,
    "avg_temp_f": 73.33,
    "total_percipitation_in": 0.15,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 9,
    "avg_max_temp_f": 85.04,
    "avg_min_temp_f": 53.5,
    "avg_temp_f": 69.27,
    "total_percipitation_in": 0.54,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 10,
    "avg_max_temp_f": 76.79,
    "avg_min_temp_f": 36.18,
    "avg_temp_f": 56.48,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 11,
    "avg_max_temp_f": 59.27,
    "avg_min_temp_f": 33.53,
    "avg_temp_f": 46.4,
    "total_percipitation_in": 2.98,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 12,
    "avg_max_temp_f": 48.86,
    "avg_min_temp_f": 32.79,
    "avg_temp_f": 40.82,
    "total_percipitation_in": 4.71,
    "total_snowfall_in": 1.2
  },
  {
    "year": 2015,
    "month": 1,
    "avg_max_temp_f": 56.96,
    "avg_min_temp_f": 30.39,
    "avg_temp_f": 43.68,
    "total_percipitation_in": 0.1,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 2,
    "avg_max_temp_f": 64.82,
    "avg_min_temp_f": 36,
    "avg_temp_f": 50.3,
    "total_percipitation_in": 1.63,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 3,
    "avg_max_temp_f": 67.29,
    "avg_min_temp_f": 38.33,
    "avg_temp_f": 52.81,
    "total_percipitation_in": 0.43,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 4,
    "avg_max_temp_f": 66.35,
    "avg_min_temp_f": 37.73,
    "avg_temp_f": 52.04,
    "total_percipitation_in": 3.15,
    "total_snowfall_in": 4.5
  },
  {
    "year": 2015,
    "month": 5,
    "avg_max_temp_f": 68.81,
    "avg_min_temp_f": 43.96,
    "avg_temp_f": 56.38,
    "total_percipitation_in": 1.97,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 6,
    "avg_max_temp_f": 87.97,
    "avg_min_temp_f": 57.23,
    "avg_temp_f": 72.6,
    "total_percipitation_in": 0.79,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 7,
    "avg_max_temp_f": 87.68,
    "avg_min_temp_f": 59.71,
    "avg_temp_f": 73.69,
    "total_percipitation_in": 2.58,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 8,
    "avg_max_temp_f": 91.39,
    "avg_min_temp_f": 58.68,
    "avg_temp_f": 75.03,
    "total_percipitation_in": 0.04,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 9,
    "avg_max_temp_f": 85.07,
    "avg_min_temp_f": 55.86,
    "avg_temp_f": 70.41,
    "total_percipitation_in": 0.15,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 10,
    "avg_max_temp_f": 73.26,
    "avg_min_temp_f": 46.17,
    "avg_temp_f": 59.93,
    "total_percipitation_in": 3.37,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 11,
    "avg_max_temp_f": 50.5,
    "avg_min_temp_f": 29.36,
    "avg_temp_f": 39.93,
    "total_percipitation_in": 3.74,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 12,
    "avg_max_temp_f": 43.42,
    "avg_min_temp_f": 24.65,
    "avg_temp_f": 34.03,
    "total_percipitation_in": 5.18,
    "total_snowfall_in": 0
  }
];

    return graphJson;
};


module.exports = graphStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36,"../stores/authorization-store":40}],43:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _lastError = null;

var loginFormStore = new Store();

loginFormStore.getLastError = function () {
    return _lastError;
};

loginFormStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _lastError = null;
            loginFormStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            _lastError = action.error;
            loginFormStore.emitChange();
            break;
    }
});

module.exports = loginFormStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36,"./authorization-store":40}],44:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _modalContent = null;

var modalStore = new Store();

modalStore.getModalContent = function () {
    return _modalContent;
};

modalStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.OPEN_MODAL:
            _modalContent = action.content;
            modalStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_MODAL:
        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            _modalContent = null;
            modalStore.emitChange();
            break;
    }
});

module.exports = modalStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36}],45:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _lastRegisterError = null;
var _lastDeregisterError = null;

var platformRegistrationStore = new Store();

platformRegistrationStore.getLastRegisterError = function () {
    return _lastRegisterError;
};

platformRegistrationStore.getLastDeregisterError = function () {
    return _lastDeregisterError;
};

platformRegistrationStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.REGISTER_PLATFORM_ERROR:
            _lastRegisterError = action.error;
            platformRegistrationStore.emitChange();
            break;

        case ACTION_TYPES.DEREGISTER_PLATFORM_ERROR:
            _lastDeregisterError = action.error;
            platformRegistrationStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_MODAL:
            _lastRegisterError = null;
            _lastDeregisterError = null;
            platformRegistrationStore.emitChange();
            break;
    }
});

module.exports = platformRegistrationStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36,"./authorization-store":40}],46:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _pointsOrder = 0;
var _devicesOrder = 1;
var _buildingsOrder = 2;
var _agentsOrder = 3;

var _items = {
    "platforms": {

        "4687fedc-65ba-43fe-21dc-098765bafedc": {
            "uuid": "4687fedc-65ba-43fe-21dc-098765bafedc",
            "name": "PNNL",
            "status": "GOOD",
            "type": "platform",
            "sortOrder": 0,
            "children": ["agents", "buildings", "points"],
            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc"],
            "points": {
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points"],
                "name": "Points",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _pointsOrder,
                "children": ["5461fedc-65ba-43fe-21dc-098765bafedl"],                    
                "5461fedc-65ba-43fe-21dc-098765bafedl":
                {
                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                    "name": "OutdoorAirTemperature",
                    "status": "GOOD",
                    "type": "point",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                }
            },
            "agents": {                
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents"],
                "name": "Agents",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _agentsOrder,
                "children": ["2461fedc-65ba-43fe-21dc-098765bafede", "7897fedc-65ba-43fe-21dc-098765bafedf"], 
                "2461fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                    "name": "Platform Agent",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents", "2461fedc-65ba-43fe-21dc-098765bafede"]
                },
                "7897fedc-65ba-43fe-21dc-098765bafedf":
                {
                    "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                    "name": "SqlHistorian",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents", "7897fedc-65ba-43fe-21dc-098765bafedf"]
                }
            },
            "buildings": {             
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                "name": "Buildings",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _buildingsOrder,
                "children": ["1111fedc-65ba-43fe-21dc-098765bafede"],
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "ISB1",
                    "status": "GOOD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "OutdoorAirTemperature",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingPower",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "status": "GOOD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["devices", "points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                "5461fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CoolingCall",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                                },
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "CondenserFanPower",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                }
                            },
                            "devices": {    
                                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices"],
                                "name": "Devices",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _devicesOrder,
                                "children": ["4488fedc-65ba-43fe-21dc-098765bafedl"],
                                "4488fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4488fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "Zone",
                                    "status": "GOOD",
                                    "type": "device",
                                    "sortOrder": 0,
                                    "children": ["points"],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl"],
                                    "points": {  
                                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                        "name": "Points",
                                        "status": "GOOD",
                                        "type": "type",
                                        "sortOrder": _pointsOrder,
                                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "FirstStageAuxilaryHeat",
                                            "status": "GOOD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                                        },
                                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "SecondStageAuxilaryHeat",
                                            "status": "GOOD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                        }
                                    }
                                }
                            }
                        }
                    }   
                }
            }
        },
        "9757fedc-65ba-43fe-21dc-098765bafedc":
        {
            "uuid": "9757fedc-65ba-43fe-21dc-098765bafedc",
            "name": "WSU",
            "status": "BAD",
            "type": "platform",
            "sortOrder": 0,
            "children": ["agents", "buildings"],
            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc"],
            "agents": {                
                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents"],
                "name": "Agents",
                "status": "GOOD",
                "type": "type",
                "sortOrder": _agentsOrder,
                "children": ["2461fedc-65ba-43fe-21dc-098765bafede", "7897fedc-65ba-43fe-21dc-098765bafedf"], 
                "2461fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                    "name": "Platform Agent",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents", "2461fedc-65ba-43fe-21dc-098765bafede"]
                },
                "7897fedc-65ba-43fe-21dc-098765bafedf":
                {
                    "uuid": "7897fedc-65ba-43fe-21dc-098765bafedf",
                    "name": "SqlHistorian",
                    "status": "GOOD",
                    "type": "agent",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents", "7897fedc-65ba-43fe-21dc-098765bafedf"]
                }
            },
            "buildings": {             
                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings"],
                "name": "Buildings",
                "status": "BAD",
                "type": "type",
                "sortOrder": _buildingsOrder,
                "children": ["1111fedc-65ba-43fe-21dc-098765bafede", "1333fedc-65ba-43fe-21dc-098765bafede"],
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "BSEL",
                    "status": "BAD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "status": "UNKNOWN",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingElectricity",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "LightingStatus",
                            "status": "UNKNOWN",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "status": "BAD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "AHU",
                            "status": "BAD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["devices", "points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["6451fedc-65ba-43fe-21dc-098765bafedl"],                                
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "DuctStaticPressureSetPoint",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                }
                            },
                            "devices": {    
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices"],
                                "name": "Devices",
                                "status": "BAD",
                                "type": "type",
                                "sortOrder": _devicesOrder,
                                "children": ["4488fedc-65ba-43fe-21dc-098765bafedl"],
                                "4488fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4488fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "Zone",
                                    "status": "BAD",
                                    "type": "device",
                                    "sortOrder": 0,
                                    "children": ["points"],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl"],
                                    "points": {  
                                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                        "name": "Points",
                                        "status": "BAD",
                                        "type": "type",
                                        "sortOrder": _pointsOrder,
                                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "TerminalBoxDamperCommand",
                                            "status": "BAD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                                        },
                                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "ZoneTemperature",
                                            "status": "GOOD",
                                            "type": "point",
                                            "sortOrder": 0,
                                            "children": [],
                                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                        }
                                    }
                                }
                            }
                        }
                    }   
                },
                "1333fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1333fedc-65ba-43fe-21dc-098765bafede",
                    "name": "CIC",
                    "status": "GOOD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingGas",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"]
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "OutdoorAirRelativeHumidity",
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "Chilled_Water_Distribution_System",
                            "status": "GOOD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["6451fedc-65ba-43fe-21dc-098765bafedl"],                                
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "NaturalGasEnergy",
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-098765bafedl"]
                                }
                            }
                        }
                    }   
                }
            }
        }
    }
};

var _expanded = false;
var _itemTypes = ["platforms", "buildings", "agents", "devices", "points"];

var platformsPanelItemsStore = new Store();


platformsPanelItemsStore.getItems = function (parent, parentPath) {

    var itemsList = [];
    var item = _items;

    if (parentPath !== null) // for everything but the top level, drill down to the parent
    {
        for (var i = 0; i < parentPath.length; i++)
        {
            if (item.hasOwnProperty(parentPath[i]))
            {
                item = item[parentPath[i]];
            }
        }
    
          
        for (var i = 0; i < item.children.length; i++)
        {           
            itemsList.push(item[item.children[i]]);
        }
            
    }
    else
    {
        for (var key in item[parent])
        {
            itemsList.push(item[parent][key]);
        }
    } 

    return itemsList;
};

platformsPanelItemsStore.getTreeCopy = function() {

    return JSON.parse(JSON.stringify(_items));
}

platformsPanelItemsStore.getFilteredItems = function (parent, filterTerm, filterStatus) {

    var compareFunct;
    var compareTerm;

    if (filterTerm === "")
    {
        compareFunct = function (parent, filterStatus)
        {
            if (parent.hasOwnProperty("status"))
            {
                return (parent.status !== filterStatus);                
            }
            else
            {
                return (filterStatus !== "UNKNOWN");
            }
        }

        compareTerm = filterStatus;
    }
    else if (filterStatus === "")
    {
        compareFunct = function (parent, filterTerm)
        {
            return (parent.name.indexOf(filterTerm) < 0);
        }

        compareTerm = filterTerm;
    }

    if (parent.children.length === 0)
    {
        if (compareFunct(parent, compareTerm))
        {
            return null;
        }
        else
        {
            return parent;
        }
    }
    else
    {
        var childrenToDelete = [];

        for (var i = 0; i < parent.children.length; i++)
        {
            var childString = parent.children[i];
            var filteredChild = platformsPanelItemsStore.getFilteredItems(parent[childString], filterTerm, filterStatus);

            if (filteredChild === null)
            {
                delete parent[childString];

                childrenToDelete.push(childString);
            }
        }
        
        for (var i = 0; i < childrenToDelete.length; i++)
        {
            var index = parent.children.indexOf(childrenToDelete[i]);
            parent.children.splice(index, 1);
        }

        if ((parent.children.length === 0) && (compareFunct(parent, compareTerm)))
        {
            parent = null;
        }
        else
        {
            if (parent.children.length > 0)
            {
                parent.expanded = true;
            }
        }

        return parent;
    }
};

platformsPanelItemsStore.getExpandedChildren = function (expandedOn, parent) {

    if (parent.children.length === 0)
    {
        return parent;
    }
    else
    {
        for (var i = 0; i < parent.children.length; i++)
        {
            var childString = parent.children[i];
            var expandedChild = platformsPanelItemsStore.getExpandedChildren(expandedOn, parent[childString]);
        }
        
        parent.expanded = expandedOn;

        return parent;
    }
};


platformsPanelItemsStore.getExpanded = function () {
    return _expanded;
};

platformsPanelItemsStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            
            var platforms = action.platforms;

            platforms.forEach(function (platform)
            {
                _items["platforms"][platform.uuid] = platform; 
                
                var platformItem = _items["platforms"][platform.uuid];
                platformItem.path = ["platforms", platform.uuid];
                // platformItem.status = "GOOD";
                platformItem.children = [];
                platformItem.type = "platform";
            });
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_BUILDING_STATUSES:
            // _items["platforms"][action.platform.uuid]["buildings"] = action.buildings;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][key]["children"] = ["agents", "devices"];                
            //     _items["platforms"][action.platform.uuid]["buildings"][key]["path"] = ["platforms", action.platform.uuid, "buildings"];
            // }
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.agents.length > 0)
            {
                platform.agents = {};
                platform.agents.path = platform.path.slice(0);
                platform.agents.path.push("agents");
                platform.agents.name = "Agents";
                platform.agents.children = [];
                platform.agents.type = "type";
                platform.agents.sortOrder = _agentsOrder;

                if (platform.children.indexOf("agents") < 0)
                {
                    platform.children.push("agents");
                }

                action.agents.forEach(function (agent)
                {
                    var agentProps = agent;
                    agentProps.path = platform.agents.path.slice(0);
                    agentProps.path.push(agent.uuid);
                    // agent.status = "GOOD";
                    agentProps.children = [];
                    agentProps.type = "agent";
                    agentProps.sortOrder = 0;
                    platform.agents.children.push(agent.uuid); 
                    platform.agents[agent.uuid] = agentProps;
                });

            }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:
            // _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"] = action.devices;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][key]["children"] = ["points"];                
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices"];
            // }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_POINT_STATUSES:
            // _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"] = action.points;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["children"] = [];
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices", action.device.uuid, "points"];
            // }

            platformsPanelItemsStore.emitChange();
            break;
    }
});

module.exports = platformsPanelItemsStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36}],47:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

// var _platforms = [
//             {
//                 "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
//                 "name": "PNNL",
//                 "status": "GOOD"
//             },
//             {
//                 "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
//                 "name": "UW",
//                 "status": "BAD"
//             },
//             {
//                 "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
//                 "name": "WSU",
//                 "status": "UNKNOWN"
//             }
//         ];;

var _expanded = null;

var platformsPanelStore = new Store();

// platformsPanelStore.getPlatforms = function () {
//     return _platforms;
// };

platformsPanelStore.getExpanded = function () {
    return _expanded;
};

platformsPanelStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.TOGGLE_PLATFORMS_PANEL:  
            (_expanded === null ? _expanded = true : _expanded = !_expanded);
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36}],48:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _platforms = null;
var _lastErrors = {};

var platformsStore = new Store();

platformsStore.getPlatform = function (uuid) {
    var foundPlatform = null;

    if (_platforms) {
        _platforms.some(function (platform) {
            if (platform.uuid === uuid) {
                foundPlatform = platform;
                return true;
            }
        });
    }

    return foundPlatform;
};

platformsStore.getPlatforms = function () {
    return _platforms;
};

platformsStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

platformsStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _platforms = null;
            platformsStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORMS:
            _platforms = action.platforms;
            platformsStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORM:
            platformsStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORM_ERROR:
            _lastErrors[action.platform.uuid] = action.error;
            platformsStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_PLATFORM_ERROR:
            delete _lastErrors[action.platform.uuid];
            platformsStore.emitChange();
            break;
    }
});

module.exports = platformsStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36,"../stores/authorization-store":40}],49:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var topicData = {};

var topicDataStore = new Store();

topicDataStore.getTopicData = function (platform, topic) {
    if (topicData[platform.uuid] && topicData[platform.uuid][topic]) {
        return topicData[platform.uuid][topic];
    }

    return null;
};

topicDataStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECEIVE_PLATFORM_TOPIC_DATA:
            topicData[action.platform.uuid] = topicData[action.platform.uuid] || {};
            topicData[action.platform.uuid][action.topic] = action.data;
            topicDataStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            topicData= {};
            topicDataStore.emitChange();
            break;
    }
});

module.exports = topicDataStore;


},{"../constants/action-types":31,"../dispatcher":32,"../lib/store":36,"./authorization-store":40}]},{},[1]);
