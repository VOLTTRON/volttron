(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var authorizationStore = require('./stores/authorization-store');
var platformsPanelItemsStore = require('./stores/platforms-panel-items-store');
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
                    // _afterLoginPath = transition.path;

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
        if (authorizationStore.getAuthorization() && router.isActive('/login')) 
        {
            router.replaceWith(_afterLoginPath);
        } 
        else if (!authorizationStore.getAuthorization() && !router.isActive('/login')) 
        {
            router.replaceWith('/login');
        }
    });

    platformsPanelItemsStore.addChangeListener(function () {
        if (platformsPanelItemsStore.getLastCheck() && authorizationStore.getAuthorization())
        {
            // console.log("current path: " + router.getCurrentPath());
            if (!router.isActive('charts'))
            {
                // console.log("replace with /platform-charts");
                router.transitionTo('/platform-charts');
                // window.location.href = "index.html#/platform-charts";
            }
        }

    });


});


},{"./components/dashboard":16,"./components/login-form":19,"./components/page-not-found":22,"./components/platform":26,"./components/platform-charts":24,"./components/platform-manager":25,"./components/platforms":29,"./stores/authorization-store":42,"./stores/platforms-panel-items-store":47,"react":undefined,"react-router":undefined}],2:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/rpc/exchange":36}],3:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34}],4:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34}],5:[function(require,module,exports){
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


},{"../action-creators/status-indicator-action-creators":9,"../constants/action-types":33,"../dispatcher":34,"../lib/rpc":37,"../stores/authorization-store":42,"../stores/platform-chart-store":46,"../stores/platforms-store":49}],6:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformsStore = require('../stores/platforms-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
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
                .catch(rpc.Error, function (error) {

                    var message = "Unable to update chart: " + error.message;

                    if (error.code === -32602)
                    {
                        if (error.message === "historian unavailable")
                        {
                            message = "Unable to update chart: The historian agent is unavailable.";
                        }
                    }
                    else
                    {
                        var platform = platformsStore.getPlatform(item.parentUuid);
                        var historianRunning = platformsStore.getHistorianRunning(platform);

                        if (!historianRunning)
                        {
                            message = "Unable to update chart: The historian agent is unavailable.";
                        }
                    }

                    handle401(error, message);
                });
		});

	},
	addToChart: function(panelItem, emitChange) {

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
                    type: ACTION_TYPES.SHOW_CHARTS,
                    emitChange: (emitChange === null || typeof emitChange === "undefined" ? true : emitChange)
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });

                var savedCharts = platformChartStore.getPinnedCharts();
                var inSavedChart = savedCharts.find(function (chart) {
                    return chart.chartKey === panelItem.name;
                });

                if (inSavedChart)
                {
                    platformActionCreators.saveCharts(savedCharts);
                }
            })
            .catch(rpc.Error, function (error) {

                var message = "Unable to load chart: " + error.message;

                if (error.code === -32602)
                {
                    if (error.message === "historian unavailable")
                    {
                        message = "Unable to load chart: The historian agent is not available.";
                    }
                }
                else
                {
                    var platform = platformsStore.getPlatform(panelItem.parentUuid);
                    var historianRunning = platformsStore.getHistorianRunning(platform);

                    if (!historianRunning)
                    {
                        message = "Unable to load chart: The historian agent is not available.";
                    }
                }

                platformsPanelActionCreators.checkItem(panelItem.path, false);
                handle401(error, message);
            });
    },
    removeFromChart: function(panelItem) {

        var savedCharts = platformChartStore.getPinnedCharts();
        var inSavedChart = savedCharts.find(function (chart) {
            return chart.chartKey === panelItem.name;
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_CHART,
            panelItem: panelItem
        });        

        if (inSavedChart)
        {
            platformActionCreators.saveCharts();
        }

    },
    removeChart: function(chartName) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_CHART,
            name: chartName
        });
    }
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
};

module.exports = platformChartActionCreators;


},{"../action-creators/platform-action-creators":5,"../action-creators/platforms-panel-action-creators":8,"../action-creators/status-indicator-action-creators":9,"../constants/action-types":33,"../dispatcher":34,"../lib/rpc":37,"../stores/authorization-store":42,"../stores/platform-chart-store":46,"../stores/platforms-store":49}],7:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var platformActionCreators = require('../action-creators/platform-action-creators');
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

                statusIndicatorActionCreators.openStatusIndicator("error", message); //This is needed because the 401 status will keep the status 
                handle401(error, error.message);                                    // indicator from being shown. This is the one time we
            })                                                                      // show bad status for not authorized. Other times, we
    },                                                                              // just log them out.
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
    registerPlatform: function (name, address, method) {
        var authorization = authorizationStore.getAuthorization();

        var rpcMethod;
        var params = {};

        switch (method)
        {
            case "discovery":
                rpcMethod = 'register_instance';
                params = {
                    display_name: name,
                    discovery_address: address
                }
                break;
            case "advanced":
                rpcMethod = 'register_platform';
                params = {
                    identity: 'platform.agent',
                    agentId: name,
                    address: address
                }
                break;
        }

        new rpc.Exchange({
            method: rpcMethod,
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + name + " was registered.");
        
                platformManagerActionCreators.loadPlatforms();                

            })
            .catch(rpc.Error, function (error) {
                
                dispatcher.dispatch({
                    type: ACTION_TYPES.CLOSE_MODAL,
                });

                var message = error.message;

                switch (error.code)
                {
                    case -32600:
                        message = "Platform " + name + " was not registered: Invalid address."
                        break;
                    case -32002:
                        message = "Platform " + name + " was not registered: " + error.message;
                        break;
                    case -32000:
                        message = "Platform " + name + " was not registered: An unknown error occurred.";
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
            })
            .catch(rpc.Error, function (error) { 
                var message = "Platform " + platformName + " was not deregistered: " + error.message;

                handle401(error, message);
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


},{"../action-creators/platform-action-creators":5,"../action-creators/status-indicator-action-creators":9,"../constants/action-types":33,"../dispatcher":34,"../lib/rpc":37,"../stores/authorization-store":42}],8:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformsPanelActionCreators = {    
    togglePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL,
        });
    },

    loadChildren: function(type, parent)
    {
        if (type === "platform")
        {
            dispatcher.dispatch({
                type: ACTION_TYPES.START_LOADING_DATA,
                panelItem: parent 
            });

            loadPanelDevices(parent);
        } 

        function loadPanelDevices(platform) {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.get_devices',
                authorization: authorization,
            }).promise
                .then(function (result) {
                    
                    var devicesList = [];

                    for (var key in result)
                    {
                        var device = JSON.parse(JSON.stringify(result[key]));
                        device.path = key;

                        devicesList.push(device);
                    }

                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_DEVICE_STATUSES,
                        platform: platform,
                        devices: devicesList
                    });

                    loadPanelAgents(platform);
                    
                })                     
                .catch(rpc.Error, function (error) {
                    endLoadingData(platform);
                    handle401(error, "Unable to load devices for platform " + platform.name + " in side panel: " + error.message);
                });    

        }

        function loadPanelAgents(platform) {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.list_agents',
                authorization: authorization,
            }).promise
                .then(function (agentsList) {
                    
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                        platform: platform,
                        agents: agentsList
                    });

                    loadPerformanceStats(platform);
                })                     
                .catch(rpc.Error, function (error) {
                    endLoadingData(platform);
                    handle401(error, "Unable to load agents for platform " + platform.name + " in side panel: " + error.message);
                });    
        }       

        function loadPerformanceStats(parent) {

            if (parent.type === "platform")
            {
                var authorization = authorizationStore.getAuthorization();

                //TODO: use service to get performance for a single platform

                new rpc.Exchange({
                    method: 'list_performance',
                    authorization: authorization,
                    }).promise
                        .then(function (result) {
                            
                            var platformPerformance = result.find(function (item) {
                                return item["platform.uuid"] === parent.uuid;
                            });

                            var pointsList = [];

                            if (platformPerformance)
                            {
                                var points = platformPerformance.performance.points;

                                points.forEach(function (point) {

                                    var pointName = (point === "percent" ? "cpu / percent" : point.replace("/", " / "));

                                    pointsList.push({
                                        "topic": platformPerformance.performance.topic + "/" + point,
                                        "name": pointName
                                    });
                                });                                
                            }

                            dispatcher.dispatch({
                                type: ACTION_TYPES.RECEIVE_PERFORMANCE_STATS,
                                parent: parent,
                                points: pointsList
                            });

                            endLoadingData(parent);
                        })
                        .catch(rpc.Error, function (error) {
                            
                            var message = error.message;

                            if (error.code === -32602)
                            {
                                if (error.message === "historian unavailable")
                                {
                                    message = "Data could not be fetched for platform " + parent.name + ". The historian agent is unavailable."
                                }
                            }

                            endLoadingData(parent);
                            handle401(error, message);
                        });   
            } 
        }

        function endLoadingData(panelItem)
        {
            dispatcher.dispatch({
                type: ACTION_TYPES.END_LOADING_DATA,
                panelItem: panelItem
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
    }    
}

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
};

module.exports = platformsPanelActionCreators;


},{"../action-creators/status-indicator-action-creators":9,"../constants/action-types":33,"../dispatcher":34,"../lib/rpc":37,"../stores/authorization-store":42,"../stores/platforms-panel-items-store":47}],9:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34}],10:[function(require,module,exports){
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
                
                if (agent.permissions.can_start)
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
                
                if (agent.permissions.can_stop)
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
                
                if (agent.permissions.can_restart)
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

        if (agent.permissions.can_remove)
        {
            remove = ( React.createElement("input", {className: "button button--agent-action", type: "button", value: "Remove", onClick: this._onRemove}) );
        }
        else
        {
            remove = ( React.createElement("input", {className: "button button--agent-action", type: "button", value: "Remove", onClick: this._onRemove, disabled: true}) );
        } 

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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"./remove-agent-form":31,"react":undefined}],11:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../stores/console-store":43,"react":undefined}],12:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var ConfirmForm = React.createClass({displayName: "ConfirmForm",
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function (e) {
        e.preventDefault();
        this.props.onConfirm();
    },
    render: function () {

        var promptText = this.props.promptText;

        if (this.props.hasOwnProperty("preText") && this.props.hasOwnProperty("postText"))
        {
            promptText = React.createElement("b", null, promptText)
        }

        return (
            React.createElement("form", {className: "confirmation-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, this.props.promptTitle), 
                React.createElement("p", null, 
                    this.props.preText, promptText, this.props.postText
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


},{"../action-creators/modal-action-creators":4,"react":undefined}],13:[function(require,module,exports){
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


},{"./composer":11,"./conversation":15,"react":undefined}],14:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var controlButtonStore = require('../stores/control-button-store');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');


var ControlButton = React.createClass({displayName: "ControlButton",
    mixins: [
        require('react-onclickoutside')
    ],
	getInitialState: function () {
		var state = {};

		state.showTaptip = false;
		state.showTooltip = false;
		state.deactivateTooltip = false;

        state.selected = (this.props.selected === true);

		state.taptipX = 0;
		state.taptipY = 0;
        state.tooltipX = 0;
        state.tooltipY = 0;

        state.tooltipOffsetX = 0;
        state.tooltipOffsetY = 0;
        state.taptipOffsetX = 0;
        state.taptipOffsetY = 0;

        if (this.props.hasOwnProperty("tooltip"))
        {
            if (this.props.tooltip.hasOwnProperty("x"))
                state.tooltipX = this.props.tooltip.x;

            if (this.props.tooltip.hasOwnProperty("y"))
                state.tooltipY = this.props.tooltip.y;
            
            if (this.props.tooltip.hasOwnProperty("xOffset"))
                state.tooltipOffsetX = this.props.tooltip.xOffset;

            if (this.props.tooltip.hasOwnProperty("yOffset"))
                state.tooltipOffsetY = this.props.tooltip.yOffset;
        }

        if (this.props.hasOwnProperty("taptip"))
        {
            if (this.props.taptip.hasOwnProperty("x"))
                state.taptipX = this.props.taptip.x;

            if (this.props.taptip.hasOwnProperty("y"))
                state.taptipY = this.props.taptip.y;
            
            if (this.props.taptip.hasOwnProperty("xOffset"))
                state.taptipOffsetX = this.props.taptip.xOffset;

            if (this.props.taptip.hasOwnProperty("yOffset"))
                state.taptipOffsetY = this.props.taptip.yOffset;
        }

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
            else
            {
                if (typeof this.props.closeAction == 'function')
                {
                    this.props.closeAction();
                }
            }
	    }
    },
    handleClickOutside: function () {
        if (this.state.showTaptip)
        {
            controlButtonActionCreators.hideTaptip(this.props.name);
        }
    },
	_showTaptip: function (evt) {

		if (!this.state.showTaptip)
		{
            if (!(this.props.taptip.hasOwnProperty("x") && this.props.taptip.hasOwnProperty("y")))
            {
                this.setState({taptipX: evt.clientX - this.state.taptipOffsetX});
                this.setState({taptipY: evt.clientY - this.state.taptipOffsetY});    
            }
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

        if (!(this.props.tooltip.hasOwnProperty("x") && this.props.tooltip.hasOwnProperty("y")))
        {
            this.setState({tooltipX: evt.clientX - this.state.tooltipOffsetX});
            this.setState({tooltipY: evt.clientY - this.state.tooltipOffsetY});
        }
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

        var buttonIcon = (this.props.icon ? this.props.icon :
                            (this.props.fontAwesomeIcon ? 
                                (React.createElement("i", {className: "fa fa-" + this.props.fontAwesomeIcon})) : 
                                    (React.createElement("div", {className: this.props.buttonClass}, React.createElement("span", null, this.props.unicodeIcon))) ) );

        if (this.props.staySelected || this.state.selected === true || this.state.showTaptip === true)
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

            //TODO: add this to repository
            if (this.props.taptip.styles)
            {
                this.props.taptip.styles.forEach(function (styleToAdd) {
                    taptipStyle[styleToAdd.key] = styleToAdd.value;
                });
            }
            //end TODO

		    var tapTipClasses = "taptip_outer";

            var taptipBreak = (this.props.taptip.hasOwnProperty("break") ? this.props.taptip.break : React.createElement("br", null));
            var taptipTitle = (this.props.taptip.hasOwnProperty("title") ? (React.createElement("h4", null, this.props.taptip.title)) : "");

            var innerStyle = {};

            if (this.props.taptip.hasOwnProperty("padding"))
            {
                innerStyle = {
                    padding: this.props.taptip.padding
                }
            } 

		    taptip = (
		    	React.createElement("div", {className: tapTipClasses, 
	                style: taptipStyle}, 
	                React.createElement("div", {className: "taptip_inner", 
                        style: innerStyle}, 
	                    React.createElement("div", {className: "opaque_inner"}, 
	                        taptipTitle, 
	                        taptipBreak, 
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

        var controlButtonClass = (this.props.controlclass ? this.props.controlclass : "control_button");

        return (
            React.createElement("div", {className: "inlineBlock"}, 
            	taptip, 
            	tooltip, 
                React.createElement("div", {className: controlButtonClass, 
                    onClick: clickAction, 
                    onMouseEnter: tooltipShow, 
                    onMouseLeave: tooltipHide, 
                    style: selectedStyle}, 
                    React.createElement("div", {className: "centeredDiv"}, 
                        buttonIcon
                    )
                )
            )
        );
    },
});







module.exports = ControlButton;

},{"../action-creators/control-button-action-creators":3,"../stores/control-button-store":44,"react":undefined,"react-onclickoutside":undefined,"react-router":undefined}],15:[function(require,module,exports){
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


},{"../stores/console-store":43,"./exchange":18,"jquery":undefined,"react":undefined}],16:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var platformChartStore = require('../stores/platform-chart-store');

var PlatformChart = require('./platform-chart');

var Dashboard = React.createClass({displayName: "Dashboard",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformChartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformChartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        
        var pinnedCharts = this.state.platformCharts; 

        var platformCharts = [];

        pinnedCharts.forEach(function (pinnedChart) {
            if (pinnedChart.data.length > 0)
            {
                var platformChart = React.createElement(PlatformChart, {chart: pinnedChart, chartKey: pinnedChart.chartKey, hideControls: true})
                platformCharts.push(platformChart);
            }
        });        

        if (pinnedCharts.length === 0) {
            platformCharts = (
                React.createElement("p", {className: "empty-help"}, 
                    "Pin a platform chart to have it appear on the dashboard"
                )
            );
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
        platformCharts: platformChartStore.getPinnedCharts()
    };
}

module.exports = Dashboard;


},{"../stores/platform-chart-store":46,"./platform-chart":23,"react":undefined,"react-router":undefined}],17:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var RegisterPlatformForm = React.createClass({displayName: "RegisterPlatformForm",
    getInitialState: function () {
        return {};
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function (e) {
        e.preventDefault();
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

module.exports = RegisterPlatformForm;


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-manager-action-creators":7,"react":undefined}],18:[function(require,module,exports){
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


},{"react":undefined}],19:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LoginForm = React.createClass({displayName: "LoginForm",
    getInitialState: function () {
        var state = {};

        return state;
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
                )
            )
        );
    }
});

module.exports = LoginForm;


},{"../action-creators/platform-manager-action-creators":7,"react":undefined,"react-router":undefined}],20:[function(require,module,exports){
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


},{"../action-creators/modal-action-creators":4,"react":undefined}],21:[function(require,module,exports){
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
        // platformsPanelActionCreators.closePanel();
        // platformsPanelActionCreators.resetPanel();
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
                    React.createElement("span", {className: "logo__beta"}, "BETA"), 
                    React.createElement("span", {className: "logo__funding"}, "Funded by DOE EERE BTO")
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


},{"../action-creators/platform-manager-action-creators":7,"../action-creators/platforms-panel-action-creators":8,"../stores/authorization-store":42,"react":undefined,"react-router":undefined}],22:[function(require,module,exports){
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


},{"react":undefined}],23:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');
var moment = require('moment');


var chartStore = require('../stores/platform-chart-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var ConfirmForm = require('./confirm-form');
var ControlButton = require('./control-button');

var PlatformChart = React.createClass({displayName: "PlatformChart",
    getInitialState: function () {
        var state = {};

        state.refreshInterval = this.props.chart.refreshInterval;
        state.pinned = this.props.chart.pinned;

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
    _removeChart: function () {

        var deleteChart = function () {
            modalActionCreators.closeModal();

            this.props.chart.series.forEach(function (series) {
                if (series.hasOwnProperty("path"))
                {
                    platformsPanelActionCreators.checkItem(series.path, false);
                }
            });

            platformChartActionCreators.removeChart(this.props.chartKey);
            platformActionCreators.saveCharts();
        }

        modalActionCreators.openModal(
            React.createElement(ConfirmForm, {
                promptTitle: "Delete chart", 
                preText: "Remove ", 
                promptText: this.props.chartKey, 
                postText: " chart from here and from Dashboard?", 
                confirmText: "Delete", 
                onConfirm: deleteChart.bind(this)}
            )
        );

        // this.props.chart.series.forEach(function (series) {
        //     if (series.hasOwnProperty("path"))
        //     {
        //         platformsPanelActionCreators.checkItem(series.path, false);
        //     }
        // });

        // platformChartActionCreators.removeChart(this.props.chartKey);
        // platformActionCreators.saveCharts();
    },
    render: function () {
        var chartData = this.props.chart; 
        var platformChart;

        var removeButton;

        if (!this.props.hideControls)
        {
            removeButton = (
              React.createElement("div", {className: "remove-chart", 
                  onClick: this._removeChart}, 
                React.createElement("i", {className: "fa fa-remove"})
              )
            );
        }

        if (chartData)
        {
            if (chartData.data.length > 0)
            {
                platformChart = (
                  React.createElement("div", {className: "platform-chart with-3d-shadow with-transitions absolute_anchor"}, 
                      React.createElement("label", {className: "chart-title"}, chartData.data[0].name), 
                      removeButton, 
                      React.createElement("div", null, 
                          React.createElement("div", {className: "viz"}, 
                               chartData.data.length != 0 ? 
                                    React.createElement(GraphLineChart, {
                                        key: this.props.chartKey, 
                                        data: chartData.data, 
                                        name: this.props.chartKey, 
                                        hideControls: this.props.hideControls, 
                                        refreshInterval: this.props.chart.refreshInterval, 
                                        pinned: this.props.chart.pinned, 
                                        chartType: this.props.chart.type}) : null
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
  mixins: [
      require('react-onclickoutside')
  ],
  getInitialState: function () {
      
      var pattern = /[!@#$%^&*()+\-=\[\]{};':"\\|, .<>\/?]/g

      var state = {};

      state.chartName = this.props.name.replace(" / ", "_") + '_chart';
      state.chartName = state.chartName.replace(pattern, "_");
      state.lineChart = null;
      state.pinned = this.props.pinned;
      state.chartType = this.props.chartType;
      state.showTaptip = false;
      state.taptipX = 0;
      state.taptipY = 0;

      return state;
  },
  componentDidMount: function() {
      platformChartStore.addChangeListener(this._onStoresChange);
      var lineChart = this._drawLineChart(this.state.chartName, this.state.chartType, this._lineData(this._getNested(this.props.data)));
      this.setState({lineChart: lineChart});

      this.chart = React.findDOMNode(this.refs[this.state.chartName]);
  },
  componentWillUnmount: function () {
      platformChartStore.removeChangeListener(this._onStoresChange);
      if (this.lineChart)
      {
        delete this.lineChart;
      }
  },
  componentDidUpdate: function() {
      if (this.state.lineChart)
      {
          this._updateLineChart(this.state.lineChart, this.state.chartName, this._lineData(this._getNested(this.props.data)));
      }
  },
  _onStoresChange: function () {
      this.setState({pinned: platformChartStore.getPinned(this.props.name)});
      this.setState({chartType: platformChartStore.getType(this.props.name)});
  },
  handleClickOutside: function () {      
      
      if (this.chart)
      {
          this.nvtooltip = this.chart.querySelector(".nvtooltip");

          if (this.nvtooltip)
          {
              this.nvtooltip.style.opacity = 0;
          }
      }
  },
  _onChartChange: function (e) {
      var chartType = e.target.value;
      
      var lineChart = this._drawLineChart(this.state.chartName, chartType, this._lineData(this._getNested(this.props.data)));

      this.setState({lineChart: lineChart});
      this.setState({showTaptip: false});

      platformChartActionCreators.setType(this.props.name, chartType);

      if (this.state.pinned)
      {
          platformActionCreators.saveCharts();
      }
  },
  _onPinToggle: function () {

      var pinned = !this.state.pinned;

      platformChartActionCreators.pinChart(this.props.name);

      platformActionCreators.saveCharts();
  },
  _onRefreshChange: function (e) {
      platformChartActionCreators.changeRefreshRate(e.target.value, this.props.name);

      if (this.state.pinned)
      {
          platformActionCreators.saveCharts();
      }
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
        var taptipX = 0;
        var taptipY = 40;

        var tooltipX = 0;
        var tooltipY = 80;

        var chartTypeSelect = (
            React.createElement("select", {
                onChange: this._onChartChange, 
                value: this.state.chartType, 
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
            "x": taptipX,
            "y": taptipY
        };
        var chartTypeIcon = (
            React.createElement("i", {className: "fa fa-line-chart"})
        );
        var chartTypeTooltip = {
            "content": "Chart Type",
            "x": tooltipX,
            "y": tooltipY
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
            "x": tooltipX,
            "y": tooltipY
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
            "x": taptipX,
            "y": taptipY
        };
        var refreshChartIcon = (
            React.createElement("i", {className: "fa fa-hourglass"})
        );
        var refreshChartTooltip = {
            "content": "Refresh Rate",
            "x": tooltipX,
            "y": tooltipY
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
          style: chartStyle, 
          ref: this.state.chartName}, 
          React.createElement("svg", {id: this.state.chartName, style: svgStyle}), 
          controlButtons
      )
    );
  },
  _drawLineChart: function (elementParent, chartType, data) {
      
      var tickCount = 0;
      // var lineChart;

      switch (chartType)
      {
          case "line":
              this.lineChart = nv.models.lineChart();
              break;
          case "lineWithFocus":
              this.lineChart = nv.models.lineWithFocusChart();
              break;
          case "stackedArea":
              this.lineChart = nv.models.stackedAreaChart();
              break;
          case "cumulativeLine":
              this.lineChart = nv.models.cumulativeLineChart();
              break;
      }

      this.lineChart.margin({left: 25, right: 25})
          .x(function(d) {return d.x})
          .y(function(d) {return d.y})
          .useInteractiveGuideline(true)
          .showYAxis(true)
          .showXAxis(true);
      this.lineChart.xAxis
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
      this.lineChart.yAxis
        .tickFormat(d3.format('.1f'));

      switch (chartType)
      {        
          case "lineWithFocus":            
              this.lineChart.x2Axis
                .tickFormat(function (d) {
                    return d3.time.format('%X')(new Date(d));
                });
              break;
      }

      d3.selectAll('#' + elementParent + ' > *').remove();
      d3.select('#' + elementParent)
        .datum(data)
        .call(this.lineChart);
      nv.utils.windowResize(function() {
        if (this.lineChart)
        {
           this.lineChart.update();
        }
      });

      nv.addGraph(function() {
        return this.lineChart;
      });

      return this.lineChart;
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"../action-creators/platform-chart-action-creators":6,"../action-creators/platforms-panel-action-creators":8,"../stores/platform-chart-store":46,"./confirm-form":12,"./control-button":14,"d3":undefined,"moment":undefined,"nvd3":undefined,"react":undefined,"react-onclickoutside":undefined,"react-router":undefined}],24:[function(require,module,exports){
'use strict';

var React = require('react');
var PlatformChart = require('./platform-chart');
var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsStore = require('../stores/platforms-store');
var chartStore = require('../stores/platform-chart-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var PlatformCharts = React.createClass({displayName: "PlatformCharts",
    getInitialState: function () {

        var vc = platformsStore.getVcInstance();

        var state = {
            platform: vc,
            chartData: chartStore.getData(),
            historianRunning: platformsStore.getHistorianRunning(vc),
            modalContent: null
        };

        return state;
    },
    componentDidMount: function () {
        chartStore.addChangeListener(this._onChartStoreChange);
        platformsStore.addChangeListener(this._onPlatformStoreChange);

        if (!this.state.platform)
        {
            platformManagerActionCreators.loadPlatforms();
        }
    },
    componentWillUnmount: function () {
        chartStore.removeChangeListener(this._onChartStoreChange);
        platformsStore.removeChangeListener(this._onPlatformStoreChange);
    },
    _onChartStoreChange: function () {
        this.setState({chartData: chartStore.getData()});
    },
    _onPlatformStoreChange: function () {

        var platform = this.state.platform;

        if (!platform)
        {
            platform = platformsStore.getVcInstance();

            if (platform)
            {
                this.setState({platform: platform});
            }
        }

        this.setState({historianRunning: platformsStore.getHistorianRunning(platform)});
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
            var noCharts = React.createElement("p", {className: "empty-help"}, "No charts have been loaded.")
            platformCharts.push(noCharts);
        }

        return (
            React.createElement("div", {className: "view"}, 
                React.createElement("div", {className: "absolute_anchor"}, 
                    React.createElement("div", {className: "view__actions"}
                    ), 
                    React.createElement("h2", null, "Charts"), 
                    platformCharts
                )
            )
        );
    },
});

module.exports = PlatformCharts;


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"../action-creators/platform-manager-action-creators":7,"../action-creators/status-indicator-action-creators":9,"../stores/platform-chart-store":46,"../stores/platforms-store":49,"./platform-chart":23,"react":undefined}],25:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../action-creators/modal-action-creators":4,"../action-creators/platform-manager-action-creators":7,"../stores/authorization-store":42,"../stores/console-store":43,"../stores/modal-store":45,"../stores/platforms-panel-store":48,"../stores/status-indicator-store":50,"./console":13,"./modal":20,"./navigation":21,"./platforms-panel":28,"./status-indicator":32,"jquery":undefined,"react":undefined,"react-router":undefined}],26:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformActionCreators = require('../action-creators/platform-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
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
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores(this));
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

        var agents;
        
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
                            React.createElement("th", null, "Tag"), 
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
                React.createElement("h2", null, 
                    React.createElement(Router.Link, {to: "platforms"}, "Platforms"), 
                    " / ", 
                    platform.name, " (", platform.uuid, ")"
                ), 

                
                React.createElement("br", null), 
                React.createElement("br", null), 
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
        platform: platformsStore.getPlatform(component.getParams().uuid)
    };
}

module.exports = Platform;


},{"../action-creators/platform-action-creators":5,"../action-creators/status-indicator-action-creators":9,"../stores/platforms-store":49,"./agent-row":10,"react":undefined,"react-router":undefined}],27:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');


var PlatformsPanelItem = React.createClass({displayName: "PlatformsPanelItem",
    getInitialState: function () {
        var state = {};
        
        state.showTooltip = false;
        state.tooltipX = null;
        state.tooltipY = null;
        state.checked = (this.props.panelItem.hasOwnProperty("checked") ? this.props.panelItem.checked : false);
        state.panelItem = this.props.panelItem;
        state.children = this.props.panelChildren;

        if (this.props.panelItem.type === "platform")
        {
            state.notInitialized = true;
            state.loading = false;
            state.cancelButton = false;
        }

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var panelItem = platformsPanelItemsStore.getItem(this.props.itemPath);
        var panelChildren = platformsPanelItemsStore.getChildren(this.props.panelItem, this.props.itemPath);

        var loadingComplete = platformsPanelItemsStore.getLoadingComplete(this.props.panelItem);

        if (loadingComplete === true || loadingComplete === null)
        {
            this.setState({panelItem: panelItem});
            this.setState({children: panelChildren});
            this.setState({checked: panelItem.checked});

            if (this.props.panelItem.type === "platform")
            {
                if (loadingComplete === true)
                {
                    this.setState({loading: false});
                    this.setState({notInitialized: false});
                }
                else if (loadingComplete === null)
                {
                    this.setState({loading: false});
                    this.setState({notInitialized: true});
                }
            }
        }
    },
    _expandAll: function () {
        
        platformsPanelActionCreators.expandAll(this.props.itemPath);
    },
    _handleArrowClick: function () {
        
        if (!this.state.loading) // If not loading, treat it as just a regular toggle button
        {
            if (this.state.panelItem.expanded === null && this.state.panelItem.type === "platform") 
            {
                this.setState({loading: true});
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
        }
        else if (this.state.hasOwnProperty("loading")) // it's a platform and it's loading
        {
            if (this.state.loading || this.state.cancelButton) // if either loading or cancelButton is still
            {                                                   // true, either way, the user wants to 
                this.setState({loading: false});                // get out of the loading state, so turn
                this.setState({cancelButton: false});           // the toggle button back to an arrow icon
            }
        }
    },
    _showCancel: function () {

        if (this.state.hasOwnProperty("loading") && (this.state.loading === true))
        {
            this.setState({cancelButton: true});
        }
    },
    _resumeLoad: function () {

        if (this.state.hasOwnProperty("loading"))
        {
            this.setState({cancelButton: false});
        }
    },
    _checkItem: function (e) {

        var checked = e.target.checked;

        platformsPanelActionCreators.checkItem(this.props.itemPath, checked);

        this.setState({checked: checked});

        if (checked)
        {
            platformChartActionCreators.addToChart(this.props.panelItem);
        }
        else
        {
            platformChartActionCreators.removeFromChart(this.props.panelItem);
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

        var childClass;
        var arrowClasses = [ "arrowButton", "noRotate" ];

        if (this.state.hasOwnProperty("loading"))
        {
            if (this.state.cancelButton)
            {
                arrowClasses.push("cancelLoading");
            }
            else if (this.state.loading)
            {
                arrowClasses.push("loadingSpinner");
            }
        }
        
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

        if (!this.state.loading)
        {
            arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) );
        }

        var arrowContent;
        var arrowContentStyle = {
            width: "14px"
        }

        if (this.state.cancelButton)
        {
            arrowContent = React.createElement("span", {style: arrowContentStyle}, React.createElement("i", {className: "fa fa-remove"}));
        }
        else if (this.state.loading)
        {
            arrowContent = React.createElement("span", {style: arrowContentStyle}, React.createElement("i", {className: "fa fa-circle-o-notch fa-spin fa-fw"}));
        }
        else if (panelItem.status === "GOOD")
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
          
        if (this.state.panelItem.expanded === true && propChildren)
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
                childClass = "showItems";                    
            }          
        }

        var itemClasses = [];

        if (!panelItem.hasOwnProperty("uuid"))
        {
            itemClasses.push("item_type");
        }
        else
        {
            itemClasses.push("item_label");
        }

        if (panelItem.type === "platform" && this.state.notInitialized)
        {
            itemClasses.push("not_initialized");
        }

        var listItem = 
                React.createElement("div", {className: itemClasses.join(' ')}, 
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
                        onClick: this._handleArrowClick, 
                        onMouseEnter: this._showCancel, 
                        onMouseLeave: this._resumeLoad}, 
                        arrowContent
                    ), 
                    ChartCheckbox, 
                    React.createElement("div", {className: toolTipClasses, 
                        style: tooltipStyle}, 
                        React.createElement("div", {className: "tooltip_inner"}, 
                            React.createElement("div", {className: "opaque_inner"}, 
                                panelItem.name, ": ", (panelItem.context ? panelItem.context : panelItem.statusLabel)
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
                React.createElement("div", {className: childClass}, 
                    React.createElement("ul", {className: "platform-panel-list"}, 
                        children
                    )
                )
            )
        );
    },
});

module.exports = PlatformsPanelItem;


},{"../action-creators/platform-chart-action-creators":6,"../action-creators/platforms-panel-action-creators":8,"../stores/platforms-panel-items-store":47,"react":undefined,"react-router":undefined}],28:[function(require,module,exports){
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
        state.expanded = platformsPanelStore.getExpanded();
        state.filterValue = "";
        state.filterStatus = "";

        return state;
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
        var expanded = platformsPanelStore.getExpanded();

        if (expanded !== this.state.expanded)
        {
            this.setState({expanded: expanded});
        }        
        
        if (expanded !== null)
        {
            var platformsList = platformsPanelItemsStore.getChildren("platforms", null);
            this.setState({platforms: platformsList});
        }
        else
        {
            this.setState({filterValue: ""});
            this.setState({filterStatus: ""});
        }
    },
    _onPanelItemsStoreChange: function () {
        if (this.state.expanded !== null)
        {
            this.setState({platforms: platformsPanelItemsStore.getChildren("platforms", null)});
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


module.exports = PlatformsPanel;


},{"../action-creators/platforms-panel-action-creators":8,"../stores/platforms-panel-items-store":47,"../stores/platforms-panel-store":48,"./control-button":14,"./platforms-panel-item":27,"react":undefined,"react-router":undefined}],29:[function(require,module,exports){
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
    getInitialState: function () {
        return getStateFromStores();
    },
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
                React.createElement("div", {className: "absolute_anchor"}, 
                    React.createElement("h2", null, "Platforms"), 
                    React.createElement("div", {className: "view__actions"}, 
                        
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


},{"../action-creators/modal-action-creators":4,"../action-creators/status-indicator-action-creators":9,"../components/deregister-platform-confirmation":17,"../components/register-platform-form":30,"../components/status-indicator":32,"../stores/platforms-store":49,"react":undefined,"react-router":undefined}],30:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var RegisterPlatformForm = React.createClass({displayName: "RegisterPlatformForm",
    getInitialState: function () {
        var state = {};
        
        state.method = 'discovery';

        state.name = state.discovery_address = state.ipaddress = state.serverKey = state.publicKey = state.secretKey = '';
        state.protocol = 'tcp';

        return state;
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
    _onSubmit: function (e) {
        e.preventDefault();
        var address = (this.state.method === "discovery" ? this.state.discovery_address : this._formatAddress());
        platformManagerActionCreators.registerPlatform(this.state.name, address, this.state.method);
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
                registerForm = (
                    React.createElement("div", null, 
                        React.createElement("div", {className: "tableDiv"}, 
                            React.createElement("div", {className: "rowDiv"}, 
                                React.createElement("div", {className: "cellDiv firstCell"}, 
                                    React.createElement("label", {className: "formLabel"}, "Name"), 
                                    React.createElement("input", {
                                        className: "form__control form__control--block inputField", 
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
                                        className: "form__control form__control--block inputField", 
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
            React.createElement("form", {className: "register-platform-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, "Register platform"), 
                registerForm

            )
        );
    },
});

module.exports = RegisterPlatformForm;


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-manager-action-creators":7,"react":undefined}],31:[function(require,module,exports){
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
    _onSubmit: function (e) {
        e.preventDefault();
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


},{"../action-creators/modal-action-creators":4,"../action-creators/platform-action-creators":5,"react":undefined}],32:[function(require,module,exports){
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

		var green = "#35B809";
		var red = "#FC0516";

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

        var textStyle = {
            fontWeight: "bold"
        }

		return (
		
        	React.createElement("div", {
        		className: classes.join(' '), 
        		onMouseEnter: this._keepVisible
        	}, 
				React.createElement("div", {style: colorStyle}), 
				React.createElement("br", null), 
				React.createElement("span", {style: textStyle}, this.state.statusMessage), 
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


},{"../action-creators/status-indicator-action-creators":9,"../stores/status-indicator-store":50,"react":undefined}],33:[function(require,module,exports){
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

    RECEIVE_PLATFORMS: null,
    RECEIVE_PLATFORM: null,

    RECEIVE_PLATFORM_STATUSES: null,
    TOGGLE_PLATFORMS_PANEL: null,

    RECEIVE_AGENT_STATUSES: null,
    RECEIVE_DEVICE_STATUSES: null,
    RECEIVE_PERFORMANCE_STATS: null,

    START_LOADING_DATA: null,
    END_LOADING_DATA: null,

    SHOW_CHARTS: null,
    ADD_TO_CHART: null,
    REMOVE_FROM_CHART: null,
    PIN_CHART: null,
    CHANGE_CHART_TYPE: null,
    CHANGE_CHART_REFRESH: null,
    REFRESH_CHART: null,
    REMOVE_CHART: null,
    LOAD_CHARTS: null,

    EXPAND_ALL: null,
    TOGGLE_ITEM: null,
    CHECK_ITEM: null,
    FILTER_ITEMS: null,

    // ADD_CONTROL_BUTTON: null,
    // REMOVE_CONTROL_BUTTON: null,
    TOGGLE_TAPTIP: null,
    HIDE_TAPTIP: null,

    RECEIVE_CHART_TOPICS: null
});


},{"react/lib/keyMirror":undefined}],34:[function(require,module,exports){
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


},{"../constants/action-types":33,"flux":undefined}],35:[function(require,module,exports){
'use strict';

function RpcError(error) {
    this.name = 'RpcError';
    this.code = error.code;
    this.message = error.message;
    this.data = error.data;
    this.response = error.response;
}
RpcError.prototype = Object.create(Error.prototype);
RpcError.prototype.constructor = RpcError;

module.exports = RpcError;


},{}],36:[function(require,module,exports){
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

            throw new RpcError(error);
        });
}

module.exports = RpcExchange;


},{"../../constants/action-types":33,"../../dispatcher":34,"../xhr":40,"./error":35,"node-uuid":undefined}],37:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange'),
};


},{"./error":35,"./exchange":36}],38:[function(require,module,exports){
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


},{"events":undefined}],39:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;


},{}],40:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":39,"./request":41}],41:[function(require,module,exports){
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


},{"./error":39,"bluebird":undefined,"jquery":undefined}],42:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38}],43:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38,"../stores/authorization-store":42}],44:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38,"../stores/authorization-store":42}],45:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38}],46:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _chartData = {};
var _showCharts = false;
var _chartTopics = {};

var chartStore = new Store();

chartStore.getPinnedCharts = function () {
    var pinnedCharts = [];

    for (var key in _chartData)
    {
        if (_chartData[key].hasOwnProperty("pinned") && (_chartData[key].pinned === true) && (_chartData[key].data.length > 0))
        {
            pinnedCharts.push(_chartData[key]);
        }
    }

    return JSON.parse(JSON.stringify(pinnedCharts));
};

chartStore.getData = function () {
    return JSON.parse(JSON.stringify(_chartData));
}

chartStore.getPinned = function (chartKey) {
    return (_chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].pinned : null);
}

chartStore.getType = function (chartKey) {
    var type = "line";

    if (_chartData.hasOwnProperty(chartKey))
    {
        if (_chartData[chartKey].hasOwnProperty("type"))
        {
            type = _chartData[chartKey].type;
        }
    }

    return type;
}

chartStore.getRefreshRate = function (chartKey) {
    return (_chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].refreshInterval : null);
}

chartStore.showCharts = function () {

    var showCharts = _showCharts;

    _showCharts = false;

    return showCharts;
}

chartStore.getChartTopics = function (parentUuid) {
    
    var topics = [];

    if (_chartTopics.hasOwnProperty(parentUuid))
    {
        topics = JSON.parse(JSON.stringify(_chartTopics[parentUuid]));

        if (topics.length)
        {    
            if (_chartData !== {})
            {
                // Filter out any topics that are already in charts
                topics = topics.filter(function (topic) {

                    var topicInChart = false;

                    if (_chartData.hasOwnProperty(topic.name))
                    {
                        var path = _chartData[topic.name].series.find(function (item) {
                            return item.topic === topic.path;
                        });

                        topicInChart = (path ? true : false);
                    }

                    return !topicInChart;
                });
            }
        }
    }

    return topics;
}

chartStore.getTopicInCharts = function (topic, topicName)
{
    var itemInChart;

    if (_chartData.hasOwnProperty(topicName))
    {
        _chartData[topicName].series.find(function (series) {

            itemInChart = (series.topic === topic);

            return itemInChart;
        });
    }

    return itemInChart;
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
                        refreshInterval: (action.panelItem.hasOwnProperty("refreshInterval") ? action.panelItem.refreshInterval :15000),
                        pinned: (action.panelItem.hasOwnProperty("pinned") ? action.panelItem.pinned : false),
                        type: (action.panelItem.hasOwnProperty("chartType") ? action.panelItem.chartType : "line"),
                        data: convertTimeToSeconds(action.panelItem.data),
                        chartKey: action.panelItem.name,
                        series: [ setChartItem(action.panelItem) ]
                    };

                    _chartData[action.panelItem.name] = chartObj;
                    chartStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.LOAD_CHARTS:           

            _chartData = {};

            action.charts.forEach(function (chart) {
                _chartData[chart.chartKey] = JSON.parse(JSON.stringify(chart));
            });
            
            chartStore.emitChange();

            break;

        case ACTION_TYPES.REMOVE_FROM_CHART:
            
            if (_chartData.hasOwnProperty(action.panelItem.name))
            {
                removeSeries(action.panelItem.name, action.panelItem.uuid);

                if (_chartData.hasOwnProperty(action.panelItem.name))
                {
                    if (_chartData[action.panelItem.name].length === 0)
                    {
                        delete _chartData[name];
                    }
                }

                chartStore.emitChange();
            }

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

        case ACTION_TYPES.SHOW_CHARTS:

            if (action.emitChange)
            {
                _showCharts = true;
                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.RECEIVE_CHART_TOPICS:
            _chartTopics = {};

            var chartTopics = JSON.parse(JSON.stringify(action.topics));

            _chartTopics[action.platform.uuid] = chartTopics;            

            chartStore.emitChange();
            break;

        case ACTION_TYPES.REMOVE_CHART:

            var name = action.name;

            if (_chartData.hasOwnProperty(name))
            {

                delete _chartData[name];

                chartStore.emitChange();
            }

            break;
    }

    function setChartItem(item) {

        var chartItem = {
            name: item.name,
            uuid: item.uuid,
            path: item.path,
            parentUuid: item.parentUuid,
            parentType: item.parentType,
            parentPath: item.parentPath,
            topic: item.topic
        }

        return chartItem;
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
                _chartData[item.name].series.push(setChartItem(item));
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

                if (typeof value === 'string')
                {
                    value = value.replace('+00:00', '');
                }
                
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38,"../stores/authorization-store":42}],47:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');
var chartStore = require('../stores/platform-chart-store');

var _pointsOrder = 0;
var _devicesOrder = 1;
var _buildingsOrder = 2;
var _agentsOrder = 3;

var _items = {
    "platforms": {}
};

var _expanded = false;
var _itemTypes = ["platforms", "buildings", "agents", "devices", "points"];

var _badLabel = "Unhealthy";
var _goodLabel = "Healthy";
var _unknownLabel = "Unknown Status";

var _loadingDataComplete = {};
var _lastCheck = false;

var platformsPanelItemsStore = new Store();

platformsPanelItemsStore.getLastCheck = function (topic)
{
    return _lastCheck;
}

platformsPanelItemsStore.findTopicInTree = function (topic)
{
    var path = [];

    var topicParts = topic.split("/");

    if (topic.indexOf("datalogger/platforms") > -1) // if a platform instance
    {
        for (var key in _items.platforms)
        {
            if (key === topicParts[2])
            {
                // path = ["platforms", uuid];

                if (_items.platforms[key].hasOwnProperty("points"))
                {
                    _items.platforms[key].points.children.find(function (point) {

                        var found = (point === topic);

                        if (found)
                        {
                            path = _items.platforms[key].points[point].path;
                        }

                        return found;
                    });
                }

                break;
            }
        }
    }
    else // else a device point
    {        
        var buildingName = topicParts[1];

        for (var key in _items.platforms)
        { //_items.platforms.children.find(function (platform) {

            var platform = _items.platforms[key];       
            var foundPlatform = false;

            if (platform.hasOwnProperty("buildings"))
            {
                platform.buildings.children.find(function (buildingUuid) {

                    var foundBuilding = (platform.buildings[buildingUuid].name === buildingName);

                    if (foundBuilding)
                    {
                        var parent = platform.buildings[buildingUuid];

                        for (var i = 2; i <= topicParts.length - 2; i++)
                        {
                            var deviceName = topicParts[i];

                            if (parent.hasOwnProperty("devices"))
                            {
                                parent.devices.children.find(function (deviceUuid) {

                                    var foundDevice = (parent.devices[deviceUuid].name === deviceName);

                                    if (foundDevice) 
                                    {
                                        parent = parent.devices[deviceUuid];
                                    }

                                    return foundDevice;
                                });
                            }
                        }
                        
                        if (parent.hasOwnProperty("points"))
                        {
                            parent.points.children.find(function (point) {
                                var foundPoint = (parent.points[point].topic === topic);

                                if (foundPoint)
                                {
                                    path = parent.points[point].path;

                                    foundPlatform = true;
                                }

                                return foundPoint;
                            });
                        }                        
                    }

                    return foundBuilding;
                });                
            }

            if (foundPlatform)
            {
                break;
            }
        }
    }

    return JSON.parse(JSON.stringify(path));
} 

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

platformsPanelItemsStore.getLoadingComplete = function (panelItem) {

    var loadingComplete = null;

    if (_loadingDataComplete.hasOwnProperty(panelItem.uuid))
    {
        loadingComplete = _loadingDataComplete[panelItem.uuid];
    }

    return loadingComplete;
};

platformsPanelItemsStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.CLEAR_AUTHORIZATION:

            _items.platforms = {};
            _loadingDataComplete = {};
            _expanded = false;
            _lastCheck = false;

            break;
        case ACTION_TYPES.FILTER_ITEMS:

            var filterTerm = action.filterTerm;
            var filterStatus = action.filterStatus;
            platformsPanelItemsStore.loadFilteredItems(filterTerm, filterStatus);
            _lastCheck = false;

            platformsPanelItemsStore.emitChange();

            break;
        case ACTION_TYPES.EXPAND_ALL:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            
            var expanded = (item.expanded !== null ? !item.expanded : true);

            expandAllChildren(item, expanded);
            _lastCheck = false;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.TOGGLE_ITEM:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            item.expanded = !item.expanded;
            _lastCheck = false;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.CHECK_ITEM:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            item.checked = action.checked;
            _lastCheck = action.checked;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.START_LOADING_DATA:

            _loadingDataComplete[action.panelItem.uuid] = false;
            _lastCheck = false;

            break;

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            
            var platforms = action.platforms;

            platforms.forEach(function (platform)
            {
                _items["platforms"][platform.uuid] = platform; 
                
                var platformItem = _items["platforms"][platform.uuid];
                platformItem.path = ["platforms", platform.uuid];

                platformItem.status = platform.health.status.toUpperCase();
                platformItem.statusLabel = getStatusLabel(platformItem.status);
                platformItem.context = platform.health.context;
                platformItem.children = [];
                platformItem.type = "platform";
                platformItem.visible = true;
                platformItem.expanded = null;
                // platformItem.name = (platform.name === null ? platform.uuid : platform.name);

                // loadAgents(platform);                
                // loadDevices(platform);
            });

            var platformsToRemove = [];

            for (var key in _items.platforms)
            {
                var match = platforms.find(function (platform) {
                    return key === platform.uuid;
                });

                if (!match)
                {
                    platformsToRemove.push(key);
                }
            }

            platformsToRemove.forEach(function (uuid) {
                delete _items.platforms[uuid];
            });            
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.agents.length > 0)
            {
                insertAgents(platform, action.agents);
            }

            // platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.devices.length > 0)
            {
                insertDevices(platform, action.devices);
            }

            // platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_PERFORMANCE_STATS:
            
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
                        platform.points.name = "Performance";
                        platform.points.expanded = false;
                        platform.points.visible = true;
                        platform.points.children = [];
                        platform.points.type = "type";
                        platform.points.status = platform.status;
                        platform.points.statusLabel = getStatusLabel(platform.status);
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

                            pointProps.checked = chartStore.getTopicInCharts(pointProps.topic, pointProps.name);

                            pointProps.status = platform.status;
                            pointProps.statusLabel = getStatusLabel(platform.status);
                            pointProps.children = [];
                            pointProps.type = "point";
                            pointProps.sortOrder = 0;
                            platform.points.children.push(uuid); 
                            platform.points[uuid] = pointProps;
                        });

                    }

                    break;
            }

            _lastCheck = false;

            platformsPanelItemsStore.emitChange();
            break;

        case ACTION_TYPES.END_LOADING_DATA:

            _loadingDataComplete[action.panelItem.uuid] = true;

            updatePlatformStatus(action.panelItem.uuid);
            
            _lastCheck = false;

            platformsPanelItemsStore.emitChange();

            break;
    }

    function insertAgents(platform, agents)
    {
        var agentsToInsert = JSON.parse(JSON.stringify(agents));

        platform.agents = {};
        platform.agents.path = JSON.parse(JSON.stringify(platform.path));
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

        var agentsHealth;

        agentsToInsert.forEach(function (agent)
        {
            var agentProps = agent;
            agentProps.expanded = false;
            agentProps.visible = true;
            agentProps.path = JSON.parse(JSON.stringify(platform.agents.path));
            agentProps.path.push(agent.uuid);
            agentProps.status = agent.health.status.toUpperCase();
            agentProps.statusLabel = getStatusLabel(agentProps.status);
            agentProps.context = agent.health.context;
            agentProps.children = [];
            agentProps.type = "agent";
            agentProps.sortOrder = 0;
            platform.agents.children.push(agent.uuid); 
            platform.agents[agent.uuid] = agentProps;

            agentsHealth = checkStatuses(agentsHealth, agentProps);
        });

        platform.agents.status = agentsHealth;
        platform.agents.statusLabel = getStatusLabel(agentsHealth);
    }

    function insertBuilding(platform, uuid, name)
    {
        if (platform.children.indexOf("buildings") < 0)
        {
            platform.children.push("buildings");

            platform.buildings = {};
            platform.buildings.name = "Buildings";
            platform.buildings.children = [];
            platform.buildings.path = JSON.parse(JSON.stringify(platform.path));
            platform.buildings.path.push("buildings");
            platform.buildings.expanded = false;
            platform.buildings.visible = true;
            platform.buildings.type = "type";
            platform.buildings.sortOrder = _buildingsOrder;
        }

        if (!platform.buildings.hasOwnProperty(uuid))
        {
            var buildingProps = {};
            buildingProps.name = name;
            buildingProps.uuid = uuid;

            buildingProps.expanded = false;
            buildingProps.visible = true;
            buildingProps.path = JSON.parse(JSON.stringify(platform.buildings.path));
            buildingProps.path.push(buildingProps.uuid);
            buildingProps.status = "UNKNOWN";
            buildingProps.statusLabel = getStatusLabel(buildingProps.status);
            buildingProps.children = ["devices"];
            buildingProps.type = "building";
            buildingProps.sortOrder = 0;          

            buildingProps.devices = {};
            buildingProps.devices.path = JSON.parse(JSON.stringify(buildingProps.path));
            buildingProps.devices.path.push("devices");
            buildingProps.devices.name = "Devices";
            buildingProps.devices.expanded = false;
            buildingProps.devices.visible = true;
            buildingProps.devices.children = [];
            buildingProps.devices.type = "type";
            buildingProps.devices.sortOrder = _devicesOrder;


            //TODO: add building points
            // buildingProps.children.push("points");
            // buildingProps.points = [];

            platform.buildings.children.push(buildingProps.uuid);
            platform.buildings[buildingProps.uuid] = buildingProps;            
        }

        return platform.buildings[uuid];
    }

    function insertDevices(platform, devices)
    {
        var devicesToInsert = JSON.parse(JSON.stringify(devices));

        var buildings = [];

        if (devicesToInsert.length > 0)
        {
            //Make a 2D array where each row is another level 
            // of devices and subdevices in the tree
            var nestedDevices = [];
            var level = 3;
            var deviceCount = 0;

            while (deviceCount < devicesToInsert.length)
            {
                var levelList = [];

                devicesToInsert.forEach(function (device) {

                    var deviceParts = device.path.split("/");

                    if (deviceParts.length === level)
                    {
                        levelList.push(device);
                        ++deviceCount;
                    }
                });

                if (levelList.length > 0)
                {
                    nestedDevices.push(levelList);
                }

                ++level;
            }
        }

        //Now we can add each row of devices, confident
        // that any parent devices will be added to the tree
        // before their subdevices
        nestedDevices.forEach(function (level, row) {

            level.forEach(function (device) {
                
                var pathParts = device.path.split("/");
                var buildingUuid = pathParts[0] + "_" + pathParts[1];
                var buildingName = pathParts[1];
                var legendInfo = pathParts[0] + " > " + buildingName;                

                var building = insertBuilding(platform, buildingUuid, buildingName);                

                insertDevice(device, building, legendInfo, row);

                var alreadyInTree = buildings.find(function (building) {
                    return building.uuid === buildingUuid;
                });

                if (!alreadyInTree) {
                    buildings.push(building);
                }

            });
        });

        buildings.forEach(function (blg) {
            
            var buildingHealth;

            blg.devices.children.forEach(function (device) {
                buildingHealth = checkStatuses(buildingHealth, blg.devices[device]);                
            });

            blg.devices.status = buildingHealth;   
            blg.devices.statusLabel = getStatusLabel(buildingHealth);

            blg.status = buildingHealth;
            blg.statusLabel = getStatusLabel(buildingHealth);
        });

        
        var buildingsHealth;

        buildings.forEach(function (blg) {
            buildingsHealth = checkStatuses(buildingsHealth, blg);            
        });

        platform.buildings.status = buildingsHealth;
        platform.buildings.statusLabel = getStatusLabel(buildingsHealth);
    }

    function insertDevice(device, building, legendInfo, row)
    {        
        switch (row)
        {
            case 0:
                //top-level devices

                var deviceParts = device.path.split("/");

                var deviceProps = {};
                deviceProps.name = deviceParts[deviceParts.length - 1];
                deviceProps.uuid = device.path.replace(/\//g, '_');
                deviceProps.expanded = false;
                deviceProps.visible = true;
                deviceProps.path = JSON.parse(JSON.stringify(building.devices.path));
                deviceProps.path.push(deviceProps.uuid);
                deviceProps.status = device.health.status.toUpperCase();
                deviceProps.statusLabel = getStatusLabel(deviceProps.status);
                deviceProps.context = device.health.context;
                deviceProps.children = [];
                deviceProps.type = "device";
                deviceProps.sortOrder = 0;

                deviceProps.legendInfo = legendInfo + " > " + deviceProps.name;

                checkForPoints(deviceProps, device);

                building.devices.children.push(deviceProps.uuid);
                building.devices[deviceProps.uuid] = deviceProps;

                break;
            default:
                //subdevices:
                var deviceParts = device.path.split("/");

                var subDeviceLevel = deviceParts.length - 1;

                // the top two spots in the device path are the campus and building,
                // so add 2 to the row and that should equal the subdevice's level
                if (subDeviceLevel !== row + 2)
                {
                    console.log("wrong level number");
                }
                else
                {
                    //Now find the subdevice's parent device by using the parts of its path
                    // to walk the tree
                    var parentPath = JSON.parse(JSON.stringify(building.path));
                    var parentDevice = building; // start at the building
                    var currentLevel = 2; // the level of the top-level devices

                    while (currentLevel < subDeviceLevel)
                    {
                        var parentDeviceUuid = deviceParts[0];

                        for (var i = 1; i <= currentLevel; i++)
                        {
                            parentDeviceUuid = parentDeviceUuid + "_" + deviceParts[i];
                        }

                        parentDevice = parentDevice.devices;
                        parentDevice = parentDevice[parentDeviceUuid];
                        ++currentLevel;
                    }

                    var deviceProps = {};
                    deviceProps.name = deviceParts[subDeviceLevel];
                    deviceProps.uuid = device.path.replace(/ \/ /g, '_');
                    deviceProps.expanded = false;
                    deviceProps.visible = true;
                    deviceProps.path = JSON.parse(JSON.stringify(parentDevice.path));
                    deviceProps.path.push("devices");
                    deviceProps.path.push(deviceProps.uuid);
                    deviceProps.status = device.health.status.toUpperCase();
                    deviceProps.statusLabel = getStatusLabel(deviceProps.status);
                    deviceProps.context = device.health.context;
                    deviceProps.children = [];
                    deviceProps.type = "device";
                    deviceProps.sortOrder = 0;

                    deviceProps.legendInfo = parentDevice.legendInfo + " > " + deviceProps.name;

                    checkForPoints(deviceProps, device);

                    //If we haven't added any subdevices to the parent device 
                    // yet, initialize its "devices" child
                    if (parentDevice.children.indexOf("devices") < 0)
                    {
                        parentDevice.children.push("devices");

                        parentDevice.devices = {};
                        parentDevice.devices.path = JSON.parse(JSON.stringify(parentDevice.path));
                        parentDevice.devices.path.push("devices");
                        parentDevice.devices.name = "Devices";
                        parentDevice.devices.expanded = false;
                        parentDevice.devices.visible = true;
                        parentDevice.devices.children = [];
                        parentDevice.devices.type = "type";
                        parentDevice.devices.sortOrder = _devicesOrder;
                        parentDevice.devices.status = deviceProps.status;
                        parentDevice.devices.statusLabel = getStatusLabel(deviceProps.status);
                        parentDevice.devices.context = deviceProps.context;
                    }                    

                    parentDevice.devices.children.push(deviceProps.uuid);
                    parentDevice.devices[deviceProps.uuid] = deviceProps; 

                    if (parentDevice.devices.children.length > 1)
                    {
                        updateDeviceGroupStatus(parentDevice);
                    }
                }
              
                break;
        }
    }

    function checkForPoints(item, data)
    {
        if (data.hasOwnProperty("points"))
        {
            if (item.children.indexOf("points") < 0)
            {
                item.children.push("points");

                item.points = {};
                item.points.path = JSON.parse(JSON.stringify(item.path));
                item.points.path.push("points");
                item.points.name = "Points";
                item.points.expanded = false;
                item.points.visible = true;
                item.points.status = item.status;
                item.points.statusLabel = getStatusLabel(item.status);
                item.points.children = [];
                item.points.type = "type";
                item.points.sortOrder = _pointsOrder;
            }

            data.points.forEach(function (pointName) {

                var pointPath = data.path + "/" + pointName;                
                var platformUuid = item.path[1];

                var pattern = /[!@#$%^&*()+\-=\[\]{};':"\\|, .<>\/?]/g

                var pointProps = {}; 
                pointProps.topic = pointPath;  
                pointProps.name = pointName;
                pointProps.uuid = pointPath.replace(pattern, '_');
                pointProps.expanded = false;
                pointProps.visible = true;
                pointProps.path = JSON.parse(JSON.stringify(item.points.path));
                pointProps.path.push(pointProps.uuid);
                pointProps.parentPath = item.legendInfo;
                pointProps.parentType = item.type;
                pointProps.parentUuid = platformUuid;
                pointProps.status = item.status;
                pointProps.statusLabel = getStatusLabel(item.status);
                pointProps.context = item.context;
                pointProps.children = [];
                pointProps.type = "point";
                pointProps.sortOrder = 0;
                pointProps.checked = chartStore.getTopicInCharts(pointProps.topic, pointProps.name);

                item.points.children.push(pointProps.uuid);
                item.points[pointProps.uuid] = pointProps;

            });
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

    function updatePlatformStatus(uuid)
    {
        if (_items.platforms.hasOwnProperty(uuid))
        {
            var platform = JSON.parse(JSON.stringify(_items.platforms[uuid]));

            if (_items.platforms[uuid].hasOwnProperty("agents"))
            {
                var agentsHealth = _items.platforms[uuid].agents.status; 
                platform.status = checkStatuses(agentsHealth, platform);
            }

            if (platform.status === "GOOD" || platform.status === "UNKNOWN")
            {
                if (_items.platforms[uuid].hasOwnProperty("buildings"))
                {
                    var buildingsHealth = _items.platforms[uuid].buildings.status;
                    platform.status = checkStatuses(buildingsHealth, platform);
                }
            }
            
            if (platform.status === "GOOD" || platform.status === "UNKNOWN")
            {
                if (_items.platforms[uuid].hasOwnProperty("points"))
                {
                    var pointsHealth = _items.platforms[uuid].points.status;  
                    platform.status = checkStatuses(pointsHealth, platform);  
                }
            }

            if (platform.status !== _items.platforms[uuid].status)
            {
                _items.platforms[uuid].status = platform.status;
                _items.platforms[uuid].statusLabel = getStatusLabel(platform.status);
                _items.platforms[uuid].context = "Status problems found."
            }
        }        
    }

    function updateDeviceGroupStatus(parent)
    {        
        var parentDevice = JSON.parse(JSON.stringify(parent));

        if (parentDevice.hasOwnProperty("devices"))
        {
            parentDevice.devices.children.forEach(function (uuid) {
                var subDeviceHealth = checkStatuses(parentDevice.devices[uuid].status, parentDevice.devices);

                if (subDeviceHealth !== parent.devices.status)
                {
                    parent.devices.status = subDeviceHealth;
                    parent.devices.statusLabel = getStatusLabel(subDeviceHealth);
                }
            });            
        }    

        var deviceGroupHealth = checkStatuses(parent.devices.status, parentDevice);
        if (deviceGroupHealth !== parent.status)
        {
            parent.status = deviceGroupHealth;
            parent.statusLabel = getStatusLabel(deviceGroupHealth);
            parent.context = "Status problems found."
        }
    }

    function checkStatuses(health, item)
    {
        if (typeof health === "undefined")
        {
            health = item.status;
        }
        else
        {
            switch (health)
            {
                case "UNKNOWN":

                    switch (item.status)
                    {
                        case "BAD":
                            health = "BAD";
                            break;
                    }
                    break;
                case "GOOD":
                    health = item.status;
            }
        }

        return health;
    }

    function getStatusLabel(status)
    {
        var statusLabel;

        switch (status)
        {
            case "GOOD":
                statusLabel = _goodLabel;
                break;
            case "BAD":
                statusLabel = _badLabel;
                break;
            case "UNKNOWN":
                statusLabel = _unknownLabel;
                break;
        }

        return statusLabel;
    }
});

module.exports = platformsPanelItemsStore;


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38,"../stores/platform-chart-store":46}],48:[function(require,module,exports){
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
        case ACTION_TYPES.CLEAR_AUTHORIZATION:  
            _expanded = null;
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38}],49:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _platforms = null;

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

platformsStore.getVcInstance = function () 
{
    var vc;

    if (_platforms)
    {
        if (_platforms.length)
        {
            vc = _platforms.find(function (platform) {

                var hasVcAgent = false;

                if (platform.agents)
                {
                    if (platform.agents.length)
                    {
                        var vcAgent = platform.agents.find(function (agent) {     
                            return agent.name.toLowerCase().indexOf("volttroncentral") > -1;
                        });

                        if (vcAgent)
                        {
                            hasVcAgent = true;
                        }
                    }
                }

                return hasVcAgent;
            });
        }
    }

    return vc;
};

platformsStore.getHistorianRunning = function (platform) {

    var historianRunning = false;

    if (platform)
    {
        if (platform.hasOwnProperty("agents"))
        {
            var historian = platform.agents.find(function (agent) {     
                return agent.name.toLowerCase().indexOf("historian") > -1;
            });

            if (historian)
            {
                historianRunning = ((historian.process_id !== null) && (historian.return_code === null));
            }
        }        
    }

    return historianRunning;
};

platformsStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _platforms = null;
            break;

        case ACTION_TYPES.RECEIVE_PLATFORMS:
            _platforms = action.platforms;
            platformsStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORM:
            platformsStore.emitChange();
            break;
    }
});

module.exports = platformsStore;


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38,"./authorization-store":42}],50:[function(require,module,exports){
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


},{"../constants/action-types":33,"../dispatcher":34,"../lib/store":38}]},{},[1]);
