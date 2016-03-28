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
var PlatformCharts = require('./components/platform-charts');

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
        React.createElement(Router.Route, {name: "charts", path: "platform-charts", handler: checkAuth(PlatformCharts)}), 
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


},{"./components/dashboard":17,"./components/login-form":22,"./components/page-not-found":25,"./components/platform":29,"./components/platform-charts":27,"./components/platform-manager":28,"./components/platforms":32,"./stores/authorization-store":45,"react":undefined,"react-router":undefined}],2:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/rpc/exchange":39}],3:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var controlButtonActionCreators = {
	toggleTaptip: function (name) {
		dispatcher.dispatch({
			type: ACTION_TYPES.TOGGLE_TAPTIP,
			name: name,
		});
	},
	hideTaptip: function (name) {
		dispatcher.dispatch({
			type: ACTION_TYPES.HIDE_TAPTIP,
			name: name,
		});
	},
};



module.exports = controlButtonActionCreators;


},{"../constants/action-types":36,"../dispatcher":37}],4:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37}],5:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/rpc":40,"../stores/authorization-store":45}],6:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var rpc = require('../lib/rpc');

var platformChartActionCreators = {
	pinChart: function (chartKey) {
		dispatcher.dispatch({
			type: ACTION_TYPES.PIN_CHART,
			chartKey: chartKey,
		});
	},
	setType: function (chartKey, chartType) {
		dispatcher.dispatch({
			type: ACTION_TYPES.CHANGE_CHART_TYPE,
			chartKey: chartKey,
			chartType: chartType
		});
	},
	changeRefreshRate: function (rate, chartKey) {
		dispatcher.dispatch({
			type: ACTION_TYPES.CHANGE_CHART_REFRESH,
			rate: rate,
			chartKey: chartKey
		});
	},
	refreshChart: function (series) {

		var authorization = authorizationStore.getAuthorization();

		series.forEach(function (item) {

			if (item.parentType === "platform")
	        {
	            var authorization = authorizationStore.getAuthorization();

	            new rpc.Exchange({
	                method: 'platforms.uuid.' + item.parentUuid + '.historian.query',
	                params: {
	                    topic: item.topic,
	                    count: 20,
	                    order: 'LAST_TO_FIRST',
	                },
	                authorization: authorization,
	            }).promise
	                .then(function (result) {
	                	item.data = result.values;

	                    item.data.forEach(function (datum) {
	                        datum.name = item.name;
	                        datum.parent = item.parentPath;
                        	datum.uuid = item.uuid;
	                    });
	                    dispatcher.dispatch({
	                        type: ACTION_TYPES.REFRESH_CHART,
	                        item: item
	                    });
	                })
	                .catch(rpc.Error, handle401);
	        }  
	        else
	        {
	            if (item.uuid === "5461fedc-65ba-43fe-21dc-098765bafedl")
	            {
	                item.data = [['2016-02-19T01:00:31.630626',31.4],['2016-02-19T01:00:16.632151',23],['2016-02-19T01:00:01.627188',16.5],['2016-02-19T00:59:46.641500',42.8],['2016-02-19T00:59:31.643573',21.2],['2016-02-19T00:59:16.643254',9.3],['2016-02-19T00:59:01.639104',8.5],['2016-02-19T00:58:46.638238',16],['2016-02-19T00:58:31.633733',12.4],['2016-02-19T00:58:16.632418',23],['2016-02-19T00:58:01.630463',16.7],['2016-02-19T00:57:46.648439',9.1],['2016-02-19T00:57:31.640824',10.5],['2016-02-19T00:57:16.636578',8.2],['2016-02-19T00:57:01.644842',2.2],['2016-02-19T00:56:46.635059',2.5],['2016-02-19T00:56:31.639332',2.4],['2016-02-19T00:56:16.647604',2.3],['2016-02-19T00:56:01.643571',11.2],['2016-02-19T00:55:46.644522',9.8]];
	                item.data.forEach(function (datum) {
	                    datum.name = item.name;
	                    datum.parent = item.parentPath;
	                    datum.uuid = item.uuid;
	                });

	                dispatcher.dispatch({
	                    type: ACTION_TYPES.REFRESH_CHART,
	                    item: item
	                });
	            }
	            else if (item.uuid === "5461fedc-65ba-43fe-21dc-111765bafedl")
	            {
	                item.data = [['2016-02-19T01:00:31.630626',73.6],['2016-02-19T01:00:16.632151',71],['2016-02-19T01:00:01.627188',69.4],['2016-02-19T00:59:46.641500',60],['2016-02-19T00:59:31.643573',67],['2016-02-19T00:59:16.643254',68.6],['2016-02-19T00:59:01.639104',77],['2016-02-19T00:58:46.638238',83.5],['2016-02-19T00:58:31.633733',57.2],['2016-02-19T00:58:16.632418',78.7],['2016-02-19T00:58:01.630463',90.7],['2016-02-19T00:57:46.648439',91.5],['2016-02-19T00:57:31.640824',84],['2016-02-19T00:57:16.636578',87.6],['2016-02-19T00:57:01.644842',77],['2016-02-19T00:56:46.635059',83.3],['2016-02-19T00:56:31.639332',90.9],['2016-02-19T00:56:16.647604',89.5],['2016-02-19T00:56:01.643571',91.8],['2016-02-19T00:55:46.644522',97.7]];
	                item.data.forEach(function (datum) {
	                    datum.name = item.name;
	                    datum.parent = item.parentPath;
	                    datum.uuid = item.uuid;
	                });

	                dispatcher.dispatch({
	                    type: ACTION_TYPES.REFRESH_CHART,
	                    item: item
	                });
	            }
	        }
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
};

module.exports = platformChartActionCreators;


},{"../constants/action-types":36,"../dispatcher":37,"../lib/rpc":40,"../stores/authorization-store":45}],7:[function(require,module,exports){
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


},{"../action-creators/platform-action-creators":5,"../constants/action-types":36,"../dispatcher":37,"../lib/rpc":40,"../stores/authorization-store":45}],8:[function(require,module,exports){
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

    closePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.CLOSE_PLATFORMS_PANEL,
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

                platforms.forEach(function (platform, i) {
                    if (platform.name === null || platform.name === "")
                    {
                        platform.name = "vc" + (i + 1);
                    }
                });

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
                // loadPanelAgents(parent);
                loadPanelBuildings(parent);
                loadPanelPoints(parent);
                break;
            case "building":
                loadPanelDevices(parent);
                loadPanelPoints(parent);
                break;
            case "device":
                loadPanelPoints(parent);
                loadPanelDevices(parent);
                break;
            // case "type":

            //     for (var i = 0; i < parent.children.length; i++)
            //     {
            //         platformsPanelActionCreators.loadChildren(parent[parent.children[i]].type, parent[parent.children[i]]);
            //     }
                
            //     break;
            default:

                loadPanelChildren(parent);

                break;

        }


        function loadPanelChildren(parent) {
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PANEL_CHILDREN,
                platform: parent
            });    
        }

        function loadPanelPoints(parent) {

            var pointsList = [];

            if (parent.type === "platform")
            {
                pointsList = [

                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/guest_nice",
                        "name": "times_percent / guest_nice"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/system",
                        "name": "times_percent / system"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/percent",
                        "name": "cpu / percent"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/irq",
                        "name": "times_percent / irq"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/steal",
                        "name": "times_percent / steal"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/user",
                        "name": "times_percent / user"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/nice",
                        "name": "times_percent / nice"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/iowait",
                        "name": "times_percent / iowait"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/idle",
                        "name": "times_percent / idle"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/guest",
                        "name": "times_percent / guest"
                    },
                    {
                        "topic": "datalogger/log/platform/status/cpu/times_percent/softirq",
                        "name": "times_percent / softirq"
                    }
                ]
            }

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_POINT_STATUSES,
                parent: parent,
                points: pointsList
            });    
        }

        function loadPanelDevices(parent) {
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
                platform: parent
            });    
        }

        function loadPanelBuildings(parent) {
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_BUILDING_STATUSES,
                platform: parent
            });    
        }

        function loadPanelAgents(platform) {
        //     var authorization = authorizationStore.getAuthorization();

        //     new rpc.Exchange({
        //         method: 'platforms.uuid.' + platform.uuid + '.list_agents',
        //         authorization: authorization,
        //     }).promise
        //         .then(function (agentsList) {
                    
        //             dispatcher.dispatch({
        //                 type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
        //                 platform: platform,
        //                 agents: agentsList
        //             });

                    
        //         })
        //         .catch(rpc.Error, handle401);    
        // }
            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                platform: platform
            });
        }
    
    },

    loadFilteredItems: function (filterTerm, filterStatus)
    {
        dispatcher.dispatch({
            type: ACTION_TYPES.FILTER_ITEMS,
            filterTerm: filterTerm,
            filterStatus: filterStatus
        });
    },

    expandAll: function (itemPath) {

        dispatcher.dispatch({
            type: ACTION_TYPES.EXPAND_ALL,
            itemPath: itemPath
        });
    },

    toggleItem: function (itemPath) {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_ITEM,
            itemPath: itemPath
        });
    },

    checkItem: function (itemPath, checked) {

        dispatcher.dispatch({
            type: ACTION_TYPES.CHECK_ITEM,
            itemPath: itemPath,
            checked: checked
        });
    },

    addToChart: function(panelItem) {

        if (panelItem.parentType === "platform")
        {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + panelItem.parentUuid + '.historian.query',
                params: {
                    topic: panelItem.topic,
                    count: 20,
                    order: 'LAST_TO_FIRST',
                },
                authorization: authorization,
            }).promise
                .then(function (result) {
                    panelItem.data = result.values;

                    panelItem.data.forEach(function (datum) {
                        datum.name = panelItem.name;
                        datum.parent = panelItem.parentPath;
                        datum.uuid = panelItem.uuid;
                    });
                    dispatcher.dispatch({
                        type: ACTION_TYPES.ADD_TO_CHART,
                        panelItem: panelItem
                    });
                })
                .catch(rpc.Error, handle401);
        }  
        else
        {
            if (panelItem.uuid === "5461fedc-65ba-43fe-21dc-098765bafedl")
            {
                panelItem.data = [['2016-02-19T01:00:31.630626',31.4],['2016-02-19T01:00:16.632151',23],['2016-02-19T01:00:01.627188',16.5],['2016-02-19T00:59:46.641500',42.8],['2016-02-19T00:59:31.643573',21.2],['2016-02-19T00:59:16.643254',9.3],['2016-02-19T00:59:01.639104',8.5],['2016-02-19T00:58:46.638238',16],['2016-02-19T00:58:31.633733',12.4],['2016-02-19T00:58:16.632418',23],['2016-02-19T00:58:01.630463',16.7],['2016-02-19T00:57:46.648439',9.1],['2016-02-19T00:57:31.640824',10.5],['2016-02-19T00:57:16.636578',8.2],['2016-02-19T00:57:01.644842',2.2],['2016-02-19T00:56:46.635059',2.5],['2016-02-19T00:56:31.639332',2.4],['2016-02-19T00:56:16.647604',2.3],['2016-02-19T00:56:01.643571',11.2],['2016-02-19T00:55:46.644522',9.8]];
                panelItem.data.forEach(function (datum) {
                    datum.name = panelItem.name;
                    datum.parent = panelItem.parentPath;
                    datum.uuid = panelItem.uuid;
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });
            }
            else if (panelItem.uuid === "5461fedc-65ba-43fe-21dc-111765bafedl")
            {
                panelItem.data = [['2016-02-19T01:01:46.625663',73.6],['2016-02-19T01:01:31.633847',71],['2016-02-19T01:01:16.627160',69.4],['2016-02-19T01:01:01.639623',60],['2016-02-19T01:00:46.626307',67],['2016-02-19T01:00:31.630768',68.6],['2016-02-19T01:00:16.632203',77],['2016-02-19T01:00:01.627241',83.5],['2016-02-19T00:59:46.641688',57.2],['2016-02-19T00:59:31.643709',78.7],['2016-02-19T00:59:16.643448',90.7],['2016-02-19T00:59:01.640538',91.5],['2016-02-19T00:58:46.638353',84],['2016-02-19T00:58:31.633809',87.6],['2016-02-19T00:58:16.632515',77],['2016-02-19T00:58:01.630531',83.3],['2016-02-19T00:57:46.648567',90.9],['2016-02-19T00:57:31.640947',89.5],['2016-02-19T00:57:16.636686',91.8],['2016-02-19T00:57:01.645023',97.7]];
                panelItem.data.forEach(function (datum) {
                    datum.name = panelItem.name;
                    datum.parent = panelItem.parentPath;
                    datum.uuid = panelItem.uuid;
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });
            }
        }

    },

    removeFromChart: function(panelItem) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_CHART,
            panelItem: panelItem
        });  

    }
}




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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/rpc":40,"../stores/authorization-store":45}],9:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var actionStatusCreators = {
	openStatusIndicator: function (status, message) {
		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_STATUS,
			status: status,
			message: message,
		});
	},
	closeStatusIndicator: function () {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_STATUS,
		});
	},
};

module.exports = actionStatusCreators;


},{"../constants/action-types":36,"../dispatcher":37}],10:[function(require,module,exports){
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
        var agent = this.props.agent, status, action, remove, notAllowed;

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
                
                if (agent.vc_can_start)
                {
                    action = (
                        React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", onClick: this._onStart})
                    );
                }
                else
                {
                    action = (
                        React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", onClick: this._onStart, disabled: true})
                    );
                } 
            } else if (agent.return_code === null) {
                status = 'Running (PID ' + agent.process_id + ')';
                
                if (agent.vc_can_stop)
                {
                    action = (
                        React.createElement("input", {className: "button button--agent-action", type: "button", value: "Stop", onClick: this._onStop})
                    );
                }
                else
                {
                    action = (
                        React.createElement("input", {className: "button button--agent-action", type: "button", value: "Stop", onClick: this._onStop, disabled: true})
                    );
                }                 
            } else {
                status = 'Stopped (returned ' + agent.return_code + ')';
                
                if (agent.vc_can_restart)
                {
                    action = (
                        React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", onClick: this._onStart})
                    );
                }
                else
                {
                    action = (
                        React.createElement("input", {className: "button button--agent-action", type: "button", value: "Start", onClick: this._onStart, disabled: true})
                    );
                } 
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"./remove-agent-form":34,"react":undefined}],11:[function(require,module,exports){
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


},{"../action-creators/platform-action-creators":5,"../stores/topic-data-store":56,"./line-chart":21,"react":undefined}],12:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../stores/console-store":46,"react":undefined}],13:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"react":undefined}],14:[function(require,module,exports){
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


},{"./composer":12,"./conversation":16,"react":undefined}],15:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var controlButtonStore = require('../stores/control-button-store');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');


var ControlButton = React.createClass({displayName: "ControlButton",
	getInitialState: function () {
		var state = {};

		state.showTaptip = false;
		state.showTooltip = false;
		state.deactivateTooltip = false;
		state.taptipX = 0;
		state.taptipY = 0;
		state.selected = (this.props.selected === true);

		state.tooltipOffsetX = (this.props.hasOwnProperty("tooltip") ? 
									(this.props.tooltip.hasOwnProperty("xOffset") ? 
										this.props.tooltip.xOffset : 0) : 0);
		state.tooltipOffsetY = (this.props.hasOwnProperty("tooltip") ? 
									(this.props.tooltip.hasOwnProperty("yOffset") ? 
										this.props.tooltip.yOffset : 0) : 0);
		state.taptipOffsetX = (this.props.hasOwnProperty("taptip") ? 
									(this.props.taptip.hasOwnProperty("xOffset") ? 
										this.props.taptip.xOffset : 0) : 0);
		state.taptipOffsetY = (this.props.hasOwnProperty("taptip") ? 
									(this.props.taptip.hasOwnProperty("yOffset") ? 
										this.props.taptip.yOffset : 0) : 0);

		return state;
	},
    componentDidMount: function () {
        controlButtonStore.addChangeListener(this._onStoresChange);

        window.addEventListener('keydown', this._hideTaptip);
    },
    componentWillUnmount: function () {
        controlButtonStore.removeChangeListener(this._onStoresChange);

        window.removeEventListener('keydown', this._hideTaptip);
    },
    componentWillReceiveProps: function (nextProps) {
    	this.setState({ selected: (nextProps.selected === true) });

    	if (nextProps.selected === true) 
    	{
    		this.setState({ showTooltip: false });
    	}    	
    },
    _onStoresChange: function () {

    	var showTaptip = controlButtonStore.getTaptip(this.props.name);
    	
    	if (showTaptip !== null)
    	{
	    	if (showTaptip !== this.state.showTaptip)
	    	{
	    		this.setState({ showTaptip: showTaptip });	
	    	}

	    	this.setState({ selected: (showTaptip === true) }); 

	    	if (showTaptip === true)
	    	{
	    		this.setState({ showTooltip: false });	
	    	}
	    }
    },
	_showTaptip: function (evt) {

		if (!this.state.showTaptip)
		{
			this.setState({taptipX: evt.clientX - this.state.taptipOffsetX});
			this.setState({taptipY: evt.clientY - this.state.taptipOffsetY});
		}

		controlButtonActionCreators.toggleTaptip(this.props.name);
	},
	_hideTaptip: function (evt) {
		if (evt.keyCode === 27) 
		{
	        controlButtonActionCreators.hideTaptip(this.props.name);
        }
	},
    _showTooltip: function (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - this.state.tooltipOffsetX});
        this.setState({tooltipY: evt.clientY - this.state.tooltipOffsetY});
    },
    _hideTooltip: function () {
        this.setState({showTooltip: false});
    },
    render: function () {
        
        var taptip;
        var tooltip;
        var clickAction;
        var selectedStyle;

        var tooltipShow;
        var tooltipHide;

        if (this.state.selected === true || this.state.showTaptip === true)
        {
        	selectedStyle = {
	        	backgroundColor: "#ccc"
	        }
        }
        else if (this.props.tooltip)
        {
        	var tooltipStyle = {
	            display: (this.state.showTooltip ? "block" : "none"),
	            position: "absolute",
	            top: this.state.tooltipY + "px",
	            left: this.state.tooltipX + "px"
	        };

	        var toolTipClasses = (this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer");

	        tooltipShow = this._showTooltip;
	        tooltipHide = this._hideTooltip;

        	tooltip = (React.createElement("div", {className: toolTipClasses, 
                        style: tooltipStyle}, 
                        React.createElement("div", {className: "tooltip_inner"}, 
                            React.createElement("div", {className: "opaque_inner"}, 
                                this.props.tooltip.content
                            )
                        )
                    ))
        }
        

        if (this.props.taptip)
        {
        	var taptipStyle = {
		        display: (this.state.showTaptip ? "block" : "none"),
		        position: "absolute",
		        left: this.state.taptipX + "px",
		        top: this.state.taptipY + "px"
		    };

		    var tapTipClasses = "taptip_outer";

		    taptip = (
		    	React.createElement("div", {className: tapTipClasses, 
	                style: taptipStyle}, 
	                React.createElement("div", {className: "taptip_inner"}, 
	                    React.createElement("div", {className: "opaque_inner"}, 
	                        React.createElement("h4", null, this.props.taptip.title), 
	                        React.createElement("br", null), 
	                        this.props.taptip.content
	                    )
	                )
	            )
        	);

        	clickAction = (this.props.taptip.action ? this.props.taptip.action : this._showTaptip);
        }
        else if (this.props.clickAction)
        {
        	clickAction = this.props.clickAction;
        }

        return (
            React.createElement("div", {className: "inlineBlock"}, 
            	taptip, 
            	tooltip, 
                React.createElement("div", {className: "control_button", 
                    onClick: clickAction, 
                    onMouseEnter: tooltipShow, 
                    onMouseLeave: tooltipHide, 
                    style: selectedStyle}, 
                    React.createElement("div", {className: "centeredDiv"}, 
                        this.props.icon
                    )
                )
            )
        );
    },
});







module.exports = ControlButton;


},{"../action-creators/control-button-action-creators":3,"../stores/control-button-store":47,"react":undefined,"react-router":undefined}],16:[function(require,module,exports){
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


},{"../stores/console-store":46,"./exchange":20,"jquery":undefined,"react":undefined}],17:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var platformChartStore = require('../stores/platform-chart-store');
var Chart = require('./chart');
var EditChartForm = require('./edit-chart-form');
var modalActionCreators = require('../action-creators/modal-action-creators');

var PlatformChart = require('./platform-chart');

var Dashboard = React.createClass({displayName: "Dashboard",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoreChange);
        platformChartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoreChange);
        platformChartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onEditChartClick: function (platform, chart) {
        modalActionCreators.openModal(React.createElement(EditChartForm, {platform: platform, chart: chart}));
    },
    render: function () {
        var charts;
        
        var pinnedCharts = this.state.platformCharts; 

        var platformCharts = [];

        for (var key in pinnedCharts)
        {
            if (pinnedCharts[key].data.length > 0)
            {
                var platformChart = React.createElement(PlatformChart, {chart: pinnedCharts[key], chartKey: key, hideControls: true})
                platformCharts.push(platformChart);
            }
        }

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

            if (pinnedCharts.length === 0) {
                platformCharts = (
                    React.createElement("p", {className: "empty-help"}, 
                        "Pin a platform chart to have it appear on the dashboard"
                    )
                );
            }
        }

        return (
            React.createElement("div", {className: "view"}, 
                React.createElement("h2", null, "Dashboard"), 
                platformCharts
                
            )
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformsStore.getPlatforms(),
        platformCharts: platformChartStore.getPinnedCharts()
    };
}

module.exports = Dashboard;


},{"../action-creators/modal-action-creators":4,"../stores/platform-chart-store":50,"../stores/platforms-store":54,"./chart":11,"./edit-chart-form":19,"./platform-chart":26,"react":undefined,"react-router":undefined}],18:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-manager-action-creators":7,"../stores/platform-registration-store":51,"react":undefined}],19:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"react":undefined}],20:[function(require,module,exports){
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


},{"react":undefined}],21:[function(require,module,exports){
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


},{"d3":undefined,"moment":undefined,"react":undefined}],22:[function(require,module,exports){
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


},{"../action-creators/platform-manager-action-creators":7,"../stores/login-form-store":48,"react":undefined,"react-router":undefined}],23:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"react":undefined}],24:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var authorizationStore = require('../stores/authorization-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

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
        platformsPanelActionCreators.closePanel();
        platformManagerActionCreators.clearAuthorization();
    },
    render: function () {
        var navItems;

        if (this.state.loggedIn) {
            navItems = ['Dashboard', 'Platforms', 'Charts'].map(function (navItem) {
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


},{"../action-creators/platform-manager-action-creators":7,"../action-creators/platforms-panel-action-creators":8,"../stores/authorization-store":45,"react":undefined,"react-router":undefined}],25:[function(require,module,exports){
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


},{"react":undefined}],26:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');
var moment = require('moment');


var chartStore = require('../stores/platform-chart-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var ControlButton = require('./control-button');

var PlatformChart = React.createClass({displayName: "PlatformChart",
    getInitialState: function () {
        var state = {};

        state.refreshInterval = this.props.chart.refreshInterval;

        return state;
    },
    componentDidMount: function () {
        this._refreshChartTimeout = setTimeout(this._refreshChart, 0);
        platformChartStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        clearTimeout(this._refreshChartTimeout);
        platformChartStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        if (this.props.chart.data.length > 0)
        {
            var refreshInterval = platformChartStore.getRefreshRate(this.props.chart.data[0].name);

            if (refreshInterval !== this.state.refreshInterval)
            {
                this.setState({refreshInterval: refreshInterval}); 

                clearTimeout(this._refreshChartTimeout);
                this._refreshChartTimeout = setTimeout(this._refreshChart, refreshInterval);
            }
        }
        
    },
    _refreshChart: function () {
        
        if (this.props.hasOwnProperty("chart"))
        {
            platformChartActionCreators.refreshChart(
                this.props.chart.series
            );

            if (this.state.refreshInterval) {
                this._refreshChartTimeout = setTimeout(this._refreshChart, this.state.refreshInterval);
            }    
        }
    },
    render: function () {
        var chartData = this.props.chart; 
        var platformChart;

        if (chartData)
        {
            if (chartData.data.length > 0)
            {
                platformChart = (
                  React.createElement("div", {className: "platform-chart with-3d-shadow with-transitions"}, 
                      React.createElement("label", {className: "chart-title"}, chartData.data[0].name), 
                      React.createElement("div", null, 
                          React.createElement("div", {className: "viz"}, 
                               chartData.data.length != 0 ? 
                                    React.createElement(GraphLineChart, {
                                        data: chartData.data, 
                                        name: chartData.data[0].name, 
                                        hideControls: this.props.hideControls, 
                                        refreshInterval: this.props.chart.refreshInterval}) : null
                          ), 

                          React.createElement("br", null)
                      )
                  ))
            }
        }

        return (
            React.createElement("div", null, 
                platformChart
            )
        );
    },
});


var GraphLineChart = React.createClass({displayName: "GraphLineChart",

  getInitialState: function () {
      var state = {};
      state.chartName = this.props.name.replace(" / ", "_") + '_chart';
      state.type = platformChartStore.getType(this.props.name);
      state.lineChart = null;
      state.pinned = false;
      state.showTaptip = false;
      state.taptipX = 0;
      state.taptipY = 0;

      return state;
  },
  componentDidMount: function() {
      platformChartStore.addChangeListener(this._onStoresChange);
      var lineChart = this._drawLineChart(this.state.chartName, this.state.type, this._lineData(this._getNested(this.props.data)));
      this.setState({lineChart: lineChart});
  },
  componentWillUnmount: function () {
      platformChartStore.removeChangeListener(this._onStoresChange);
  },
  componentDidUpdate: function() {
      if (this.state.lineChart)
      {
          this._updateLineChart(this.state.lineChart, this.state.chartName, this._lineData(this._getNested(this.props.data)));
      }
  },
  _onStoresChange: function () {
      this.setState({pinned: platformChartStore.getPinned(this.props.name)});
      this.setState({type: platformChartStore.getType(this.props.name)});
  },
  _onChartChange: function (e) {
      var chartType = e.target.value;
      
      var lineChart = this._drawLineChart(this.state.chartName, chartType, this._lineData(this._getNested(this.props.data)));

      // this.setState({ type: e.target.value});
      this.setState({lineChart: lineChart});
      this.setState({showTaptip: false});

      platformChartActionCreators.setType(this.props.name, chartType);
  },
  _onPinToggle: function () {
      platformChartActionCreators.pinChart(this.props.name);
  },
  _onRefreshChange: function (e) {
      platformChartActionCreators.changeRefreshRate(e.target.value, this.props.name);
  },
  render: function() {

    var chartStyle = {
        width: "90%"
    }

    var svgStyle = {
      padding: "0px 50px"
    }

    var controlStyle = {
      width: "100%",
      textAlign: "left"
    }

    var pinClasses = ["chart-pin inlineBlock"];
    pinClasses.push(this.state.pinned ? "pinned-chart" : "unpinned-chart");
  
    var controlButtons;

    if (!this.props.hideControls)
    {
        var taptipX = 60;
        var taptipY = 120;

        var tooltipX = 20;
        var tooltipY = 60;

        var chartTypeSelect = (
            React.createElement("select", {
                onChange: this._onChartChange, 
                value: this.state.type, 
                autoFocus: true, 
                required: true
            }, 
                React.createElement("option", {value: "line"}, "Line"), 
                React.createElement("option", {value: "lineWithFocus"}, "Line with View Finder"), 
                React.createElement("option", {value: "stackedArea"}, "Stacked Area"), 
                React.createElement("option", {value: "cumulativeLine"}, "Cumulative Line")
            )
        );

        var chartTypeTaptip = { 
            "title": "Chart Type", 
            "content": chartTypeSelect,
            "xOffset": taptipX,
            "yOffset": taptipY
        };
        var chartTypeIcon = (
            React.createElement("i", {className: "fa fa-line-chart"})
        );
        var chartTypeTooltip = {
            "content": "Chart Type",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        var chartTypeControlButton = (
            React.createElement(ControlButton, {
                name: this.state.chartName + "_chartTypeControlButton", 
                taptip: chartTypeTaptip, 
                tooltip: chartTypeTooltip, 
                icon: chartTypeIcon})
        );

        
        var pinChartIcon = (
            React.createElement("div", {className: pinClasses.join(' ')}, 
                React.createElement("i", {className: "fa fa-thumb-tack"})
            )
        );
        var pinChartTooltip = {
            "content": "Pin to Dashboard",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        var pinChartControlButton = (
            React.createElement(ControlButton, {
                name: this.state.chartName + "_pinChartControlButton", 
                icon: pinChartIcon, 
                tooltip: pinChartTooltip, 
                clickAction: this._onPinToggle})
        );
        
        var refreshChart = (
            React.createElement("div", null, 
                React.createElement("input", {
                    type: "number", 
                    onChange: this._onRefreshChange, 
                    value: this.props.refreshInterval, 
                    min: "250", 
                    step: "1", 
                    placeholder: "disabled"}
                ), " (ms)", 
                React.createElement("br", null), 
                React.createElement("span", null, 
                    "Omit to disable"
                )
            )
        );

        var refreshChartTaptip = { 
            "title": "Refresh Rate", 
            "content": refreshChart,
            "xOffset": taptipX,
            "yOffset": taptipY
        };
        var refreshChartIcon = (
            React.createElement("i", {className: "fa fa-hourglass"})
        );
        var refreshChartTooltip = {
            "content": "Refresh Rate",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        var refreshChartControlButton = (
            React.createElement(ControlButton, {
                name: this.state.chartName + "_refreshChartControlButton", 
                taptip: refreshChartTaptip, 
                tooltip: refreshChartTooltip, 
                icon: refreshChartIcon})
        );

        var spaceStyle = {
            width: "20px",
            height: "2px"
        }

        controlButtons = (
            React.createElement("div", {className: "displayBlock", 
                style: controlStyle}, 
                pinChartControlButton, 
                chartTypeControlButton, 
                refreshChartControlButton, 
                React.createElement("div", {className: "inlineBlock", 
                      style: spaceStyle})
            )
        );
    }

    return (
      React.createElement("div", {className: "platform-line-chart", 
          style: chartStyle}, 
          React.createElement("svg", {id: this.state.chartName, style: svgStyle}), 
          controlButtons
      )
    );
  },
  _drawLineChart: function (elementParent, type, data) {
      
      var tickCount = 0;
      var lineChart;

      switch (type)
      {
          case "line":
              lineChart = nv.models.lineChart();
              break;
          case "lineWithFocus":
              lineChart = nv.models.lineWithFocusChart();
              break;
          case "stackedArea":
              lineChart = nv.models.stackedAreaChart();
              break;
          case "cumulativeLine":
              lineChart = nv.models.cumulativeLineChart();
              break;
      }

      lineChart.margin({left: 25, right: 25})
          .x(function(d) {return d.x})
          .y(function(d) {return d.y})
          .useInteractiveGuideline(true)
          .showYAxis(true)
          .showXAxis(true);
      lineChart.xAxis
        .tickFormat(function (d, i) {

            var tickValue;

            if (typeof i === "undefined")
            {
                if (tickCount === 0)
                {
                    tickValue = moment(d).fromNow();
                    tickCount++;
                }
                else if (tickCount === 1)
                {
                    tickValue = moment(d).fromNow();
                    tickCount = 0;
                }
            }
            else
            {
                tickValue = "";
            }

            return tickValue;
        })
        .staggerLabels(false);
      lineChart.yAxis
        .tickFormat(d3.format('.1f'));

      switch (type)
      {        
          case "lineWithFocus":            
              lineChart.x2Axis
                .tickFormat(function (d) {
                    return d3.time.format('%X')(new Date(d));
                });
              break;
      }

      d3.selectAll('#' + elementParent + ' > *').remove();
      d3.select('#' + elementParent)
        .datum(data)
        .call(lineChart);
      nv.utils.windowResize(function() { lineChart.update() });

      nv.addGraph(function() {
        return lineChart;
      });

      return lineChart;
    },
    _updateLineChart: function (lineChart, elementParent, data) {
      d3.select('#' + elementParent)
        .datum(data)
        .call(lineChart);
    },
    _getNested: function (data) {
      var keyYearMonth = d3.nest()
        .key(function(d){return d.parent; })
        .key(function(d){return d["0"]; });
      var keyedData = keyYearMonth.entries(
        data.map(function(d) {
          return d;
        })
      );
      return keyedData;
    },
    _lineData: function (data) {
      var colors = ['DarkOrange', 'ForestGreen', 'DeepPink', 'DarkViolet', 'Teal', 'Maroon', 'RoyalBlue', 'Silver', 'MediumPurple', 'Red', 'Lime', 'Tan', 'LightGoldenrodYellow', 'Turquoise', 'Pink', 'DeepSkyBlue', 'OrangeRed', 'LightGrey', 'Olive'];
      data = data.sort(function(a,b){ return a.key > b.key; });
      var lineDataArr = [];
      for (var i = 0; i <= data.length-1; i++) {
        var lineDataElement = [];
        var currentValues = data[i].values.sort(function(a,b){ return +a.key - +b.key; });
        for (var j = 0; j <= currentValues.length-1; j++) {
          lineDataElement.push({
            'x': +currentValues[j].key,
            'y': +currentValues[j].values[0][1]
          });
        }
        lineDataArr.push({
          key: data[i].key,
          color: colors[i],
          values: lineDataElement
        });
      }
      return lineDataArr;
    }
  
});




module.exports = PlatformChart;


},{"../action-creators/platform-chart-action-creators":6,"../stores/platform-chart-store":50,"./control-button":15,"d3":undefined,"moment":undefined,"nvd3":undefined,"react":undefined,"react-router":undefined}],27:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var PlatformChart = require('./platform-chart');

var chartStore = require('../stores/platform-chart-store');

var PlatformCharts = React.createClass({displayName: "PlatformCharts",
    getInitialState: function () {
        var state = {
            chartData: getChartsFromStores()
        };

        return state;
    },
    componentWillMount: function () {
        
    },
    componentDidMount: function () {
        chartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        chartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        var platformCharts = getChartsFromStores();

        this.setState({chartData: platformCharts});
    },
    render: function () {

        var chartData = this.state.chartData; 

        var platformCharts = [];

        for (var key in chartData)
        {
            if (chartData[key].data.length > 0)
            {
                var platformChart = React.createElement(PlatformChart, {key: key, chart: chartData[key], chartKey: key, hideControls: false})
                platformCharts.push(platformChart);
            }
        }

        if (platformCharts.length === 0)
        {
            var noCharts = React.createElement("div", null, "No charts have been loaded. Add charts by selecting points in the side panel.")
            platformCharts.push(noCharts);
        }

        return (
                React.createElement("div", null, 
                    React.createElement("div", {className: "view"}, 
                        React.createElement("h2", null, "Charts"), 
                        platformCharts
                    )
                )
        );
    },
});

function getChartsFromStores() {

    return chartStore.getData();
}

module.exports = PlatformCharts;


},{"../stores/platform-chart-store":50,"./platform-chart":26,"react":undefined,"react-router":undefined}],28:[function(require,module,exports){
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
var StatusIndicator = require('./status-indicator');
var statusIndicatorStore = require('../stores/status-indicator-store');

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
        statusIndicatorStore.addChangeListener(this._onStoreChange);
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
        statusIndicatorStore.removeChangeListener(this._onStoreChange);
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

        var statusIndicator;

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

        if (this.state.status) {
            statusIndicator = (
                React.createElement(StatusIndicator, null)
            );
        }

        return (
            React.createElement("div", {className: classes.join(' ')}, 
                statusIndicator, 
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
        status: statusIndicatorStore.getStatus(),
        statusMessage: statusIndicatorStore.getStatusMessage(),
    };
}

module.exports = PlatformManager;


},{"../action-creators/console-action-creators":2,"../action-creators/modal-action-creators":4,"../action-creators/platform-manager-action-creators":7,"../stores/authorization-store":45,"../stores/console-store":46,"../stores/modal-store":49,"../stores/platforms-panel-store":53,"../stores/status-indicator-store":55,"./console":14,"./modal":23,"./navigation":24,"./platforms-panel":31,"./status-indicator":35,"jquery":undefined,"react":undefined,"react-router":undefined}],29:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"../stores/platforms-store":54,"./agent-row":10,"./chart":11,"./confirm-form":13,"./edit-chart-form":19,"react":undefined,"react-router":undefined}],30:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');


var PlatformsPanelItem = React.createClass({displayName: "PlatformsPanelItem",
    getInitialState: function () {
        var state = {};
        
        state.showTooltip = false;
        state.tooltipX = null;
        state.tooltipY = null;
        state.checked = (this.props.panelItem.hasOwnProperty("checked") ? this.props.panelItem.checked : false);
        state.panelItem = this.props.panelItem;
        state.children = this.props.panelChildren;

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var panelItem = getItemFromStore(this.props.itemPath);
        var panelChildren = getChildrenFromStore(this.props.panelItem, this.props.itemPath)

        this.setState({panelItem: panelItem});
        this.setState({children: panelChildren});
        this.setState({checked: panelItem.checked});
    },
    _expandAll : function () {
        
        platformsPanelActionCreators.expandAll(this.props.itemPath);
    },
    _toggleItem: function () {

        if (this.state.panelItem.expanded === null)
        {
            platformsPanelActionCreators.loadChildren(this.props.panelItem.type, this.props.panelItem);
        }
        else
        {
            if (this.state.panelItem.expanded)
            {
                platformsPanelActionCreators.expandAll(this.props.itemPath);
            }
            else
            {
                platformsPanelActionCreators.toggleItem(this.props.itemPath);    
            }
        }
    },
    _checkItem: function (e) {

        var checked = e.target.checked;

        platformsPanelActionCreators.checkItem(this.props.itemPath, checked);

        this.setState({checked: checked});

        if (checked)
        {
            platformsPanelActionCreators.addToChart(this.props.panelItem);
        }
        else
        {
            platformsPanelActionCreators.removeFromChart(this.props.panelItem);
        }
    },
    _showTooltip: function (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 70});
    },
    _hideTooltip: function () {
        this.setState({showTooltip: false});
    },
    _moveTooltip: function (evt) {
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 70});
    },
    render: function () {
        var panelItem = this.state.panelItem;
        var itemPath = this.props.itemPath;
        var propChildren = this.state.children;
        var children;

        var visibleStyle = {};

        if (panelItem.visible !== true)
        {
            visibleStyle = {
                display: "none"
            }
        }

        var itemClasses;
        var arrowClasses = ["arrowButton", "noRotate"];

        var ChartCheckbox;

        if (["point"].indexOf(panelItem.type) > -1)
        {
            ChartCheckbox = (React.createElement("input", {className: "panelItemCheckbox", 
                                    type: "checkbox", 
                                    onChange: this._checkItem, 
                                    checked: this.state.checked}));
        }

        var tooltipStyle = {
            display: (panelItem.type !== "type" ? (this.state.showTooltip ? "block" : "none") : "none"),
            position: "absolute",
            top: this.state.tooltipY + "px",
            left: this.state.tooltipX + "px"
        };

        var toolTipClasses = (this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer");

        arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) );

        var arrowContent;
        var arrowContentStyle = {
            width: "14px"
        }

        if (panelItem.status === "GOOD")
        {
            arrowContent = React.createElement("span", {style: arrowContentStyle}, "▶");
        } 
        else if (panelItem.status === "BAD") 
        {
            arrowContent = React.createElement("span", {style: arrowContentStyle}, React.createElement("i", {className: "fa fa-minus-circle"}));
        }
        else
        {
            arrowContent = React.createElement("span", {style: arrowContentStyle}, "▬");
        }
          
        if (this.state.panelItem.expanded === true )
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
                        React.createElement(PlatformsPanelItem, {panelItem: propChild, itemPath: propChild.path, panelChildren: grandchildren})
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

        var itemClass = (!panelItem.hasOwnProperty("uuid") ? "item_type" : "item_label ");

        var listItem = 
                React.createElement("div", {className: itemClass}, 
                    panelItem.name
                );

        return (
            React.createElement("li", {
                key: panelItem.uuid, 
                className: "panel-item", 
                style: visibleStyle
            }, 
                React.createElement("div", {className: "platform-info"}, 
                    React.createElement("div", {className: arrowClasses.join(' '), 
                        onDoubleClick: this._expandAll, 
                        onClick: this._toggleItem}, 
                        arrowContent
                    ), 
                        React.createElement(Router.Link, {to: "charts"}, ChartCheckbox), 
                    React.createElement("div", {className: toolTipClasses, 
                        style: tooltipStyle}, 
                        React.createElement("div", {className: "tooltip_inner"}, 
                            React.createElement("div", {className: "opaque_inner"}, 
                                panelItem.uuid
                            )
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

function getChildrenFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getChildren(parentItem, parentPath);
}

function getItemFromStore(itemPath) {
    return platformsPanelItemsStore.getItem(itemPath);
}

module.exports = PlatformsPanelItem;


},{"../action-creators/platforms-panel-action-creators":8,"../stores/platforms-panel-items-store":52,"react":undefined,"react-router":undefined}],31:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var PlatformsPanelItem = require('./platforms-panel-item');
var ControlButton = require('./control-button');


var PlatformsPanel = React.createClass({displayName: "PlatformsPanel",
    getInitialState: function () {
        var state = {};
        state.platforms = [];     
        state.expanded = getExpandedFromStore();
        state.filterValue = "";
        state.filterStatus = "";

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
        platformsPanelActionCreators.loadFilteredItems(e.target.value, "");
        this.setState({ filterStatus: "" });
    },
    _onFilterGood: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "GOOD");
        this.setState({ filterStatus: "GOOD" });
        this.setState({ filterValue: "" });
    },
    _onFilterBad: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "BAD");
        this.setState({ filterStatus: "BAD" });
        this.setState({ filterValue: "" });
    },
    _onFilterUnknown: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "UNKNOWN");
        this.setState({ filterStatus: "UNKNOWN" });
        this.setState({ filterValue: "" });
    },
    _onFilterOff: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "");
        this.setState({ filterValue: "" });
        this.setState({ filterStatus: "" });
    },
    _togglePanel: function () {
        platformsPanelActionCreators.togglePanel();
    },
    render: function () {
        var platforms;
        
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

        var filterGood, filterBad, filterUnknown;
        filterGood = filterBad = filterUnknown = false;

        switch (this.state.filterStatus)
        {
            case "GOOD":
                filterGood = true;
                break;
            case "BAD":
                filterBad = true;
                break;
            case "UNKNOWN":
                filterUnknown = true;
                break;
        }

        var tooltipX = 60;
        var tooltipY = 190;

        var filterGoodIcon = (
            React.createElement("div", {className: "status-good"}, 
                React.createElement("span", null, "▶")
            )
        );
        var filterGoodTooltip = {
            "content": "Healthy",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterGoodControlButton = (
            React.createElement(ControlButton, {
                name: "filterGoodControlButton", 
                icon: filterGoodIcon, 
                selected: filterGood, 
                tooltip: filterGoodTooltip, 
                clickAction: this._onFilterGood})
        );

        var filterBadIcon = (
            React.createElement("div", {className: "status-bad"}, 
                React.createElement("i", {className: "fa fa-minus-circle"})
            )
        );
        var filterBadTooltip = {
            "content": "Unhealthy",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterBadControlButton = (
            React.createElement(ControlButton, {
                name: "filterBadControlButton", 
                icon: filterBadIcon, 
                selected: filterBad, 
                tooltip: filterBadTooltip, 
                clickAction: this._onFilterBad})
        );

        var filterUnknownIcon = (
            React.createElement("div", {className: "status-unknown"}, 
                React.createElement("span", null, "▬")
            )
        );
        var filterUnknownTooltip = {
            "content": "Unknown Status",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterUnknownControlButton = (
            React.createElement(ControlButton, {
                name: "filterUnknownControlButton", 
                icon: filterUnknownIcon, 
                selected: filterUnknown, 
                tooltip: filterUnknownTooltip, 
                clickAction: this._onFilterUnknown})
        );

        var filterOffIcon = (
            React.createElement("i", {className: "fa fa-ban"})
        );
        var filterOffTooltip = {
            "content": "Clear Filter",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterOffControlButton = (
            React.createElement(ControlButton, {
                name: "filterOffControlButton", 
                icon: filterOffIcon, 
                tooltip: filterOffTooltip, 
                clickAction: this._onFilterOff})
        );

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
                        React.createElement("div", {className: "inlineBlock"}, 
                            filterGoodControlButton, 
                            filterBadControlButton, 
                            filterUnknownControlButton, 
                            filterOffControlButton
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

function getPlatformsFromStore() {
    return platformsPanelItemsStore.getChildren("platforms", null);
};

function getExpandedFromStore() {
    return platformsPanelStore.getExpanded();
};

function getFilteredPlatforms(filterTerm, filterStatus, platforms) {
    return platformsPanelItemsStore.getFilteredItems(filterTerm, filterStatus, platforms);
}


module.exports = PlatformsPanel;


},{"../action-creators/platforms-panel-action-creators":8,"../stores/platforms-panel-items-store":52,"../stores/platforms-panel-store":53,"./control-button":15,"./platforms-panel-item":30,"react":undefined,"react-router":undefined}],32:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsStore = require('../stores/platforms-store');
var RegisterPlatformForm = require('../components/register-platform-form');
var StatusForm = require('../components/status-indicator');
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
    _onGoodStatusClick: function () {
        statusIndicatorActionCreators.openStatusIndicator("success", "nothing happened");
    },
    _onBadStatusClick: function () {
        statusIndicatorActionCreators.openStatusIndicator("error", "nothing happened");
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
                React.createElement("div", {className: "absolute_anchor"}, 
                    React.createElement("h2", null, "Platforms"), 
                    React.createElement("div", {className: "view__actions"}, 
                        React.createElement("button", {className: "button", onClick: this._onGoodStatusClick}, 
                            "Show Good Status"
                        ), 
                        " ", 
                        React.createElement("button", {className: "button", onClick: this._onBadStatusClick}, 
                            "Show Bad Status"
                        ), 
                        " ", 
                        React.createElement("button", {className: "button", onClick: this._onRegisterClick}, 
                            "Register platform"
                        )
                    ), 
                    platforms
                )
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


},{"../action-creators/modal-action-creators":4,"../action-creators/status-indicator-action-creators":9,"../components/deregister-platform-confirmation":18,"../components/register-platform-form":33,"../components/status-indicator":35,"../stores/platforms-store":54,"react":undefined,"react-router":undefined}],33:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformRegistrationStore = require('../stores/platform-registration-store');

var RegisterPlatformForm = React.createClass({displayName: "RegisterPlatformForm",
    getInitialState: function () {
        var state = getStateFromStores();
        
        state.method = 'discovery';

        state.name = state.discovery_address = state.ipaddress = state.serverKey = state.publicKey = state.secretKey = '';
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
        this.setState({ discovery_address: e.target.value });
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
    _toggleMethod: function (e) {
        this.setState({ method: (this.state.method === "discovery" ? "advanced" : "discovery") });
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmitDiscovery: function () {

        platformManagerActionCreators.registerInstance(
            this.state.name, 
            this.state.discovery_address);
        
    },
    _onSubmitAdvanced: function () {

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

        var registerForm;

        var submitMethod;

        switch (this.state.method)
        {
            case "discovery":
                submitMethod = this._onSubmitDiscovery;

                registerForm = (
                    React.createElement("div", null, 
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
                                    width: "70%"}, 
                                    React.createElement("label", {className: "formLabel"}, "Address"), 
                                    React.createElement("input", {
                                        className: "form__control form__control--block", 
                                        type: "text", 
                                        onChange: this._onAddressChange, 
                                        value: this.state.discovery_address, 
                                        required: true}
                                    )
                                )
                            )
                        ), 
                        
                        React.createElement("div", {className: "tableDiv"}, 
                            React.createElement("div", {className: "rowDiv"}, 
                                React.createElement("div", {className: "cellDiv firstCell"}, 
                                    React.createElement("div", {className: "form__link", 
                                        onClick: this._toggleMethod}, 
                                        React.createElement("a", null, "Advanced")
                                    )
                                ), 
                                React.createElement("div", {className: "cellDiv", 
                                    width: "70%"}, 
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
                                            disabled: !this.state.name || !this.state.discovery_address
                                        }, 
                                            "Register"
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
                break;
            case "advanced":

                submitMethod = this._onSubmitAdvanced;

                registerForm = (
                    React.createElement("div", null, 
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
                        
                        React.createElement("div", {className: "tableDiv"}, 
                            React.createElement("div", {className: "rowDiv"}, 
                                React.createElement("div", {className: "cellDiv firstCell"}, 
                                    React.createElement("div", {className: "form__link", 
                                        onClick: this._toggleMethod}, 
                                        React.createElement("a", null, "Discover")
                                    )
                                ), 
                                React.createElement("div", {className: "cellDiv", 
                                    width: "70%"}, 
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
                            )
                        )
                    )
                )
                break;
        }

        return (
            React.createElement("form", {className: "register-platform-form", onSubmit: submitMethod}, 
                React.createElement("h1", null, "Register platform"), 
                this.state.error && (
                    React.createElement("div", {className: "error"}, this.state.error.message)
                ), 
                registerForm

            )
        );
    },
});

function getStateFromStores() {
    return { error: platformRegistrationStore.getLastDeregisterError() };
}

module.exports = RegisterPlatformForm;


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-manager-action-creators":7,"../stores/platform-registration-store":51,"react":undefined}],34:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"react":undefined}],35:[function(require,module,exports){
'use strict';

var React = require('react');

var statusIndicatorCreators = require('../action-creators/status-indicator-action-creators');
var statusIndicatorStore = require('../stores/status-indicator-store');

var StatusIndicator = React.createClass({displayName: "StatusIndicator",

	getInitialState: function () {
        var state = getStateFromStores();

        state.errors = (state.status === "error");
        state.fadeOut = false;

        return state;
    },
    componentDidMount: function () {        
        if (!this.state.errors)
        {   
        	this.fadeTimer = setTimeout(this._fadeForClose, 4000);
            this.closeTimer = setTimeout(this._autoCloseOnSuccess, 5000);
        }
    },
    _fadeForClose: function () {
    	this.setState({ fadeOut: true });
    },
    _keepVisible: function (evt) {
    	if (this.fadeTimer)
    	{
    		this.setState({ fadeOut: false });

    		clearTimeout(this.fadeTimer);
    		clearTimeout(this.closeTimer);

    		evt.currentTarget.addEventListener("mouseleave", this._closeOnMouseOut);
    	}
    },
    _closeOnMouseOut: function () {
    	if (!this.state.errors)
        {   
        	this.fadeTimer = setTimeout(this._fadeForClose, 0);
            this.closeTimer = setTimeout(this._autoCloseOnSuccess, 1000);
        }
    },
    _autoCloseOnSuccess: function () {
    	statusIndicatorCreators.closeStatusIndicator();
    },
    _onCloseClick: function () {
        statusIndicatorCreators.closeStatusIndicator();
    },

	render: function () {
		var classes = ["status-indicator"];

		var green = "#A1D490";
		var red = "#CC5056";

		var displayButton = "none";
		var color = green;
        
        if (this.state.errors)
        {
			displayButton = "block";
			color = red;
        }
        else if (this.state.fadeOut)
        {
        	classes.push("hide-slow");
        }

        var buttonStyle = {			
			margin: "auto"
		};

		var colorStyle = {
			background: color,
			width: "100%",
			height: "2rem",
			margin: "0"
		}

		var buttonDivStyle = {
			width: "100%",
			height: "3rem",
			display: displayButton
		}

		var spacerStyle = {
			width: "100%",
			height: "2rem"
		}

		return (
		
        	React.createElement("div", {
        		className: classes.join(' '), 
        		onMouseEnter: this._keepVisible
        	}, 
				React.createElement("div", {style: colorStyle}), 
				React.createElement("br", null), 
				this.state.statusMessage, 
                React.createElement("div", {style: spacerStyle}), 
                React.createElement("div", {style: buttonDivStyle}, 
	                React.createElement("button", {
	                    className: "button", 
	                    style: buttonStyle, 
	                    onClick: this._onCloseClick
	                }, 
	                    "Close"
	                )
                )
			)
        
			
		);
	},
});

function getStateFromStores() {
    return {
        status: statusIndicatorStore.getStatus(),
        statusMessage: statusIndicatorStore.getStatusMessage(),
    };
}

module.exports = StatusIndicator;


},{"../action-creators/status-indicator-action-creators":9,"../stores/status-indicator-store":55,"react":undefined}],36:[function(require,module,exports){
'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
    OPEN_MODAL: null,
    CLOSE_MODAL: null,

    OPEN_STATUS: null,
    CLOSE_STATUS: null,

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
    CLOSE_PLATFORMS_PANEL: null,

    RECEIVE_AGENT_STATUSES: null,
    RECEIVE_DEVICE_STATUSES: null,
    RECEIVE_POINT_STATUSES: null,
    RECEIVE_BUILDING_STATUSES: null,

    RECEIVE_PANEL_CHILDREN: null,

    ADD_TO_CHART: null,
    REMOVE_FROM_CHART: null,
    PIN_CHART: null,
    CHANGE_CHART_TYPE: null,
    CHANGE_CHART_REFRESH: null,
    REFRESH_CHART: null,

    EXPAND_ALL: null,
    TOGGLE_ITEM: null,
    CHECK_ITEM: null,
    FILTER_ITEMS: null,

    // ADD_CONTROL_BUTTON: null,
    // REMOVE_CONTROL_BUTTON: null,
    TOGGLE_TAPTIP: null,
    HIDE_TAPTIP: null,


    RECEIVE_PLATFORM_TOPIC_DATA: null,
});


},{"react/lib/keyMirror":undefined}],37:[function(require,module,exports){
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


},{"../constants/action-types":36,"flux":undefined}],38:[function(require,module,exports){
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


},{}],39:[function(require,module,exports){
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


},{"../../constants/action-types":36,"../../dispatcher":37,"../xhr":43,"./error":38,"node-uuid":undefined}],40:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange'),
};


},{"./error":38,"./exchange":39}],41:[function(require,module,exports){
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


},{"events":undefined}],42:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;


},{}],43:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":42,"./request":44}],44:[function(require,module,exports){
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


},{"./error":42,"bluebird":undefined,"jquery":undefined}],45:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41}],46:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"../stores/authorization-store":45}],47:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _controlButtons = {};

var controlButtonStore = new Store();



controlButtonStore.getTaptip = function (name) {
    
    var showTaptip = null;

    if (_controlButtons.hasOwnProperty([name]))
    {
        if (_controlButtons[name].hasOwnProperty("showTaptip"))
        {
            showTaptip = _controlButtons[name].showTaptip;
        }
    }

    return showTaptip;
}

controlButtonStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.TOGGLE_TAPTIP:             

            var showTaptip;

            if (_controlButtons.hasOwnProperty(action.name))
            {
                _controlButtons[action.name].showTaptip = showTaptip = !_controlButtons[action.name].showTaptip;
            }
            else
            {
                _controlButtons[action.name] = { "showTaptip": true };
                showTaptip = true;
            }

            if (showTaptip === true) 
            {            
                //close other taptips    
                for (var key in _controlButtons)
                {
                    if (key !== action.name)
                    {
                        _controlButtons[key].showTaptip = false;
                    }
                }
            }

            controlButtonStore.emitChange();

            break;

        case ACTION_TYPES.HIDE_TAPTIP:             

            if (_controlButtons.hasOwnProperty(action.name))
            {
                if (_controlButtons[action.name].hasOwnProperty("showTaptip"))
                {
                    _controlButtons[action.name].showTaptip = false;
                    // delete _controlButtons[action.name];   
                }
            }

            controlButtonStore.emitChange();

            break;
    } 

    
    
});



module.exports = controlButtonStore;


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"../stores/authorization-store":45}],48:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"./authorization-store":45}],49:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41}],50:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _chartData = {};

var chartStore = new Store();

chartStore.getPinnedCharts = function () {
    var pinnedCharts = [];

    for (var key in _chartData)
    {
        if (_chartData[key].hasOwnProperty("pinned") && _chartData[key].pinned === true)
        {
            pinnedCharts.push(_chartData[key]);
        }
    }

    return pinnedCharts;
};

chartStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

chartStore.getData = function () {
    return _chartData;
}

chartStore.getPinned = function (chartKey) {
    return _chartData[chartKey].pinned;
}

chartStore.getType = function (chartKey) {
    var type = "line";

    if (_chartData[chartKey].hasOwnProperty("type"))
    {
        type = _chartData[chartKey].type;
    }

    return type;
}

chartStore.getRefreshRate = function (chartKey) {
    return _chartData[chartKey].refreshInterval;
}

chartStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.ADD_TO_CHART:             

            if (_chartData.hasOwnProperty(action.panelItem.name))
            {
                insertSeries(action.panelItem);
                chartStore.emitChange();
            }
            else
            {
                if (action.panelItem.hasOwnProperty("data"))
                {
                    // _chartData[action.panelItem.name] = JSON.parse(JSON.stringify(action.panelItem.data));
                    
                    var chartObj = {
                        refreshInterval: 15000,
                        pinned: false, 
                        data: convertTimeToSeconds(action.panelItem.data),
                        series: [
                            { 
                                name: action.panelItem.name, 
                                uuid: action.panelItem.uuid, 
                                parentUuid: action.panelItem.parentUuid,
                                parentType: action.panelItem.parentType,
                                parentPath: action.panelItem.parentPath,
                                topic: action.panelItem.topic 
                            }
                        ]
                    };

                    _chartData[action.panelItem.name] = chartObj;
                    chartStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.REMOVE_FROM_CHART:
            
            removeSeries(action.panelItem.name, action.panelItem.uuid);
            chartStore.emitChange();

            break;

        case ACTION_TYPES.REFRESH_CHART:

            removeSeries(action.item.name, action.item.uuid);
            insertSeries(action.item);
            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_REFRESH:

            if (_chartData[action.chartKey].hasOwnProperty("refreshInterval"))
            {
                _chartData[action.chartKey].refreshInterval = action.rate;
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.PIN_CHART:

            if (_chartData[action.chartKey].hasOwnProperty("pinned"))
            {
                _chartData[action.chartKey].pinned = !_chartData[action.chartKey].pinned;
            }
            else
            {
                _chartData[action.chartKey].pinned = true;   
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_TYPE:

            if (_chartData[action.chartKey].type !== action.chartType)
            {
                _chartData[action.chartKey].type = action.chartType;
            }

            chartStore.emitChange();

            break;
    } 

    function insertSeries(item) {

        var chartItems = _chartData[item.name].data.filter(function (datum) { 
            return datum.uuid === item.uuid 
        });

        if (chartItems.length === 0)
        {
            if (item.hasOwnProperty("data"))
            {
                _chartData[item.name].data = _chartData[item.name].data.concat(convertTimeToSeconds(item.data));
                _chartData[item.name].series.push(
                    { 
                        name: item.name, 
                        uuid: item.uuid, 
                        parentUuid: item.parentUuid,
                        parentType: item.parentType,
                        parentPath: item.parentPath,
                        topic: item.topic  
                    }
                );
            }
        }

    }

    function removeSeries(name, uuid) {

        if (_chartData[name].data.length > 0)
        {
            for (var i = _chartData[name].data.length - 1; i >= 0; i--)
            {
                if (_chartData[name].data[i].uuid === uuid)
                {
                    _chartData[name].data.splice(i, 1);
                }                    
            }

            for (var i = 0; i < _chartData[name].series.length; i++)
            {
                if (_chartData[name].series[i].uuid === uuid)
                {
                    _chartData[name].series.splice(i, 1);

                    break;
                }
            }
        }
    }

    function convertTimeToSeconds(data) {
        var dataList = [];

        for (var key in data)
        {
            var newItem = {};

            for (var skey in data[key])
            {
                var value = data[key][skey];
                
                if (skey === "0" && typeof value === 'string' &&
                    Date.parse(value + 'Z')) {
                    value = Date.parse(value + 'Z');
                    // initialState.xDates = true;
                }

                newItem[skey] = value;    
            }

            dataList.push(newItem);
        }

        return dataList;
    }
    
});



module.exports = chartStore;


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"../stores/authorization-store":45}],51:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"./authorization-store":45}],52:[function(require,module,exports){
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
            "expanded": null,
            "visible": true,
            "status": "GOOD",
            "type": "platform",
            "sortOrder": 0,
            "children": ["agents", "buildings", "points"],
            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc"],
            "points": {
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points"],
                "name": "Points",
                "expanded": null,
                "visible": true,
                "status": "GOOD",
                "type": "type",
                "sortOrder": _pointsOrder,
                "children": ["5461fedc-65ba-43fe-21dc-000765bafedl"],                    
                "5461fedc-65ba-43fe-21dc-000765bafedl":
                {
                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                    "name": "OutdoorAirTemperature",
                    "expanded": null,
                    "visible": true,
                    "status": "GOOD",
                    "type": "point",
                    "sortOrder": 0,
                    "children": [],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "points", "5461fedc-65ba-43fe-21dc-000765bafedl"],
                    "data": [
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 1,
                                    "avg_max_temp_f": 46.83,
                                    "avg_min_temp_f": 28.1,
                                    "avg_temp_f": 37.47,
                                    "total_percipitation_in": 2.35,
                                    "total_snowfall_in": 9.6
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 2,
                                    "avg_max_temp_f": 47.58,
                                    "avg_min_temp_f": 26.35,
                                    "avg_temp_f": 36.96,
                                    "total_percipitation_in": 7.61,
                                    "total_snowfall_in": 25.5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 3,
                                    "avg_max_temp_f": 51.45,
                                    "avg_min_temp_f": 31.39,
                                    "avg_temp_f": 41.42,
                                    "total_percipitation_in": 11.74,
                                    "total_snowfall_in": 39.6
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 4,
                                    "avg_max_temp_f": 61.5,
                                    "avg_min_temp_f": 35.13,
                                    "avg_temp_f": 48.32,
                                    "total_percipitation_in": 1.44,
                                    "total_snowfall_in": 2.3
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 5,
                                    "avg_max_temp_f": 64.9,
                                    "avg_min_temp_f": 40.68,
                                    "avg_temp_f": 52.79,
                                    "total_percipitation_in": 2.17,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 6,
                                    "avg_max_temp_f": 73.79,
                                    "avg_min_temp_f": 48.18,
                                    "avg_temp_f": 60.98,
                                    "total_percipitation_in": 2.06,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 7,
                                    "avg_max_temp_f": 85.07,
                                    "avg_min_temp_f": 56.1,
                                    "avg_temp_f": 70.58,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 8,
                                    "avg_max_temp_f": 88.1,
                                    "avg_min_temp_f": 56.45,
                                    "avg_temp_f": 72.28,
                                    "total_percipitation_in": 0.15,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 9,
                                    "avg_max_temp_f": 84.47,
                                    "avg_min_temp_f": 54.13,
                                    "avg_temp_f": 69.3,
                                    "total_percipitation_in": 3.42,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 10,
                                    "avg_max_temp_f": 71.14,
                                    "avg_min_temp_f": 43.54,
                                    "avg_temp_f": 57.34,
                                    "total_percipitation_in": 2.8,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 11,
                                    "avg_max_temp_f": 53.62,
                                    "avg_min_temp_f": 32.07,
                                    "avg_temp_f": 42.62,
                                    "total_percipitation_in": 1.07,
                                    "total_snowfall_in": 5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "PNNL",
                                    "month": 12,
                                    "avg_max_temp_f": 48.97,
                                    "avg_min_temp_f": 25.42,
                                    "avg_temp_f": 37.19,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                }
                            ]
                }
            },
            "agents": {                
                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "agents"],
                "name": "Agents",
                "expanded": null,
                "visible": true,
                "status": "GOOD",
                "type": "type",
                "sortOrder": _agentsOrder,
                "children": ["2461fedc-65ba-43fe-21dc-098765bafede", "7897fedc-65ba-43fe-21dc-098765bafedf"], 
                "2461fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                    "name": "Platform Agent",
                    "expanded": null,
                    "visible": true,
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
                    "expanded": null,
                    "visible": true,
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
                "expanded": null,
                "visible": true,
                "status": "GOOD",
                "type": "type",
                "sortOrder": _buildingsOrder,
                "children": ["1111fedc-65ba-43fe-21dc-098765bafede"],
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "ISB1",
                    "expanded": null,
                    "visible": true,
                    "status": "GOOD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "expanded": null,
                        "visible": true,
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-111765bafedl", "6451fedc-65ba-43fe-21dc-000765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-111765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                            "name": "OutdoorAirTemperature",
                            "expanded": null,
                            "visible": true,
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-111765bafedl"],
                            "parentPath": "PNNL > ISB1",
                            "parentType": "building",
                            "parentUuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                            "data": [
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 1,
                                    "avg_max_temp_f": 44.25,
                                    "avg_min_temp_f": 23.25,
                                    "avg_temp_f": 33.75,
                                    "total_percipitation_in": 0.91,
                                    "total_snowfall_in": 2
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 2,
                                    "avg_max_temp_f": 53.14,
                                    "avg_min_temp_f": 27.9,
                                    "avg_temp_f": 40.52,
                                    "total_percipitation_in": 0.5,
                                    "total_snowfall_in": 1.1
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 3,
                                    "avg_max_temp_f": 61.18,
                                    "avg_min_temp_f": 36.18,
                                    "avg_temp_f": 48.68,
                                    "total_percipitation_in": 2.99,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 4,
                                    "avg_max_temp_f": 67.76,
                                    "avg_min_temp_f": 41.24,
                                    "avg_temp_f": 54.5,
                                    "total_percipitation_in": 1.64,
                                    "total_snowfall_in": 0.5
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 5,
                                    "avg_max_temp_f": 73.55,
                                    "avg_min_temp_f": 47.86,
                                    "avg_temp_f": 60.7,
                                    "total_percipitation_in": 2.96,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 6,
                                    "avg_max_temp_f": 84.77,
                                    "avg_min_temp_f": 55.1,
                                    "avg_temp_f": 69.93,
                                    "total_percipitation_in": 0.16,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 7,
                                    "avg_max_temp_f": 93.69,
                                    "avg_min_temp_f": 61.81,
                                    "avg_temp_f": 77.75,
                                    "total_percipitation_in": 0.02,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 8,
                                    "avg_max_temp_f": 89.25,
                                    "avg_min_temp_f": 55.89,
                                    "avg_temp_f": 72.57,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 9,
                                    "avg_max_temp_f": 82,
                                    "avg_min_temp_f": 50.78,
                                    "avg_temp_f": 66.39,
                                    "total_percipitation_in": 0.92,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 10,
                                    "avg_max_temp_f": 69.5,
                                    "avg_min_temp_f": 39.5,
                                    "avg_temp_f": 54.5,
                                    "total_percipitation_in": 0.94,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 11,
                                    "avg_max_temp_f": 60.32,
                                    "avg_min_temp_f": 33.63,
                                    "avg_temp_f": 46.97,
                                    "total_percipitation_in": 0.73,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-111765bafedl",
                                    "name": "OutdoorAirTemperature",
                                    "parent": "ISB1",
                                    "month": 12,
                                    "avg_max_temp_f": 48.81,
                                    "avg_min_temp_f": 24.95,
                                    "avg_temp_f": 36.88,
                                    "total_percipitation_in": 1.53,
                                    "total_snowfall_in": 10.5
                                }
                            ]
                        },
                        "6451fedc-65ba-43fe-21dc-000765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                            "name": "WholeBuildingPower",
                            "expanded": null,
                            "visible": true,
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "6451fedc-65ba-43fe-21dc-000765bafedl"],
                            "data": [
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 1,
                                    "avg_max_temp_f": 44.25,
                                    "avg_min_temp_f": 23.25,
                                    "avg_temp_f": 33.75,
                                    "total_percipitation_in": 0.91,
                                    "total_snowfall_in": 2
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 2,
                                    "avg_max_temp_f": 53.14,
                                    "avg_min_temp_f": 27.9,
                                    "avg_temp_f": 40.52,
                                    "total_percipitation_in": 0.5,
                                    "total_snowfall_in": 1.1
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 3,
                                    "avg_max_temp_f": 61.18,
                                    "avg_min_temp_f": 36.18,
                                    "avg_temp_f": 48.68,
                                    "total_percipitation_in": 2.99,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 4,
                                    "avg_max_temp_f": 67.76,
                                    "avg_min_temp_f": 41.24,
                                    "avg_temp_f": 54.5,
                                    "total_percipitation_in": 1.64,
                                    "total_snowfall_in": 0.5
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 5,
                                    "avg_max_temp_f": 73.55,
                                    "avg_min_temp_f": 47.86,
                                    "avg_temp_f": 60.7,
                                    "total_percipitation_in": 2.96,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 6,
                                    "avg_max_temp_f": 84.77,
                                    "avg_min_temp_f": 55.1,
                                    "avg_temp_f": 69.93,
                                    "total_percipitation_in": 0.16,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 7,
                                    "avg_max_temp_f": 93.69,
                                    "avg_min_temp_f": 61.81,
                                    "avg_temp_f": 77.75,
                                    "total_percipitation_in": 0.02,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 8,
                                    "avg_max_temp_f": 89.25,
                                    "avg_min_temp_f": 55.89,
                                    "avg_temp_f": 72.57,
                                    "total_percipitation_in": 0,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 9,
                                    "avg_max_temp_f": 82,
                                    "avg_min_temp_f": 50.78,
                                    "avg_temp_f": 66.39,
                                    "total_percipitation_in": 0.92,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 10,
                                    "avg_max_temp_f": 69.5,
                                    "avg_min_temp_f": 39.5,
                                    "avg_temp_f": 54.5,
                                    "total_percipitation_in": 0.94,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 11,
                                    "avg_max_temp_f": 60.32,
                                    "avg_min_temp_f": 33.63,
                                    "avg_temp_f": 46.97,
                                    "total_percipitation_in": 0.73,
                                    "total_snowfall_in": 0
                                },
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-000765bafedl",
                                    "name": "WholeBuildingPower",
                                    "parent": "ISB1",
                                    "month": 12,
                                    "avg_max_temp_f": 48.81,
                                    "avg_min_temp_f": 24.95,
                                    "avg_temp_f": 36.88,
                                    "total_percipitation_in": 1.53,
                                    "total_snowfall_in": 10.5
                                }
                            ]
                        }
                    },
                    "devices": {       
                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices"],
                        "name": "Devices",
                        "expanded": null,
                        "visible": true,
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "RTU1",
                            "expanded": null,
                            "visible": true,
                            "status": "GOOD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["devices", "points"],
                            "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "expanded": null,
                                "visible": true,
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["5461fedc-65ba-43fe-21dc-222765bafedl", "6451fedc-65ba-43fe-21dc-11165bafedl"],
                                "5461fedc-65ba-43fe-21dc-222765bafedl":
                                {
                                    "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                    "name": "CoolingCall",
                                    "expanded": null,
                                    "visible": true,
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "5461fedc-65ba-43fe-21dc-222765bafedl"],
                                    "data": [
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 1,
                                            "avg_max_temp_f": 57.13,
                                            "avg_min_temp_f": 31.32,
                                            "avg_temp_f": 44.23,
                                            "total_percipitation_in": 1.01,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 2,
                                            "avg_max_temp_f": 54.64,
                                            "avg_min_temp_f": 34.82,
                                            "avg_temp_f": 44.73,
                                            "total_percipitation_in": 5.47,
                                            "total_snowfall_in": 2
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 3,
                                            "avg_max_temp_f": 62.48,
                                            "avg_min_temp_f": 37.44,
                                            "avg_temp_f": 49.96,
                                            "total_percipitation_in": 3.89,
                                            "total_snowfall_in": 1
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 4,
                                            "avg_max_temp_f": 66.56,
                                            "avg_min_temp_f": 40.5,
                                            "avg_temp_f": 53.53,
                                            "total_percipitation_in": 2.81,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 5,
                                            "avg_max_temp_f": 75.83,
                                            "avg_min_temp_f": 46.83,
                                            "avg_temp_f": 61.33,
                                            "total_percipitation_in": 0.73,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 6,
                                            "avg_max_temp_f": 85.28,
                                            "avg_min_temp_f": 53.39,
                                            "avg_temp_f": 69.33,
                                            "total_percipitation_in": 0.2,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 7,
                                            "avg_max_temp_f": 91,
                                            "avg_min_temp_f": 60.93,
                                            "avg_temp_f": 75.97,
                                            "total_percipitation_in": 0.28,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 8,
                                            "avg_max_temp_f": 88.85,
                                            "avg_min_temp_f": 57.8,
                                            "avg_temp_f": 73.33,
                                            "total_percipitation_in": 0.15,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 9,
                                            "avg_max_temp_f": 85.04,
                                            "avg_min_temp_f": 53.5,
                                            "avg_temp_f": 69.27,
                                            "total_percipitation_in": 0.54,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 10,
                                            "avg_max_temp_f": 76.79,
                                            "avg_min_temp_f": 36.18,
                                            "avg_temp_f": 56.48,
                                            "total_percipitation_in": 0,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 11,
                                            "avg_max_temp_f": 59.27,
                                            "avg_min_temp_f": 33.53,
                                            "avg_temp_f": 46.4,
                                            "total_percipitation_in": 2.98,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-222765bafedl",
                                            "name": "CoolingCall",
                                            "parent": "RTU1",
                                            "month": 12,
                                            "avg_max_temp_f": 48.86,
                                            "avg_min_temp_f": 32.79,
                                            "avg_temp_f": 40.82,
                                            "total_percipitation_in": 4.71,
                                            "total_snowfall_in": 1.2
                                        }
                                    ]
                                },
                                "6451fedc-65ba-43fe-21dc-11165bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                    "name": "CondenserFanPower",
                                    "expanded": null,
                                    "visible": true,
                                    "status": "GOOD",
                                    "type": "point",
                                    "sortOrder": 0,
                                    "children": [],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points", "6451fedc-65ba-43fe-21dc-11165bafedl"],
                                    "data": [
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 1,
                                            "avg_max_temp_f": 56.96,
                                            "avg_min_temp_f": 30.39,
                                            "avg_temp_f": 43.68,
                                            "total_percipitation_in": 0.1,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 2,
                                            "avg_max_temp_f": 64.82,
                                            "avg_min_temp_f": 36,
                                            "avg_temp_f": 50.3,
                                            "total_percipitation_in": 1.63,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 3,
                                            "avg_max_temp_f": 67.29,
                                            "avg_min_temp_f": 38.33,
                                            "avg_temp_f": 52.81,
                                            "total_percipitation_in": 0.43,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 4,
                                            "avg_max_temp_f": 66.35,
                                            "avg_min_temp_f": 37.73,
                                            "avg_temp_f": 52.04,
                                            "total_percipitation_in": 3.15,
                                            "total_snowfall_in": 4.5
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 5,
                                            "avg_max_temp_f": 68.81,
                                            "avg_min_temp_f": 43.96,
                                            "avg_temp_f": 56.38,
                                            "total_percipitation_in": 1.97,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 6,
                                            "avg_max_temp_f": 87.97,
                                            "avg_min_temp_f": 57.23,
                                            "avg_temp_f": 72.6,
                                            "total_percipitation_in": 0.79,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 7,
                                            "avg_max_temp_f": 87.68,
                                            "avg_min_temp_f": 59.71,
                                            "avg_temp_f": 73.69,
                                            "total_percipitation_in": 2.58,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 8,
                                            "avg_max_temp_f": 91.39,
                                            "avg_min_temp_f": 58.68,
                                            "avg_temp_f": 75.03,
                                            "total_percipitation_in": 0.04,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 9,
                                            "avg_max_temp_f": 85.07,
                                            "avg_min_temp_f": 55.86,
                                            "avg_temp_f": 70.41,
                                            "total_percipitation_in": 0.15,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 10,
                                            "avg_max_temp_f": 73.26,
                                            "avg_min_temp_f": 46.17,
                                            "avg_temp_f": 59.93,
                                            "total_percipitation_in": 3.37,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 11,
                                            "avg_max_temp_f": 50.5,
                                            "avg_min_temp_f": 29.36,
                                            "avg_temp_f": 39.93,
                                            "total_percipitation_in": 3.74,
                                            "total_snowfall_in": 0
                                        },
                                        {
                                            "uuid": "6451fedc-65ba-43fe-21dc-11165bafedl",
                                            "name": "CondenserFanPower",
                                            "parent": "RTU1",
                                            "month": 12,
                                            "avg_max_temp_f": 43.42,
                                            "avg_min_temp_f": 24.65,
                                            "avg_temp_f": 34.03,
                                            "total_percipitation_in": 5.18,
                                            "total_snowfall_in": 0
                                        }
                                    ]
                                }
                            },
                            "devices": {    
                                "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices"],
                                "name": "Devices",
                                "expanded": null,
                                "visible": true,
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _devicesOrder,
                                "children": ["4488fedc-65ba-43fe-21dc-098765bafedl"],
                                "4488fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4488fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "Zone",
                                    "expanded": null,
                                    "visible": true,
                                    "status": "GOOD",
                                    "type": "device",
                                    "sortOrder": 0,
                                    "children": ["points"],
                                    "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl"],
                                    "points": {  
                                        "path": ["platforms", "4687fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                        "name": "Points",
                                        "expanded": null,
                                        "visible": true,
                                        "status": "GOOD",
                                        "type": "type",
                                        "sortOrder": _pointsOrder,
                                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "FirstStageAuxilaryHeat",
                                            "expanded": null,
                                            "visible": true,
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
                                            "expanded": null,
                                            "visible": true,
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
            "expanded": null,
            "visible": true,
            "status": "BAD",
            "type": "platform",
            "sortOrder": 0,
            "children": ["agents", "buildings"],
            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc"],
            "agents": {                
                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "agents"],
                "name": "Agents",
                "expanded": null,
                "visible": true,
                "status": "GOOD",
                "type": "type",
                "sortOrder": _agentsOrder,
                "children": ["2461fedc-65ba-43fe-21dc-098765bafede", "7897fedc-65ba-43fe-21dc-098765bafedf"], 
                "2461fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "2461fedc-65ba-43fe-21dc-098765bafede",
                    "name": "Platform Agent",
                    "expanded": null,
                    "visible": true,
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
                    "expanded": null,
                    "visible": true,
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
                "expanded": null,
                "visible": true,
                "status": "BAD",
                "type": "type",
                "sortOrder": _buildingsOrder,
                "children": ["1111fedc-65ba-43fe-21dc-098765bafede", "1333fedc-65ba-43fe-21dc-098765bafede"],
                "1111fedc-65ba-43fe-21dc-098765bafede":
                {
                    "uuid": "1111fedc-65ba-43fe-21dc-098765bafede",
                    "name": "BSEL",
                    "expanded": null,
                    "visible": true,
                    "status": "BAD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "expanded": null,
                        "visible": true,
                        "status": "UNKNOWN",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "OutdoorAirTemperature",
                            "expanded": null,
                            "visible": true,
                            "status": "GOOD",
                            "type": "point",
                            "sortOrder": 0,
                            "children": [],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "points", "5461fedc-65ba-43fe-21dc-098765bafedl"],
                            "parentPath": "WSU > BSEL",
                            "parentType": "building",
                            "parentUuid": "1111fedc-65ba-43fe-21dc-098765bafede"
                        },
                        "6451fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "LightingStatus",
                            "expanded": null,
                            "visible": true,
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
                        "expanded": null,
                        "visible": true,
                        "status": "BAD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "AHU",
                            "expanded": null,
                            "visible": true,
                            "status": "BAD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["devices", "points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "expanded": null,
                                "visible": true,
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["6451fedc-65ba-43fe-21dc-098765bafedl"],                                
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "DuctStaticPressureSetPoint",
                                    "expanded": null,
                                    "visible": true,
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
                                "expanded": null,
                                "visible": true,
                                "status": "BAD",
                                "type": "type",
                                "sortOrder": _devicesOrder,
                                "children": ["4488fedc-65ba-43fe-21dc-098765bafedl"],
                                "4488fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "4488fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "Zone",
                                    "expanded": null,
                                    "visible": true,
                                    "status": "BAD",
                                    "type": "device",
                                    "sortOrder": 0,
                                    "children": ["points"],
                                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl"],
                                    "points": {  
                                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1111fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "devices", "4488fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                        "name": "Points",
                                        "expanded": null,
                                        "visible": true,
                                        "status": "BAD",
                                        "type": "type",
                                        "sortOrder": _pointsOrder,
                                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"],
                                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                                        {
                                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                                            "name": "TerminalBoxDamperCommand",
                                            "expanded": null,
                                            "visible": true,
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
                                            "expanded": null,
                                            "visible": true,
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
                    "expanded": null,
                    "visible": true,
                    "status": "GOOD",
                    "type": "building",
                    "sortOrder": 0,
                    "children": ["devices", "points"],
                    "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede"],
                    "points": {         
                        "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "points"],
                        "name": "Points",
                        "expanded": null,
                        "visible": true,
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _pointsOrder,
                        "children": ["5461fedc-65ba-43fe-21dc-098765bafedl", "6451fedc-65ba-43fe-21dc-098765bafedl"], 
                        "5461fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "5461fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "WholeBuildingGas",
                            "expanded": null,
                            "visible": true,
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
                            "expanded": null,
                            "visible": true,
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
                        "expanded": null,
                        "visible": true,
                        "status": "GOOD",
                        "type": "type",
                        "sortOrder": _devicesOrder,
                        "children": ["1231fedc-65ba-43fe-21dc-098765bafedl"],
                        "1231fedc-65ba-43fe-21dc-098765bafedl":
                        {
                            "uuid": "1231fedc-65ba-43fe-21dc-098765bafedl",
                            "name": "Chilled_Water_Distribution_System",
                            "expanded": null,
                            "visible": true,
                            "status": "GOOD",
                            "type": "device",
                            "sortOrder": 0,
                            "children": ["points"],
                            "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl"],
                            "points": {      
                                "path": ["platforms", "9757fedc-65ba-43fe-21dc-098765bafedc", "buildings", "1333fedc-65ba-43fe-21dc-098765bafede", "devices", "1231fedc-65ba-43fe-21dc-098765bafedl", "points"],
                                "name": "Points",
                                "expanded": null,
                                "visible": true,
                                "status": "GOOD",
                                "type": "type",
                                "sortOrder": _pointsOrder,
                                "children": ["6451fedc-65ba-43fe-21dc-098765bafedl"],                                
                                "6451fedc-65ba-43fe-21dc-098765bafedl":
                                {
                                    "uuid": "6451fedc-65ba-43fe-21dc-098765bafedl",
                                    "name": "NaturalGasEnergy",
                                    "expanded": null,
                                    "visible": true,
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

platformsPanelItemsStore.getItem = function (itemPath)
{
    var itemsList = [];
    var item = _items;
    
    for (var i = 0; i < itemPath.length; i++)
    {
        if (item.hasOwnProperty(itemPath[i]))
        {
            item = item[itemPath[i]];
        }
    }

    return item;
}  

platformsPanelItemsStore.getChildren = function (parent, parentPath) {

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

platformsPanelItemsStore.loadFilteredItems = function (filterTerm, filterStatus) {

    var filterItems = function (parent, filterTerm, filterStatus) {

        var notAMatch;
        var compareTerm;

        if (filterTerm === "")
        {
            notAMatch = function (parent, filterStatus)
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
            notAMatch = function (parent, filterTerm)
            {
                var upperParent = parent.name.toUpperCase();;
                var filterStr = filterTerm;

                var filterParts = filterTerm.split(" ");
                var foundColon = (filterParts[0].indexOf(":") > -1);

                if (foundColon)
                {
                    var index = filterTerm.indexOf(":");
                    var filterKey = filterTerm.substring(0, index);
                    filterStr = filterTerm.substring(index + 1);

                    if (parent.hasOwnProperty(filterKey))
                    {
                        upperParent = parent[filterKey].toUpperCase();    
                    }
                    else
                    {
                        return true;
                    }
                }               

                return (upperParent.trim().indexOf(filterStr.trim().toUpperCase()) < 0);
            }

            compareTerm = filterTerm;
        }

        if (parent.children.length === 0)
        {
            parent.visible = !notAMatch(parent, compareTerm);
            parent.expanded = null;

            return parent;
        }
        else
        {
            var childrenToHide = 0;

            for (var i = 0; i < parent.children.length; i++)
            {
                var childString = parent.children[i];
                var filteredChild = filterItems(parent[childString], filterTerm, filterStatus);

                if (!filteredChild.visible)
                {
                    ++childrenToHide;
                }
            }
            
            if (childrenToHide === parent.children.length)
            {
                parent.visible = !notAMatch(parent, compareTerm);
                parent.expanded = false;
            }
            else
            {
                parent.visible = true;
                parent.expanded = true;
            }        

            return parent;
        }
    }

    for (var key in _items.platforms)
    {
        if (filterTerm !== "" || filterStatus !== "")
        {
            filterItems(_items.platforms[key], filterTerm, filterStatus);
        }
        else
        {
            expandAllChildren(_items.platforms[key], false);
            _items.platforms[key].visible = true;
        }        
    }

}

var expandAllChildren = function (parent, expanded) {
    
    for (var i = 0; i < parent.children.length; i++)
    {
        var childString = parent.children[i];
        expandAllChildren(parent[childString], expanded);
    }

    if (parent.children.length > 0)
    {
        parent.expanded = expanded;
    }
    else
    {
        parent.expanded = null;
    }

    parent.visible = true;
};


platformsPanelItemsStore.getExpanded = function () {
    return _expanded;
};

platformsPanelItemsStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.FILTER_ITEMS:

            var filterTerm = action.filterTerm;
            var filterStatus = action.filterStatus;
            platformsPanelItemsStore.loadFilteredItems(filterTerm, filterStatus);

            platformsPanelItemsStore.emitChange();

            break;
        case ACTION_TYPES.EXPAND_ALL:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            
            var expanded = (item.expanded !== null ? !item.expanded : true);

            expandAllChildren(item, expanded);

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.TOGGLE_ITEM:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            item.expanded = !item.expanded;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.CHECK_ITEM:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            item.checked = action.checked;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            
            var platforms = action.platforms;

            platforms.forEach(function (platform)
            {
                _items["platforms"][platform.uuid] = platform; 
                
                var platformItem = _items["platforms"][platform.uuid];
                platformItem.path = ["platforms", platform.uuid];

                var status = JSON.parse(platform.status);
                platformItem.status = status.status.toUpperCase();
                platformItem.children = [];
                platformItem.type = "platform";
                platformItem.visible = true;
                platformItem.expanded = null;
                // platformItem.name = (platform.name === null ? platform.uuid : platform.name);

                loadAgents(platform);                
                loadDevices(platform);
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
            var platform = _items["platforms"][action.platform.uuid];

            if (platform.children.length > 0)
            {
                platform.expanded = true;
            }
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:

            // var platform = _items["platforms"][action.platform.uuid];

            // if (action.agents.length > 0)
            // {
            //     platform.expanded = true;
            //     platform.agents = {};
            //     platform.agents.path = platform.path.slice(0);
            //     platform.agents.path.push("agents");
            //     platform.agents.name = "Agents";
            //     platform.agents.expanded = false;
            //     platform.agents.visible = true;
            //     platform.agents.children = [];
            //     platform.agents.type = "type";
            //     platform.agents.sortOrder = _agentsOrder;

            //     if (platform.children.indexOf("agents") < 0)
            //     {
            //         platform.children.push("agents");
            //     }

            //     action.agents.forEach(function (agent)
            //     {
            //         var agentProps = agent;
            //         agentProps.expanded = false;
            //         agentProps.visible = true;
            //         agentProps.path = platform.agents.path.slice(0);
            //         agentProps.path.push(agent.uuid);
            //         // agent.status = "GOOD";
            //         agentProps.children = [];
            //         agentProps.type = "agent";
            //         agentProps.sortOrder = 0;
            //         platform.agents.children.push(agent.uuid); 
            //         platform.agents[agent.uuid] = agentProps;
            //     });

            // }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:

            var item = platformsPanelItemsStore.getItem(action.platform.path);

            // var platform = _items["platforms"][action.platform.uuid];

            if (item.children.length > 0)
            {
                item.expanded = true;
            }
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
            // var item = platformsPanelItemsStore.getItem(action.platform.path);

            // // var platform = _items["platforms"][action.platform.uuid];

            // if (item.children.length > 0)
            // {
            //     item.expanded = true;
            // }

            switch (action.parent.type)
            {
                case "platform":
            
                    var platform = _items["platforms"][action.parent.uuid];

                    if (action.points.length > 0)
                    {
                        platform.expanded = true;
                        platform.points = {};
                        platform.points.path = platform.path.slice(0);
                        platform.points.path.push("points");
                        platform.points.name = "Points";
                        platform.points.expanded = false;
                        platform.points.visible = true;
                        platform.points.children = [];
                        platform.points.type = "type";
                        platform.points.sortOrder = _pointsOrder;

                        if (platform.children.indexOf("points") < 0)
                        {
                            platform.children.push("points");
                        }

                        action.points.forEach(function (point)
                        {
                            //TODO: add UUID to points rpc?

                            var pointProps = point;
                            pointProps.expanded = false;
                            pointProps.visible = true;
                            pointProps.path = platform.points.path.slice(0);

                            var uuid = (point.hasOwnProperty("topic") ? point.topic : point.uuid);
                            
                            pointProps.uuid = uuid;
                            pointProps.path.push(uuid);
                            pointProps.topic = point.topic;

                            pointProps.parentPath = getParentPath(platform);
                            
                            pointProps.parentType = platform.type;
                            pointProps.parentUuid = platform.uuid;

                            // point.status = "GOOD";
                            pointProps.children = [];
                            pointProps.type = "point";
                            pointProps.sortOrder = 0;
                            platform.points.children.push(uuid); 
                            platform.points[uuid] = pointProps;
                        });

                    }

                    break;
            }

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_PANEL_CHILDREN:
            // _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"] = action.points;

            // for (var key in _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"])
            // {
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["children"] = [];
            //     _items["platforms"][action.platform.uuid]["buildings"][action.building.uuid]["devices"][action.device.uuid]["points"][key]["path"] = ["platforms", action.platform.uuid, "buildings", action.building.uuid, "devices", action.device.uuid, "points"];
            // }
            var item = platformsPanelItemsStore.getItem(action.platform.path);

            // var platform = _items["platforms"][action.platform.uuid];

            if (item.children.length > 0)
            {
                item.expanded = true;
            }

            platformsPanelItemsStore.emitChange();
            break;
    }

    function loadAgents(platform)
    {
        // var platform = _items["platforms"][action.platform.uuid];
        
        if (platform.agents.length > 0)
        {
            var agents = [];

            platform.agents.forEach(function (agent) {
                agents.push(agent);
            });

            // platform.expanded = true;
            platform.agents = {};
            platform.agents.path = platform.path.slice(0);
            platform.agents.path.push("agents");
            platform.agents.name = "Agents";
            platform.agents.expanded = false;
            platform.agents.visible = true;
            platform.agents.children = [];
            platform.agents.type = "type";
            platform.agents.sortOrder = _agentsOrder;

            if (platform.children.indexOf("agents") < 0)
            {
                platform.children.push("agents");
            }

            agents.forEach(function (agent)
            {
                var agentProps = agent;
                agentProps.expanded = false;
                agentProps.visible = true;
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
        else
        {
            delete platform.agents;
        }
    }

    function loadDevices(platform)
    {
        // var platform = _items["platforms"][action.platform.uuid];
        
        if (platform.devices.length > 0)
        {
            // var agents = [];

            // platform.agents.forEach(function (agent)) {
            //     agents.push(agent);
            // }

            // platform.expanded = true;
            // platform.agents = {};
            // platform.agents.path = platform.path.slice(0);
            // platform.agents.path.push("agents");
            // platform.agents.name = "Agents";
            // platform.agents.expanded = false;
            // platform.agents.visible = true;
            // platform.agents.children = [];
            // platform.agents.type = "type";
            // platform.agents.sortOrder = _agentsOrder;

            // if (platform.children.indexOf("agents") < 0)
            // {
            //     platform.children.push("agents");
            // }

            // agents.forEach(function (agent)
            // {
            //     var agentProps = agent;
            //     agentProps.expanded = false;
            //     agentProps.visible = true;
            //     agentProps.path = platform.agents.path.slice(0);
            //     agentProps.path.push(agent.uuid);
            //     // agent.status = "GOOD";
            //     agentProps.children = [];
            //     agentProps.type = "agent";
            //     agentProps.sortOrder = 0;
            //     platform.agents.children.push(agent.uuid); 
            //     platform.agents[agent.uuid] = agentProps;
            // });

        }
        else
        {
            delete platform.devices;
        }
    }

    function getParentPath(parent)
    {
        var path = parent.path;

        var pathParts = [];

        var item = _items;

        path.forEach(function (part) {
            item = item[part];
            if (_itemTypes.indexOf(part) < 0)
            {
                pathParts.push(item.name);
            } 
        });

        var pathStr = pathParts.join(" > ");

        return pathStr;
    }
});

module.exports = platformsPanelItemsStore;


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41}],53:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _expanded = null;

var platformsPanelStore = new Store();

platformsPanelStore.getExpanded = function () {
    return _expanded;
};

platformsPanelStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.TOGGLE_PLATFORMS_PANEL:  
            (_expanded === null ? _expanded = true : _expanded = !_expanded);
            platformsPanelStore.emitChange();
            break;
        case ACTION_TYPES.CLOSE_PLATFORMS_PANEL:  
            _expanded = false;
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41}],54:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"../stores/authorization-store":45}],55:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _statusMessage = null;
var _status = null;

var statusIndicatorStore = new Store();

statusIndicatorStore.getStatusMessage = function () {
    return _statusMessage;
};

statusIndicatorStore.getStatus = function () {
    return _status;
};

statusIndicatorStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.OPEN_STATUS:
            _statusMessage = action.message;
            _status = action.status;

            statusIndicatorStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_STATUS:
            _statusMessage = null;
            _status = null;
            statusIndicatorStore.emitChange();
            break;
    }
});

module.exports = statusIndicatorStore;


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41}],56:[function(require,module,exports){
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


},{"../constants/action-types":36,"../dispatcher":37,"../lib/store":41,"./authorization-store":45}]},{},[1]);
