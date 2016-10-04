(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _reactRouter = require('react-router');

var _platformManager = require('./components/platform-manager');

var _platformManager2 = _interopRequireDefault(_platformManager);

var _configureDevices = require('./components/configure-devices');

var _configureDevices2 = _interopRequireDefault(_configureDevices);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var React = require('react');
var ReactDOM = require('react-dom');

var authorizationStore = require('./stores/authorization-store');
var platformsPanelItemsStore = require('./stores/platforms-panel-items-store');
var devicesStore = require('./stores/devices-store');
var Dashboard = require('./components/dashboard');
var LoginForm = require('./components/login-form');
var PageNotFound = require('./components/page-not-found');
var Platform = require('./components/platform');

var Platforms = require('./components/platforms');

var PlatformCharts = require('./components/platform-charts');
var Navigation = require('./components/navigation');
var devicesActionCreators = require('./action-creators/devices-action-creators');

var _afterLoginPath = '/dashboard';

var checkAuth = function checkAuth(AuthComponent) {
    return function (_React$Component) {
        _inherits(_class, _React$Component);

        function _class() {
            _classCallCheck(this, _class);

            return _possibleConstructorReturn(this, Object.getPrototypeOf(_class).apply(this, arguments));
        }

        _createClass(_class, [{
            key: 'componentWillMount',
            value: function componentWillMount() {

                if (AuthComponent.displayName !== 'LoginForm' && AuthComponent.displayName !== 'PageNotFound') {
                    if (!authorizationStore.getAuthorization()) {
                        _reactRouter.hashHistory.replace('/login');
                    }
                } else if (authorizationStore.getAuthorization()) {
                    _reactRouter.hashHistory.replace(_afterLoginPath);
                }
            }
        }, {
            key: 'render',
            value: function render() {
                return React.createElement(AuthComponent, this.props);
            }
        }]);

        return _class;
    }(React.Component);
};

var PublicExterior = React.createClass({
    displayName: 'PublicExterior',

    render: function render() {

        return React.createElement(
            'div',
            { className: 'public-exterior not-logged-in' },
            React.createElement(
                'div',
                { className: 'main' },
                React.createElement(Navigation, null),
                this.props.children
            )
        );
    }
});

var routes = React.createElement(
    _reactRouter.Router,
    { history: _reactRouter.hashHistory },
    React.createElement(
        _reactRouter.Route,
        { path: '/', component: checkAuth(_platformManager2.default) },
        React.createElement(_reactRouter.IndexRedirect, { to: 'dashboard' }),
        React.createElement(_reactRouter.Route, { path: 'dashboard', component: checkAuth(Dashboard) }),
        React.createElement(_reactRouter.Route, { path: 'platforms', component: checkAuth(Platforms) }),
        React.createElement(_reactRouter.Route, { path: 'platform/:uuid', component: checkAuth(Platform) }),
        React.createElement(_reactRouter.Route, { path: 'configure-devices', component: checkAuth(_configureDevices2.default) }),
        React.createElement(_reactRouter.Route, { path: 'charts', component: checkAuth(PlatformCharts) })
    ),
    React.createElement(
        _reactRouter.Route,
        { path: '/', component: checkAuth(PublicExterior) },
        React.createElement(_reactRouter.Route, { path: 'login', component: checkAuth(LoginForm) })
    ),
    React.createElement(_reactRouter.Route, { path: '*', component: PageNotFound })
);

ReactDOM.render(routes, document.getElementById('app'), function (Handler) {
    authorizationStore.addChangeListener(function () {
        if (authorizationStore.getAuthorization() && this.router.isActive('/login')) {
            this.router.replace(_afterLoginPath);
        } else if (!authorizationStore.getAuthorization() && !this.router.isActive('/login')) {
            this.router.replace('/login');
        }
    }.bind(this));

    platformsPanelItemsStore.addChangeListener(function () {
        if (platformsPanelItemsStore.getLastCheck() && authorizationStore.getAuthorization()) {
            if (!this.router.isActive('charts')) {
                this.router.push('/charts');
            }
        }
    }.bind(this));

    devicesStore.addChangeListener(function () {

        if (devicesStore.getNewScan()) {
            if (!this.router.isActive('configure-devices')) {
                this.router.push('/configure-devices');
            }
        }
    }.bind(this));

    // var handleKeyDown = function (keydown) {

    //     if (this.router.isActive('configure-devices'))
    //     {
    //         if (keydown.target.nodeName !== "INPUT")
    //         {
    //             devicesActionCreators.handleKeyDown(keydown);    
    //         }            
    //     }
    // }

    // document.addEventListener("keydown", handleKeyDown.bind(this));
});

},{"./action-creators/devices-action-creators":4,"./components/configure-devices":16,"./components/dashboard":25,"./components/login-form":30,"./components/navigation":32,"./components/page-not-found":35,"./components/platform":39,"./components/platform-charts":37,"./components/platform-manager":38,"./components/platforms":42,"./stores/authorization-store":57,"./stores/devices-store":60,"./stores/platforms-panel-items-store":63,"react":undefined,"react-dom":undefined,"react-router":undefined}],2:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var RpcExchange = require('../lib/rpc/exchange');

var consoleActionCreators = {
    toggleConsole: function toggleConsole() {
        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_CONSOLE
        });
    },
    updateComposerValue: function updateComposerValue(value) {
        dispatcher.dispatch({
            type: ACTION_TYPES.UPDATE_COMPOSER_VALUE,
            value: value
        });
    },
    makeRequest: function makeRequest(opts) {
        new RpcExchange(opts).promise.catch(function ignore() {});
    }
};

module.exports = consoleActionCreators;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/rpc/exchange":51}],3:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var controlButtonActionCreators = {
	toggleTaptip: function toggleTaptip(name) {
		dispatcher.dispatch({
			type: ACTION_TYPES.TOGGLE_TAPTIP,
			name: name
		});
	},
	hideTaptip: function hideTaptip(name) {
		dispatcher.dispatch({
			type: ACTION_TYPES.HIDE_TAPTIP,
			name: name
		});
	}
};

module.exports = controlButtonActionCreators;

},{"../constants/action-types":48,"../dispatcher":49}],4:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

var devicesActionCreators = {
    configureDevices: function configureDevices(platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CONFIGURE_DEVICES,
            platform: platform
        });
    },
    addDevices: function addDevices(platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.ADD_DEVICES,
            platform: platform
        });
    },
    scanForDevices: function scanForDevices(platformUuid, bacnetProxyUuid, low, high, address) {

        var authorization = authorizationStore.getAuthorization();

        var params = {};

        if (low) {
            params.low_device_id = Number(low);
        }

        if (high) {
            params.high_device_id = Number(high);
        }

        if (address) {
            params.target_address = address;
        }

        return new rpc.Exchange({
            method: 'platform.uuid.' + platformUuid + '.agent.uuid.' + bacnetProxyUuid + '.who_is',
            authorization: authorization,
            params: params
        }).promise.then(function (result) {
            dispatcher.dispatch({
                type: ACTION_TYPES.LISTEN_FOR_IAMS,
                platformUuid: platformUuid,
                bacnetProxyUuid: bacnetProxyUuid,
                low_device_id: low,
                high_device_id: high,
                target_address: address
            });
        }).catch(rpc.Error, function (error) {

            error.message = "Unable to scan for devices. " + error.message + ".";

            handle401(error, error.message);
        });
    },
    deviceDetected: function deviceDetected(device, platform, bacnet) {
        dispatcher.dispatch({
            type: ACTION_TYPES.DEVICE_DETECTED,
            platform: platform,
            bacnet: bacnet,
            device: device
        });
    },
    pointReceived: function pointReceived(data, platform, bacnet) {
        dispatcher.dispatch({
            type: ACTION_TYPES.POINT_RECEIVED,
            platform: platform,
            bacnet: bacnet,
            data: data
        });
    },
    cancelScan: function cancelScan(platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CANCEL_SCANNING,
            platform: platform
        });
    },
    handleKeyDown: function handleKeyDown(keydown) {
        dispatcher.dispatch({
            type: ACTION_TYPES.HANDLE_KEY_DOWN,
            keydown: keydown
        });
    },
    focusOnDevice: function focusOnDevice(deviceId, address) {
        dispatcher.dispatch({
            type: ACTION_TYPES.FOCUS_ON_DEVICE,
            deviceId: deviceId,
            address: address
        });

        console.log("focused on device");
    },
    // listDetectedDevices: function (platform) {
    //     dispatcher.dispatch({
    //         type: ACTION_TYPES.LIST_DETECTED_DEVICES,
    //         platform: platform
    //     });
    // },
    configureDevice: function configureDevice(device) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            // expanded:false, 
            // "filter":[3000124], 
            device_id: Number(device.id),
            proxy_identity: "platform.bacnet_proxy",
            address: device.address
        };

        return new rpc.Exchange({
            method: 'platform.uuid.' + device.platformUuid + '.agent.uuid.' + device.bacnetProxyUuid + '.publish_bacnet_props',
            authorization: authorization,
            params: params
        }).promise.then(function (result) {

            dispatcher.dispatch({
                type: ACTION_TYPES.CONFIGURE_DEVICE,
                device: device
            });
        }).catch(rpc.Error, function (error) {

            error.message = "Unable to receive points. " + error.message + ".";

            handle401(error, error.message);
        });
    },
    toggleShowPoints: function toggleShowPoints(device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_SHOW_POINTS,
            device: device
        });
    },
    // configureRegistry: function (device) {
    //     dispatcher.dispatch({
    //         type: ACTION_TYPES.CONFIGURE_REGISTRY,
    //         device: device
    //     });
    // },
    // generateRegistry: function (device) {
    //     dispatcher.dispatch({
    //         type: ACTION_TYPES.GENERATE_REGISTRY,
    //         device: device
    //     });
    // },
    cancelRegistry: function cancelRegistry(device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CANCEL_REGISTRY,
            device: device
        });
    },
    loadRegistry: function loadRegistry(deviceId, deviceAddress, csvData, fileName) {
        dispatcher.dispatch({
            type: ACTION_TYPES.LOAD_REGISTRY,
            deviceId: deviceId,
            deviceAddress: deviceAddress,
            data: csvData.filter(function (row) {
                return row.length > 0;
            }),
            file: fileName
        });
    },
    editRegistry: function editRegistry(device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.EDIT_REGISTRY,
            device: device
        });
    },
    updateRegistry: function updateRegistry(deviceId, deviceAddress, selectedPoints, attributes) {
        dispatcher.dispatch({
            type: ACTION_TYPES.UPDATE_REGISTRY,
            deviceId: deviceId,
            deviceAddress: deviceAddress,
            selectedPoints: selectedPoints,
            attributes: attributes
        });
    },
    saveRegistry: function saveRegistry(deviceId, deviceAddress, values) {
        dispatcher.dispatch({
            type: ACTION_TYPES.SAVE_REGISTRY,
            deviceId: deviceId,
            deviceAddress: deviceAddress,
            data: values
        });
    },
    saveConfig: function saveConfig(device, settings) {
        dispatcher.dispatch({
            type: ACTION_TYPES.SAVE_CONFIG,
            device: device,
            settings: settings
        });
    }
};

function handle401(error, message, highlight, orientation) {
    if (error.code && error.code === 401 || error.response && error.response.status === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error
        });

        platformManagerActionCreators.clearAuthorization();
    } else if (message) {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = devicesActionCreators;

},{"../action-creators/status-indicator-action-creators":10,"../constants/action-types":48,"../dispatcher":49,"../lib/rpc":52,"../stores/authorization-store":57}],5:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var modalActionCreators = {
	openModal: function openModal(content) {
		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_MODAL,
			content: content
		});
	},
	closeModal: function closeModal() {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_MODAL
		});
	}
};

module.exports = modalActionCreators;

},{"../constants/action-types":48,"../dispatcher":49}],6:[function(require,module,exports){
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
    loadPlatform: function loadPlatform(platform) {
        platformActionCreators.loadAgents(platform);
        platformActionCreators.loadCharts(platform);
    },
    loadAgents: function loadAgents(platform) {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.list_agents',
            authorization: authorization
        }).promise.then(function (agentsList) {
            platform.agents = agentsList;

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PLATFORM,
                platform: platform
            });

            if (!agentsList.length) {
                return;
            }

            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.status_agents',
                authorization: authorization
            }).promise.then(function (agentStatuses) {
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
                    platform: platform
                });
            }).catch(rpc.Error, function (error) {
                handle401(error);
            });
        }).catch(rpc.Error, function (error) {
            handle401(error);
        });
    },
    startAgent: function startAgent(platform, agent) {
        var authorization = authorizationStore.getAuthorization();

        agent.actionPending = true;

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_PLATFORM,
            platform: platform
        });

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.start_agent',
            params: [agent.uuid],
            authorization: authorization
        }).promise.then(function (status) {
            agent.process_id = status.process_id;
            agent.return_code = status.return_code;
        }).catch(rpc.Error, function (error) {
            handle401(error, "Unable to start agent " + agent.name + ": " + error.message, agent.name);
        }).finally(function () {
            agent.actionPending = false;

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PLATFORM,
                platform: platform
            });
        });
    },
    stopAgent: function stopAgent(platform, agent) {
        var authorization = authorizationStore.getAuthorization();

        agent.actionPending = true;

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_PLATFORM,
            platform: platform
        });

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.stop_agent',
            params: [agent.uuid],
            authorization: authorization
        }).promise.then(function (status) {
            agent.process_id = status.process_id;
            agent.return_code = status.return_code;
        }).catch(rpc.Error, function (error) {
            handle401(error, "Unable to stop agent " + agent.name + ": " + error.message, agent.name);
        }).finally(function () {
            agent.actionPending = false;

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PLATFORM,
                platform: platform
            });
        });
    },
    removeAgent: function removeAgent(platform, agent) {
        var authorization = authorizationStore.getAuthorization();

        agent.actionPending = true;

        dispatcher.dispatch({
            type: ACTION_TYPES.CLOSE_MODAL
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_PLATFORM,
            platform: platform
        });

        var methodStr = 'platforms.uuid.' + platform.uuid + '.remove_agent';
        var agentId = [agent.uuid];

        new rpc.Exchange({
            method: methodStr,
            params: agentId,
            authorization: authorization
        }).promise.then(function (result) {

            if (result.error) {
                statusIndicatorActionCreators.openStatusIndicator("error", "Unable to remove agent " + agent.name + ": " + result.error, agent.name);
            } else {
                platformActionCreators.loadPlatform(platform);
            }
        }).catch(rpc.Error, function (error) {
            handle401(error, "Unable to remove agent " + agent.name + ": " + error.message, agent.name);
        });
    },
    installAgents: function installAgents(platform, files) {

        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + platform.uuid + '.install',
            params: { files: files },
            authorization: authorization
        }).promise.then(function (results) {
            var errors = [];

            results.forEach(function (result) {
                if (result.error) {
                    errors.push(result.error);
                }
            });

            if (errors.length) {
                statusIndicatorActionCreators.openStatusIndicator("error", "Unable to install agents for platform " + platform.name + ": " + errors.join('\n'), platform.name);
            }

            if (errors.length !== files.length) {
                platformActionCreators.loadPlatform(platform);
            }
        }).catch(rpc.Error, function (error) {
            handle401(error, "Unable to install agents for platform " + platform.name + ": " + error.message, platform.name);
        });
    },
    handleChartsForUser: function handleChartsForUser(callback) {
        var authorization = authorizationStore.getAuthorization();
        var user = authorizationStore.getUsername();

        if (user) {
            callback(authorization, user);
        }
    },
    loadChartTopics: function loadChartTopics() {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'historian.get_topic_list',
            authorization: authorization
        }).promise.then(function (topics) {

            var filteredTopics = [];

            topics.forEach(function (topic, index) {

                if (topic.indexOf("datalogger/platform/status") < 0) // ignore -- they're local platform topics that are in
                    {
                        // the list twice, also at datalogger/platform/<uuid>
                        var item = {};
                        var topicParts = topic.split("/");

                        if (topicParts.length > 2) {
                            var name;
                            var parentPath;
                            var label;

                            if (topic.indexOf("datalogger/platforms") > -1) // if a platform instance
                                {
                                    var platformUuid = topicParts[2];
                                    var topicPlatform = platformsStore.getPlatform(platformUuid);
                                    parentPath = topicPlatform ? topicPlatform.name : "Unknown Platform";
                                    label = topicParts[topicParts.length - 2] + "/" + topicParts[topicParts.length - 1] + " (" + parentPath + ")";
                                    name = topicParts[topicParts.length - 2] + " / " + topicParts[topicParts.length - 1]; // the name is the
                                    // last two path parts
                                } // ex.: times_percent / idle
                            else // else a device point
                                {
                                    parentPath = topicParts[0];

                                    for (var i = 1; i < topicParts.length - 1; i++) {
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
        }).catch(rpc.Error, function (error) {

            var message = error.message;

            if (error.code === -32602) {
                if (error.message === "historian unavailable") {
                    message = "Charts can't be added. The VOLTTRON Central historian is unavailable.";
                }
            } else {
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
    loadCharts: function loadCharts(platform) {

        var doLoadCharts = function (authorization, user) {
            new rpc.Exchange({
                method: 'get_setting_keys',
                authorization: authorization
            }).promise.then(function (valid_keys) {

                if (valid_keys.indexOf(user) > -1) {
                    new rpc.Exchange({
                        method: 'get_setting',
                        params: { key: user },
                        authorization: authorization
                    }).promise.then(function (charts) {

                        var notifyRouter = false;

                        dispatcher.dispatch({
                            type: ACTION_TYPES.LOAD_CHARTS,
                            charts: charts
                        });
                    }).catch(rpc.Error, function (error) {
                        handle401(error);
                    });
                }
            }).catch(rpc.Error, function (error) {
                handle401(error);
            });
        }.bind(platform);

        platformActionCreators.handleChartsForUser(doLoadCharts);
    },
    saveCharts: function saveCharts(chartsToSave) {

        var doSaveCharts = function (authorization, user) {
            var savedCharts = this ? this : platformChartStore.getPinnedCharts();

            new rpc.Exchange({
                method: 'set_setting',
                params: { key: user, value: savedCharts },
                authorization: authorization
            }).promise.then(function () {}).catch(rpc.Error, function (error) {
                handle401(error, "Unable to save charts: " + error.message);
            });
        }.bind(chartsToSave);

        platformActionCreators.handleChartsForUser(doSaveCharts);
    },
    saveChart: function saveChart(newChart) {

        var doSaveChart = function (authorization, user) {
            var newCharts = [this];

            new rpc.Exchange({
                method: 'set_setting',
                params: { key: user, value: newCharts },
                authorization: authorization
            }).promise.then(function () {}).catch(rpc.Error, function (error) {
                handle401(error, "Unable to save chart: " + error.message);
            });
        }.bind(newChart);

        platformActionCreators.handleChartsForUser(doSaveChart);
    },
    deleteChart: function deleteChart(chartToDelete) {

        var doDeleteChart = function (authorization, user) {

            var savedCharts = platformChartStore.getPinnedCharts();

            var newCharts = savedCharts.filter(function (chart) {
                return chart.chartKey !== this;
            });

            new rpc.Exchange({
                method: 'set_setting',
                params: { key: user, value: newCharts },
                authorization: authorization
            }).promise.then(function () {}).catch(rpc.Error, function (error) {
                handle401(error, "Unable to delete chart: " + error.message);
            });
        }.bind(chartToDelete);

        platformActionCreators.handleChartsForUser(doDeleteChart);
    },
    removeSavedPlatformCharts: function removeSavedPlatformCharts(platform) {

        var authorization = authorizationStore.getAuthorization();

        // first get all the keys (i.e., users) that charts are saved under
        new rpc.Exchange({
            method: 'get_setting_keys',
            authorization: authorization
        }).promise.then(function (valid_keys) {

            // then get the charts for each user
            valid_keys.forEach(function (key) {

                new rpc.Exchange({
                    method: 'get_setting',
                    params: { key: key },
                    authorization: authorization
                }).promise.then(function (charts) {

                    // for each saved chart, keep the chart if it has any series that don't belong
                    // to the deregistered platform
                    var filteredCharts = charts.filter(function (chart) {

                        var keeper = true;
                        var seriesToRemove;

                        var filteredSeries = chart.series.filter(function (series) {
                            var seriesToKeep = series.path.indexOf(this.uuid) < 0;

                            // also have to remove any data associated with the removed series
                            if (!seriesToKeep) {
                                var filteredData = chart.data.filter(function (datum) {
                                    return datum.uuid !== this.uuid;
                                }, series);

                                chart.data = filteredData;
                            }

                            return seriesToKeep;
                        }, this);

                        // keep the chart if there are any series that don't belong to the deregistered platform,
                        // but leave out the series that do belong to the deregistered platform
                        if (filteredSeries.length !== 0) {
                            chart.series = filteredSeries;
                        } else {
                            keeper = false;
                        }

                        return keeper;
                    }, platform);

                    // now save the remaining charts. Even if there are none, do the save, because that's what deletes 
                    // the rejects.
                    new rpc.Exchange({
                        method: 'set_setting',
                        params: { key: key, value: filteredCharts },
                        authorization: authorization
                    }).promise.then(function () {}).catch(rpc.Error, function (error) {
                        handle401(error, "Error removing deregistered platform's charts from saved charts (e0): " + error.message);
                    });
                }).catch(rpc.Error, function (error) {
                    handle401(error, "Error removing deregistered platform's charts from saved charts (e1): " + error.message);
                });
            });
        }).catch(rpc.Error, function (error) {
            handle401(error, "Error removing deregistered platform's charts from saved charts (e2): " + error.message);
        });
    }

};

function handle401(error, message, highlight, orientation) {
    if (error.code && error.code === 401 || error.response && error.response.status === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION
        });
    } else if (message) {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformActionCreators;

},{"../action-creators/status-indicator-action-creators":10,"../constants/action-types":48,"../dispatcher":49,"../lib/rpc":52,"../stores/authorization-store":57,"../stores/platform-chart-store":62,"../stores/platforms-panel-items-store":63,"../stores/platforms-store":65}],7:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformsStore = require('../stores/platforms-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var rpc = require('../lib/rpc');

var platformChartActionCreators = {
    pinChart: function pinChart(chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.PIN_CHART,
            chartKey: chartKey
        });
    },
    setType: function setType(chartKey, chartType) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_TYPE,
            chartKey: chartKey,
            chartType: chartType
        });
    },
    changeRefreshRate: function changeRefreshRate(rate, chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_REFRESH,
            rate: rate,
            chartKey: chartKey
        });
    },
    setMin: function setMin(min, chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_MIN,
            min: min,
            chartKey: chartKey
        });
    },
    setMax: function setMax(max, chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_MAX,
            max: max,
            chartKey: chartKey
        });
    },
    refreshChart: function refreshChart(series) {

        var authorization = authorizationStore.getAuthorization();

        series.forEach(function (item) {
            new rpc.Exchange({
                method: 'historian.query',
                params: {
                    topic: item.topic,
                    count: 20,
                    order: 'LAST_TO_FIRST'
                },
                authorization: authorization
            }).promise.then(function (result) {

                if (result.hasOwnProperty("values")) {
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
                } else {
                    console.log("chart " + item.name + " isn't being refreshed");
                }
            }).catch(rpc.Error, function (error) {
                handle401(error);
            });
        });
    },
    addToChart: function addToChart(panelItem, emitChange) {

        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'historian.query',
            params: {
                topic: panelItem.topic,
                count: 20,
                order: 'LAST_TO_FIRST'
            },
            authorization: authorization
        }).promise.then(function (result) {

            if (result.hasOwnProperty("values")) {
                panelItem.data = result.values;

                panelItem.data.forEach(function (datum) {
                    datum.name = panelItem.name;
                    datum.parent = panelItem.parentPath;
                    datum.uuid = panelItem.uuid;
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.SHOW_CHARTS,
                    emitChange: emitChange === null || typeof emitChange === "undefined" ? true : emitChange
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });

                platformsPanelActionCreators.checkItem(panelItem.path, true);

                var savedCharts = platformChartStore.getPinnedCharts();
                var inSavedChart = savedCharts.find(function (chart) {
                    return chart.chartKey === panelItem.name;
                });

                if (inSavedChart) {
                    platformActionCreators.saveCharts(savedCharts);
                }
            } else {
                var message = "Unable to load chart: An unknown problem occurred.";
                var orientation = "center";
                var error = {};

                if (panelItem.path && panelItem.path.length > 1) {
                    var platformUuid = panelItem.path[1];
                    var forwarderRunning = platformsStore.getForwarderRunning(platformUuid);

                    if (!forwarderRunning) {
                        message = "Unable to load chart: The forwarder agent for the device's platform isn't available.";
                        orientation = "left";
                    }
                }

                platformsPanelActionCreators.checkItem(panelItem.path, false);
                handle401(error, message, null, orientation);
            }
        }).catch(rpc.Error, function (error) {

            var message = "Unable to load chart: " + error.message;
            var orientation;

            if (error.code === -32602) {
                if (error.message === "historian unavailable") {
                    message = "Unable to load chart: The VOLTTRON Central platform's historian is unavailable.";
                    orientation = "left";
                }
            } else {
                var historianRunning = platformsStore.getVcHistorianRunning();

                if (!historianRunning) {
                    message = "Unable to load chart: The VOLTTRON Central platform's historian is unavailable.";
                    orientation = "left";
                }
            }

            platformsPanelActionCreators.checkItem(panelItem.path, false);
            handle401(error, message, null, orientation);
        });
    },
    removeFromChart: function removeFromChart(panelItem) {

        var savedCharts = platformChartStore.getPinnedCharts();
        var inSavedChart = savedCharts.find(function (chart) {
            return chart.chartKey === panelItem.name;
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_CHART,
            panelItem: panelItem
        });

        platformsPanelActionCreators.checkItem(panelItem.path, false);

        if (inSavedChart) {
            platformActionCreators.saveCharts();
        }
    },
    removeChart: function removeChart(chartName) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_CHART,
            name: chartName
        });
    }
};

function handle401(error, message, highlight, orientation) {
    if (error.code && error.code === 401 || error.response && error.response.status === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION
        });
    } else if (message) {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformChartActionCreators;

},{"../action-creators/platform-action-creators":6,"../action-creators/platforms-panel-action-creators":9,"../action-creators/status-indicator-action-creators":10,"../constants/action-types":48,"../dispatcher":49,"../lib/rpc":52,"../stores/authorization-store":57,"../stores/platform-chart-store":62,"../stores/platforms-panel-items-store":63,"../stores/platforms-store":65}],8:[function(require,module,exports){
'use strict';

var _typeof = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? function (obj) { return typeof obj; } : function (obj) { return obj && typeof Symbol === "function" && obj.constructor === Symbol ? "symbol" : typeof obj; };

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var platformActionCreators = require('../action-creators/platform-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var rpc = require('../lib/rpc');

var initializing = false;

var platformManagerActionCreators = {
    initialize: function initialize() {
        if (!authorizationStore.getAuthorization()) {
            return;
        }

        var reload = false;
        platformManagerActionCreators.loadPlatforms(reload);
    },
    requestAuthorization: function requestAuthorization(username, password) {
        new rpc.Exchange({
            method: 'get_authorization',
            params: {
                username: username,
                password: password
            }
        }, ['password']).promise.then(function (result) {

            dispatcher.dispatch({
                type: ACTION_TYPES.WILL_INITIALIZE_PLATFORMS
            });

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_AUTHORIZATION,
                authorization: result,
                name: username
            });
        }).then(platformManagerActionCreators.initialize).catch(rpc.Error, function (error) {

            var message = error.message;

            if (error.response.status === 401) {
                message = "Invalid username/password specified.";
            }

            statusIndicatorActionCreators.openStatusIndicator("error", message, null, "center"); //This is needed because the 401 status  
            handle401(error, error.message); // will keep the statusindicator from being shown. This is 
        }); // the one time we show bad status for not authorized. Other 
    }, // times, we just log them out.
    clearAuthorization: function clearAuthorization() {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION
        });
    },
    loadPlatforms: function loadPlatforms(reload) {
        var authorization = authorizationStore.getAuthorization();

        return new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization
        }).promise.then(function (platforms) {

            platforms = platforms.map(function (platform, index) {

                if (platform.name === null || platform.name === "" || _typeof(platform.name) === undefined) {
                    platform.name = "Unnamed Platform " + (index + 1);
                }

                return platform;
            });

            var managerPlatforms = JSON.parse(JSON.stringify(platforms));
            var panelPlatforms = JSON.parse(JSON.stringify(platforms));

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PLATFORMS,
                platforms: managerPlatforms
            });

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
                platforms: panelPlatforms,
                reload: reload
            });

            managerPlatforms.forEach(function (platform, i) {
                platformActionCreators.loadAgents(platform);

                if (!reload) {
                    platformActionCreators.loadCharts(platform);
                }
            });
        }).catch(rpc.Error, function (error) {
            handle401(error, error.message);
        });
    },
    registerPlatform: function registerPlatform(name, address, method) {
        var authorization = authorizationStore.getAuthorization();

        var rpcMethod;
        var params = {};

        switch (method) {
            case "discovery":
                rpcMethod = 'register_instance';
                params = {
                    display_name: name,
                    discovery_address: address
                };
                break;
            case "advanced":
                rpcMethod = 'register_platform';
                params = {
                    identity: 'platform.agent',
                    agentId: name,
                    address: address
                };
                break;
        }

        new rpc.Exchange({
            method: rpcMethod,
            authorization: authorization,
            params: params
        }).promise.then(function (result) {
            dispatcher.dispatch({
                type: ACTION_TYPES.CLOSE_MODAL
            });

            statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + name + " was registered.", name, "center");

            var reload = true;
            platformManagerActionCreators.loadPlatforms(reload);
        }).catch(rpc.Error, function (error) {

            dispatcher.dispatch({
                type: ACTION_TYPES.CLOSE_MODAL
            });

            var message = "Platform " + name + " was not registered: " + error.message;
            var orientation;

            switch (error.code) {
                case -32600:
                    message = "Platform " + name + " was not registered: Invalid address.";
                    orientation = "center";
                    break;
                case -32000:
                    message = "Platform " + name + " was not registered: An unknown error occurred.";
                    orientation = "center";
                    break;
            }

            handle401(error, message, name, orientation);
        });
    },
    deregisterPlatform: function deregisterPlatform(platform) {
        var authorization = authorizationStore.getAuthorization();

        var platformName = platform.name;

        new rpc.Exchange({
            method: 'unregister_platform',
            authorization: authorization,
            params: {
                platform_uuid: platform.uuid
            }
        }).promise.then(function (result) {
            dispatcher.dispatch({
                type: ACTION_TYPES.CLOSE_MODAL
            });

            platformActionCreators.removeSavedPlatformCharts(platform);

            statusIndicatorActionCreators.openStatusIndicator("success", "Platform " + platformName + " was deregistered.", platformName, "center");
            dispatcher.dispatch({
                type: ACTION_TYPES.REMOVE_PLATFORM_CHARTS,
                platform: platform
            });

            var reload = true;
            platformManagerActionCreators.loadPlatforms(reload);
        }).catch(rpc.Error, function (error) {
            var message = "Platform " + platformName + " was not deregistered: " + error.message;

            handle401(error, message, platformName);
        });
    }
};

function handle401(error, message, highlight, orientation) {
    if (error.code && error.code === 401 || error.response && error.response.status === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error
        });

        platformManagerActionCreators.clearAuthorization();
    } else if (message) {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformManagerActionCreators;

},{"../action-creators/platform-action-creators":6,"../action-creators/status-indicator-action-creators":10,"../constants/action-types":48,"../dispatcher":49,"../lib/rpc":52,"../stores/authorization-store":57}],9:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformsPanelActionCreators = {
    togglePanel: function togglePanel() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL
        });
    },

    loadChildren: function loadChildren(type, parent) {
        if (type === "platform") {
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
                authorization: authorization
            }).promise.then(function (result) {

                var devicesList = [];

                for (var key in result) {
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
            }).catch(rpc.Error, function (error) {
                endLoadingData(platform);
                handle401(error, "Unable to load devices for platform " + platform.name + " in side panel: " + error.message, platform.name);
            });
        }

        function loadPanelAgents(platform) {
            var authorization = authorizationStore.getAuthorization();

            new rpc.Exchange({
                method: 'platforms.uuid.' + platform.uuid + '.list_agents',
                authorization: authorization
            }).promise.then(function (agentsList) {

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AGENT_STATUSES,
                    platform: platform,
                    agents: agentsList
                });

                loadPerformanceStats(platform);
            }).catch(rpc.Error, function (error) {
                endLoadingData(platform);
                handle401(error, "Unable to load agents for platform " + platform.name + " in side panel: " + error.message, platform.name);
            });
        }

        function loadPerformanceStats(parent) {

            if (parent.type === "platform") {
                var authorization = authorizationStore.getAuthorization();

                //TODO: use service to get performance for a single platform

                new rpc.Exchange({
                    method: 'list_performance',
                    authorization: authorization
                }).promise.then(function (result) {

                    var platformPerformance = result.find(function (item) {
                        return item["platform.uuid"] === parent.uuid;
                    });

                    var pointsList = [];

                    if (platformPerformance) {
                        var points = platformPerformance.performance.points;

                        points.forEach(function (point) {

                            var pointName = point === "percent" ? "cpu / percent" : point.replace("/", " / ");

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
                }).catch(rpc.Error, function (error) {

                    var message = error.message;

                    if (error.code === -32602) {
                        if (error.message === "historian unavailable") {
                            message = "Data could not be fetched for platform " + parent.name + ". The historian agent is unavailable.";
                        }
                    }

                    endLoadingData(parent);
                    handle401(error, message, parent.name, "center");
                });
            }
        }

        function endLoadingData(panelItem) {
            dispatcher.dispatch({
                type: ACTION_TYPES.END_LOADING_DATA,
                panelItem: panelItem
            });
        }
    },

    loadFilteredItems: function loadFilteredItems(filterTerm, filterStatus) {
        dispatcher.dispatch({
            type: ACTION_TYPES.FILTER_ITEMS,
            filterTerm: filterTerm,
            filterStatus: filterStatus
        });
    },

    expandAll: function expandAll(itemPath) {

        dispatcher.dispatch({
            type: ACTION_TYPES.EXPAND_ALL,
            itemPath: itemPath
        });
    },

    toggleItem: function toggleItem(itemPath) {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_ITEM,
            itemPath: itemPath
        });
    },

    checkItem: function checkItem(itemPath, checked) {

        dispatcher.dispatch({
            type: ACTION_TYPES.CHECK_ITEM,
            itemPath: itemPath,
            checked: checked
        });
    }
};

function handle401(error, message, highlight, orientation) {
    if (error.code && error.code === 401 || error.response && error.response.status === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION
        });
    } else if (message) {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformsPanelActionCreators;

},{"../action-creators/status-indicator-action-creators":10,"../constants/action-types":48,"../dispatcher":49,"../lib/rpc":52,"../stores/authorization-store":57,"../stores/platforms-panel-items-store":63}],10:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var actionStatusCreators = {
	openStatusIndicator: function openStatusIndicator(status, message, highlight, align) {

		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_STATUS,
			status: status,
			message: message,
			highlight: highlight,
			align: align
		});
	},
	closeStatusIndicator: function closeStatusIndicator() {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_STATUS
		});
	}
};

module.exports = actionStatusCreators;

},{"../constants/action-types":48,"../dispatcher":49}],11:[function(require,module,exports){
'use strict';

var React = require('react');

var platformActionCreators = require('../action-creators/platform-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');

var RemoveAgentForm = require('./remove-agent-form');

var AgentRow = React.createClass({
    displayName: 'AgentRow',

    _onStop: function _onStop() {
        platformActionCreators.stopAgent(this.props.platform, this.props.agent);
    },
    _onStart: function _onStart() {
        platformActionCreators.startAgent(this.props.platform, this.props.agent);
    },
    _onRemove: function _onRemove() {
        modalActionCreators.openModal(React.createElement(RemoveAgentForm, { platform: this.props.platform, agent: this.props.agent }));
    },
    render: function render() {
        var agent = this.props.agent,
            status,
            action,
            remove,
            notAllowed;

        if (agent.actionPending === undefined) {
            status = 'Retrieving status...';
        } else if (agent.actionPending) {
            if (agent.process_id === null || agent.return_code !== null) {
                status = 'Starting...';
                action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Start', disabled: true });
            } else {
                status = 'Stopping...';
                action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Stop', disabled: true });
            }
        } else {

            if (agent.process_id === null) {
                status = 'Never started';

                if (agent.permissions.can_start) {
                    action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Start', onClick: this._onStart });
                } else {
                    action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Start', onClick: this._onStart, disabled: true });
                }
            } else if (agent.return_code === null) {
                status = 'Running (PID ' + agent.process_id + ')';

                if (agent.permissions.can_stop) {
                    action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Stop', onClick: this._onStop });
                } else {
                    action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Stop', onClick: this._onStop, disabled: true });
                }
            } else {
                status = 'Stopped (returned ' + agent.return_code + ')';

                if (agent.permissions.can_restart) {
                    action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Start', onClick: this._onStart });
                } else {
                    action = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Start', onClick: this._onStart, disabled: true });
                }
            }
        }

        if (agent.permissions.can_remove) {
            remove = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Remove', onClick: this._onRemove });
        } else {
            remove = React.createElement('input', { className: 'button button--agent-action', type: 'button', value: 'Remove', onClick: this._onRemove, disabled: true });
        }

        return React.createElement(
            'tr',
            null,
            React.createElement(
                'td',
                null,
                agent.name
            ),
            React.createElement(
                'td',
                null,
                agent.identity
            ),
            React.createElement(
                'td',
                null,
                agent.uuid
            ),
            React.createElement(
                'td',
                null,
                status
            ),
            React.createElement(
                'td',
                null,
                action,
                ' ',
                remove
            )
        );
    }
});

module.exports = AgentRow;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-action-creators":6,"./remove-agent-form":46,"react":undefined}],12:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
	value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var BaseComponent = function (_React$Component) {
	_inherits(BaseComponent, _React$Component);

	function BaseComponent() {
		_classCallCheck(this, BaseComponent);

		return _possibleConstructorReturn(this, Object.getPrototypeOf(BaseComponent).apply(this, arguments));
	}

	_createClass(BaseComponent, [{
		key: '_bind',
		value: function _bind() {
			var _this2 = this;

			for (var _len = arguments.length, methods = Array(_len), _key = 0; _key < _len; _key++) {
				methods[_key] = arguments[_key];
			}

			methods.forEach(function (method) {
				return _this2[method] = _this2[method].bind(_this2);
			});
		}
	}]);

	return BaseComponent;
}(_react2.default.Component);

exports.default = BaseComponent;

},{"react":undefined}],13:[function(require,module,exports){
'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
var OutsideClick = require('react-click-outside');

var ComboBox = React.createClass({
    displayName: 'ComboBox',

    getInitialState: function getInitialState() {

        var preppedItems = prepItems(this.props.itemskey, this.props.itemsvalue, this.props.itemslabel, this.props.items);

        var state = {
            selectedKey: "",
            selectedLabel: "",
            selectedValue: "",
            inputValue: "",
            hideMenu: true,
            preppedItems: preppedItems,
            itemsList: preppedItems,
            focusedIndex: -1
        };

        this.forceHide = false;

        return state;
    },
    componentDidUpdate: function componentDidUpdate() {
        if (this.forceHide) {
            ReactDOM.findDOMNode(this.refs.comboInput).blur();
            this.forceHide = false;
        } else {
            if (this.state.focusedIndex > -1) {
                var modal = document.querySelector(".modal__dialog");

                var comboItems = document.querySelectorAll(".combobox-item");

                if (comboItems.length > this.state.focusedIndex) {
                    var targetItem = comboItems[this.state.focusedIndex];

                    if (targetItem) {
                        var menu = targetItem.parentNode;

                        var menuRect = menu.getBoundingClientRect();
                        var modalRect = modal.getBoundingClientRect();
                        var targetRect = targetItem.getBoundingClientRect();

                        if (targetRect.bottom > modalRect.bottom || targetRect.top < modalRect.top) {
                            var newTop = targetRect.top - menuRect.top;

                            modal.scrollTop = newTop;
                        }
                    }
                }
            }
        }
    },
    handleClickOutside: function handleClickOutside() {
        if (!this.state.hideMenu) {
            var validValue = this._validateValue(this.state.inputValue);
            this.props.onselect(validValue);
            this.setState({ hideMenu: true });
            this.setState({ focusedIndex: -1 });
        }
    },
    _validateValue: function _validateValue(inputValue) {

        var validInput = this.props.items.find(function (item) {
            return item.label === inputValue;
        });

        var validKey = validInput ? validInput.key : "";
        var validValue = validInput ? validInput.value : "";
        var validLabel = validInput ? validInput.label : "";

        this.setState({ selectedKey: validKey });
        this.setState({ selectedValue: validValue });
        this.setState({ selectedLabel: validLabel });

        return validValue;
    },
    _onClick: function _onClick(e) {
        this.setState({ selectedKey: e.target.dataset.key });
        this.setState({ selectedLabel: e.target.dataset.label });
        this.setState({ selectedValue: e.target.dataset.value });
        this.setState({ inputValue: e.target.dataset.label });
        this.setState({ hideMenu: true });

        this.props.onselect(e.target.dataset.value);

        this.setState({ focusedIndex: -1 });
    },
    _onFocus: function _onFocus() {
        this.setState({ hideMenu: false });
    },
    _onKeyup: function _onKeyup(e) {
        switch (e.keyCode) {
            case 13:
                //Enter key
                this.forceHide = true;
                this.setState({ hideMenu: true });

                var inputValue = this.state.inputValue;

                if (this.state.focusedIndex > -1) {
                    var selectedItem = this.state.itemsList[this.state.focusedIndex];
                    inputValue = selectedItem.label;

                    this.setState({ inputValue: inputValue });
                    this.setState({ selectedKey: selectedItem.key });
                    this.setState({ selectedLabel: selectedItem.label });
                    this.setState({ selectedValue: selectedItem.value });
                }

                var validValue = this._validateValue(inputValue);
                this.props.onselect(validValue);

                this.setState({ focusedIndex: -1 });
                break;
        }
    },
    _onKeydown: function _onKeydown(e) {
        switch (e.keyCode) {
            case 9: //Tab key
            case 40:
                //Arrow down key

                e.preventDefault();

                var newIndex = 0;

                if (this.state.focusedIndex < this.state.itemsList.length - 1) {
                    newIndex = this.state.focusedIndex + 1;
                }

                this.setState({ focusedIndex: newIndex });
                break;
            case 38:
                //Arrow up key

                e.preventDefault();

                var newIndex = this.state.itemsList.length - 1;

                if (this.state.focusedIndex > 0) {
                    newIndex = this.state.focusedIndex - 1;
                }

                this.setState({ focusedIndex: newIndex });
                break;
        }
    },
    _onChange: function _onChange(e) {

        var inputValue = e.target.value;

        var itemsList = filterItems(inputValue, this.state.preppedItems);

        this.setState({ itemsList: itemsList });

        this.setState({ inputValue: inputValue });
    },

    render: function render() {

        var menuStyle = {
            display: this.state.hideMenu ? 'none' : 'block'
        };

        var inputStyle = {
            width: "390px"
        };

        var items = this.state.itemsList.map(function (item, index) {

            var highlightStyle = {};

            if (this.state.focusedIndex > -1 && this.state.focusedIndex === index) {
                highlightStyle.backgroundColor = "#B2C9D1";
            }

            return React.createElement(
                'div',
                { className: 'combobox-item',
                    style: highlightStyle,
                    key: item.key },
                React.createElement(
                    'div',
                    {
                        onClick: this._onClick,
                        'data-label': item.label,
                        'data-value': item.value,
                        'data-key': item.key },
                    item.label
                )
            );
        }, this);

        return React.createElement(
            'div',
            { className: 'combobox-control' },
            React.createElement('input', {
                style: inputStyle,
                type: 'text',
                onFocus: this._onFocus,
                onChange: this._onChange,
                onKeyUp: this._onKeyup,
                onKeyDown: this._onKeydown,
                ref: 'comboInput',
                placeholder: 'type here to see topics',
                value: this.state.inputValue }),
            React.createElement(
                'div',
                { className: 'combobox-menu', style: menuStyle },
                items
            )
        );
    }
});

function prepItems(itemsKey, itemsValue, itemsLabel, itemsList) {
    var props = {
        itemsKey: itemsKey,
        itemsValue: itemsValue,
        itemsLabel: itemsLabel
    };

    var list = itemsList.map(function (item, index) {

        var preppedItem = {
            key: this.itemsKey ? item[this.itemsKey] : index,
            value: this.itemsValue ? item[this.itemsValue] : item,
            label: this.itemsLabel ? item[this.itemsLabel] : item
        };

        return preppedItem;
    }, props);

    return JSON.parse(JSON.stringify(list));
}

function filterItems(filterTerm, itemsList) {
    var listCopy = JSON.parse(JSON.stringify(itemsList));

    var filteredItems = listCopy;

    if (filterTerm) {
        filteredItems = [];

        listCopy.forEach(function (item) {
            if (item.label.toUpperCase().indexOf(filterTerm.toUpperCase()) > -1) {
                filteredItems.push(item);
            }
        });
    }

    return filteredItems;
}

module.exports = OutsideClick(ComboBox);

},{"react":undefined,"react-click-outside":undefined,"react-dom":undefined}],14:[function(require,module,exports){
'use strict';

var React = require('react');

var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');

var Composer = React.createClass({
    displayName: 'Composer',

    getInitialState: getStateFromStores,
    componentDidMount: function componentDidMount() {
        consoleStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        consoleStore.removeChangeListener(this._onChange);
    },
    _onChange: function _onChange() {
        this.replaceState(getStateFromStores());
    },
    _onSendClick: function _onSendClick() {
        consoleActionCreators.makeRequest(JSON.parse(this.state.composerValue));
    },
    _onTextareaChange: function _onTextareaChange(e) {
        consoleActionCreators.updateComposerValue(e.target.value);
    },
    render: function render() {
        return React.createElement(
            'div',
            { className: 'composer' },
            React.createElement('textarea', {
                key: this.state.composerId,
                onChange: this._onTextareaChange,
                defaultValue: this.state.composerValue
            }),
            React.createElement('input', {
                className: 'button',
                ref: 'send',
                type: 'button',
                value: 'Send',
                disabled: !this.state.valid,
                onClick: this._onSendClick
            })
        );
    }
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
        valid: valid
    };
}

module.exports = Composer;

},{"../action-creators/console-action-creators":2,"../stores/console-store":58,"react":undefined}],15:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

var ConfigDeviceForm = function (_BaseComponent) {
    _inherits(ConfigDeviceForm, _BaseComponent);

    function ConfigDeviceForm(props) {
        _classCallCheck(this, ConfigDeviceForm);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(ConfigDeviceForm).call(this, props));

        _this._bind("_updateSetting", "_onSubmit");

        _this.state = getStateFromStores(_this.props.device);
        return _this;
    }

    _createClass(ConfigDeviceForm, [{
        key: '_updateSetting',
        value: function _updateSetting(evt) {
            var newVal = evt.target.value;
            var key = evt.currentTarget.dataset.setting;

            var tmpState = JSON.parse(JSON.stringify(this.state));

            var newSettings = tmpState.settings.map(function (item) {
                if (item.key === key) {
                    item.value = newVal;
                }

                return item;
            });

            this.setState({ settings: newSettings });
        }
    }, {
        key: '_onCancelClick',
        value: function _onCancelClick(e) {
            modalActionCreators.closeModal();
        }
    }, {
        key: '_onSubmit',
        value: function _onSubmit(e) {
            e.preventDefault();
            devicesActionCreators.saveConfig(this.props.device, this.state.settings);
            modalActionCreators.closeModal();
        }
    }, {
        key: 'render',
        value: function render() {

            var tableStyle = {
                backgroundColor: "#E7E7E7"
            };

            var uneditableAttributes = _react2.default.createElement(
                'table',
                { style: tableStyle },
                _react2.default.createElement(
                    'tbody',
                    null,
                    _react2.default.createElement(
                        'tr',
                        null,
                        _react2.default.createElement(
                            'td',
                            null,
                            'Proxy Address'
                        ),
                        _react2.default.createElement(
                            'td',
                            { className: 'plain' },
                            '10.0.2.15'
                        )
                    ),
                    _react2.default.createElement(
                        'tr',
                        null,
                        _react2.default.createElement(
                            'td',
                            null,
                            'Network Interface'
                        ),
                        _react2.default.createElement(
                            'td',
                            { className: 'plain' },
                            'UDP/IP'
                        )
                    ),
                    _react2.default.createElement(
                        'tr',
                        null,
                        _react2.default.createElement(
                            'td',
                            null,
                            'Campus'
                        ),
                        _react2.default.createElement(
                            'td',
                            { className: 'plain' },
                            'PNNL'
                        )
                    )
                )
            );

            var firstStyle = {
                width: "30%",
                textAlign: "right"
            };

            var secondStyle = {
                width: "50%"
            };

            var settingsRows = this.state.settings.map(function (setting) {

                var stateSetting = this.state.settings.find(function (s) {
                    return s.key === setting.key;
                });

                return _react2.default.createElement(
                    'tr',
                    { key: setting.key },
                    _react2.default.createElement(
                        'td',
                        { style: firstStyle },
                        setting.label
                    ),
                    _react2.default.createElement(
                        'td',
                        { style: secondStyle,
                            className: 'plain' },
                        _react2.default.createElement('input', {
                            className: 'form__control form__control--block',
                            type: 'text',
                            'data-setting': setting.key,
                            onChange: this._updateSetting,
                            value: stateSetting.value
                        })
                    )
                );
            }, this);

            var editableAttributes = _react2.default.createElement(
                'table',
                null,
                _react2.default.createElement(
                    'tbody',
                    null,
                    settingsRows
                )
            );

            var configDeviceBox = {
                padding: "0px 50px",
                marginTop: "20px",
                marginBottom: "20px"
            };

            return _react2.default.createElement(
                'form',
                { className: 'config-device-form', onSubmit: this._onSubmit },
                _react2.default.createElement(
                    'div',
                    { className: 'centerContent' },
                    _react2.default.createElement(
                        'h3',
                        null,
                        'Device Configuration'
                    )
                ),
                _react2.default.createElement(
                    'div',
                    { className: 'configDeviceContainer' },
                    _react2.default.createElement(
                        'div',
                        { className: 'uneditableAttributes' },
                        uneditableAttributes
                    ),
                    _react2.default.createElement(
                        'div',
                        { style: configDeviceBox },
                        editableAttributes
                    )
                ),
                _react2.default.createElement(
                    'div',
                    { className: 'form__actions' },
                    _react2.default.createElement(
                        'button',
                        {
                            className: 'button button--secondary',
                            type: 'button',
                            onClick: this._onCancelClick
                        },
                        'Cancel'
                    ),
                    _react2.default.createElement(
                        'button',
                        { className: 'button' },
                        'Save'
                    )
                )
            );
        }
    }]);

    return ConfigDeviceForm;
}(_baseComponent2.default);

;

var getStateFromStores = function getStateFromStores(device) {

    return {
        settings: [{ key: "unit", value: "", label: "Unit" }, { key: "building", value: "", label: "Building" }, { key: "path", value: "", label: "Path" }, { key: "interval", value: "", label: "Interval" }, { key: "timezone", value: "", label: "Timezone" }, { key: "heartbeat_point", value: "", label: "Heartbeat Point" }, { key: "minimum_priority", value: "", label: "Minimum Priority" }, { key: "max_objs_per_read", value: "", label: "Maximum Objects per Read" }]
    };
};

exports.default = ConfigDeviceForm;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"./base-component":12,"react":undefined}],16:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

var _devicesFound = require('./devices-found');

var _devicesFound2 = _interopRequireDefault(_devicesFound);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var platformsStore = require('../stores/platforms-store');
var devicesStore = require('../stores/devices-store');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

var scanDuration = 10000; // 10 seconds

var ConfigureDevices = function (_BaseComponent) {
    _inherits(ConfigureDevices, _BaseComponent);

    function ConfigureDevices(props) {
        _classCallCheck(this, ConfigureDevices);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(ConfigureDevices).call(this, props));

        _this._bind('_onPlatformStoresChange', '_onDevicesStoresChange', '_onDeviceMethodChange', '_onProxySelect', '_onDeviceStart', '_onDeviceEnd', '_onAddress', '_onStartScan', '_showCancel', '_resumeScan', '_cancelScan', '_onDevicesLoaded');

        _this.state = getInitialState();
        return _this;
    }

    _createClass(ConfigureDevices, [{
        key: 'componentDidMount',
        value: function componentDidMount() {
            platformsStore.addChangeListener(this._onPlatformStoresChange);
            devicesStore.addChangeListener(this._onDevicesStoresChange);
        }
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {
            platformsStore.removeChangeListener(this._onPlatformStoresChange);
            devicesStore.removeChangeListener(this._onDevicesStoresChange);

            if (this._scanTimeout) {
                clearTimeout(this._scanTimeout);
            }
        }
    }, {
        key: '_onPlatformStoresChange',
        value: function _onPlatformStoresChange() {

            if (this.state.platform) {
                var bacnetProxies = platformsStore.getRunningBacnetProxies(this.state.platform.uuid);

                this.setState({ bacnetProxies: bacnetProxies });

                if (bacnetProxies.length < 1 && this.state.deviceMethod === "scanForDevices") {
                    this.setState({ deviceMethod: "addDevicesManually" });
                }
            }
        }
    }, {
        key: '_onDevicesStoresChange',
        value: function _onDevicesStoresChange() {

            if (devicesStore.getNewScan()) {
                this.setState(getInitialState());

                if (this._scanTimeout) {
                    clearTimeout(this._scanTimeout);
                }
            } else {
                this.setState({ devices: devicesStore.getDevices(this.state.platform, this.state.selectedProxyUuid) });
            }
        }
    }, {
        key: '_onDeviceMethodChange',
        value: function _onDeviceMethodChange(evt) {

            var deviceMethod = evt.target.value;

            if (this.state.bacnetProxies.length) {
                this.setState({ deviceMethod: deviceMethod });
            } else {
                statusIndicatorActionCreators.openStatusIndicator("error", "Can't scan for devices: A BACNet proxy agent for the platform must be installed and running.", null, "left");
            }
        }
    }, {
        key: '_onProxySelect',
        value: function _onProxySelect(evt) {
            var selectedProxyUuid = evt.target.value;
            this.setState({ selectedProxyUuid: selectedProxyUuid });
        }
    }, {
        key: '_onDeviceStart',
        value: function _onDeviceStart(evt) {

            this.setState({ deviceStart: evt.target.value });

            if (!this.state.startedInputtingDeviceEnd) {
                this.setState({ deviceEnd: evt.target.value });
            }
        }
    }, {
        key: '_onDeviceEnd',
        value: function _onDeviceEnd(evt) {

            if (!this.state.startedInputtingDeviceEnd) {
                this.setState({ startedInputtingDeviceEnd: true });
            }

            this.setState({ deviceEnd: evt.target.value });
        }
    }, {
        key: '_onAddress',
        value: function _onAddress(evt) {
            this.setState({ address: evt.target.value });
        }
    }, {
        key: '_onStartScan',
        value: function _onStartScan(evt) {
            devicesActionCreators.scanForDevices(this.state.platform.uuid, this.state.selectedProxyUuid, this.state.deviceStart, this.state.deviceEnd, this.state.address);

            this.setState({ scanning: true });
            this.setState({ scanStarted: true });
            this.setState({ canceled: false });

            if (this._scanTimeout) {
                clearTimeout(this._scanTimeout);
            }

            this._scanTimeout = setTimeout(this._cancelScan, scanDuration);
        }
    }, {
        key: '_onDevicesLoaded',
        value: function _onDevicesLoaded(devicesLoaded) {
            this.setState({ devicesLoaded: devicesLoaded });
        }
    }, {
        key: '_showCancel',
        value: function _showCancel() {

            if (this.state.scanning) {
                this.setState({ cancelButton: true });
            }
        }
    }, {
        key: '_resumeScan',
        value: function _resumeScan() {

            if (this.state.scanning) {
                this.setState({ cancelButton: false });
            }
        }
    }, {
        key: '_cancelScan',
        value: function _cancelScan() {
            this.setState({ scanning: false });
            this.setState({ canceled: true });
        }
    }, {
        key: 'render',
        value: function render() {

            var deviceContent, defaultMessage;

            if (this.state.platform) {

                var platform = this.state.platform;

                var methodSelect = _react2.default.createElement(
                    'select',
                    {
                        onChange: this._onDeviceMethodChange,
                        value: this.state.deviceMethod,
                        autoFocus: true,
                        required: true
                    },
                    _react2.default.createElement(
                        'option',
                        { value: 'scanForDevices' },
                        'Scan for Devices'
                    ),
                    _react2.default.createElement(
                        'option',
                        { value: 'addDevicesManually' },
                        'Add Manually'
                    )
                );

                var proxySelect;

                var wideStyle = {
                    width: "100%"
                };

                var fifthCell = {
                    width: "20px"
                };

                if (this.state.deviceMethod === "scanForDevices") {
                    var proxies = this.state.bacnetProxies.map(function (proxy) {
                        return _react2.default.createElement(
                            'option',
                            { key: proxy.uuid, value: proxy.uuid },
                            proxy.name
                        );
                    });

                    proxySelect = _react2.default.createElement(
                        'tr',
                        null,
                        _react2.default.createElement(
                            'td',
                            { className: 'plain' },
                            _react2.default.createElement(
                                'b',
                                null,
                                'BACNet Proxy Agent: '
                            )
                        ),
                        _react2.default.createElement(
                            'td',
                            { className: 'plain',
                                colSpan: 4 },
                            _react2.default.createElement(
                                'select',
                                {
                                    style: wideStyle,
                                    onChange: this._onProxySelect,
                                    value: this.state.selectedProxyUuid,
                                    autoFocus: true,
                                    required: true
                                },
                                proxies
                            )
                        ),
                        _react2.default.createElement('td', { className: 'plain', style: fifthCell })
                    );
                }

                var buttonStyle = {
                    height: "24px"
                };

                var platformNameLength = platform.name.length * 6;

                var platformNameStyle = {
                    width: "25%",
                    minWidth: platformNameLength
                };

                var deviceRangeStyle = {
                    width: "70px"
                };

                var tdStyle = {
                    minWidth: "120px"
                };

                var scanOptions = _react2.default.createElement(
                    'div',
                    { className: 'detectDevicesContainer' },
                    _react2.default.createElement(
                        'div',
                        { className: 'detectDevicesBox' },
                        _react2.default.createElement(
                            'table',
                            null,
                            _react2.default.createElement(
                                'tbody',
                                null,
                                proxySelect,
                                _react2.default.createElement(
                                    'tr',
                                    null,
                                    _react2.default.createElement(
                                        'td',
                                        { className: 'plain', style: tdStyle },
                                        _react2.default.createElement(
                                            'b',
                                            null,
                                            'Device ID Range'
                                        )
                                    ),
                                    _react2.default.createElement(
                                        'td',
                                        { className: 'plain' },
                                        'Min:'
                                    ),
                                    _react2.default.createElement(
                                        'td',
                                        { className: 'plain' },
                                        _react2.default.createElement('input', {
                                            type: 'number',
                                            style: deviceRangeStyle,
                                            onChange: this._onDeviceStart,
                                            value: this.state.deviceStart })
                                    ),
                                    _react2.default.createElement(
                                        'td',
                                        { className: 'plain' },
                                        'Max:'
                                    ),
                                    _react2.default.createElement(
                                        'td',
                                        { className: 'plain' },
                                        _react2.default.createElement('input', {
                                            type: 'number',
                                            style: deviceRangeStyle,
                                            onChange: this._onDeviceEnd,
                                            value: this.state.deviceEnd })
                                    ),
                                    _react2.default.createElement('td', { className: 'plain' })
                                ),
                                _react2.default.createElement(
                                    'tr',
                                    null,
                                    _react2.default.createElement(
                                        'td',
                                        null,
                                        _react2.default.createElement(
                                            'b',
                                            null,
                                            'Address'
                                        )
                                    ),
                                    _react2.default.createElement(
                                        'td',
                                        { className: 'plain',
                                            colSpan: 4 },
                                        _react2.default.createElement('input', {
                                            style: wideStyle,
                                            type: 'text',
                                            onChange: this._onAddress,
                                            value: this.state.address })
                                    ),
                                    _react2.default.createElement('td', { className: 'plain', style: fifthCell })
                                )
                            )
                        )
                    )
                );

                var scanOptionsStyle = {
                    float: "left",
                    marginRight: "10px"
                };

                var platformNameStyle = {
                    float: "left",
                    width: "100%"
                };

                var devicesContainer;
                var scanButton;

                if (this.state.scanning) {
                    var spinnerContent;

                    if (this.state.cancelButton) {
                        spinnerContent = _react2.default.createElement(
                            'span',
                            { className: 'cancelScanning' },
                            _react2.default.createElement('i', { className: 'fa fa-remove' })
                        );
                    } else {
                        spinnerContent = _react2.default.createElement('i', { className: 'fa fa-cog fa-spin fa-2x fa-fw margin-bottom' });
                    }

                    scanButton = _react2.default.createElement(
                        'div',
                        { style: scanOptionsStyle },
                        _react2.default.createElement(
                            'div',
                            { className: 'scanningSpinner',
                                onClick: this._cancelScan,
                                onMouseEnter: this._showCancel,
                                onMouseLeave: this._resumeScan },
                            spinnerContent
                        )
                    );
                } else {
                    scanButton = _react2.default.createElement(
                        'div',
                        { style: scanOptionsStyle },
                        _react2.default.createElement(
                            'button',
                            { style: buttonStyle, onClick: this._onStartScan },
                            'Go'
                        )
                    );
                }

                if (this.state.devicesLoaded || this.state.scanStarted) {
                    devicesContainer = _react2.default.createElement(_devicesFound2.default, {
                        devices: this.state.devices,
                        devicesloaded: this._onDevicesLoaded,
                        platform: this.state.platform,
                        canceled: this.state.canceled,
                        bacnet: this.state.selectedProxyUuid });
                }

                deviceContent = _react2.default.createElement(
                    'div',
                    { className: 'device-box device-scan' },
                    _react2.default.createElement(
                        'div',
                        { style: platformNameStyle },
                        _react2.default.createElement(
                            'div',
                            { style: scanOptionsStyle },
                            _react2.default.createElement(
                                'b',
                                null,
                                'Instance: '
                            )
                        ),
                        _react2.default.createElement(
                            'div',
                            { style: scanOptionsStyle },
                            platform.name
                        )
                    ),
                    _react2.default.createElement(
                        'div',
                        { style: scanOptionsStyle },
                        _react2.default.createElement(
                            'b',
                            null,
                            'Method: '
                        )
                    ),
                    _react2.default.createElement(
                        'div',
                        { style: scanOptionsStyle },
                        methodSelect
                    ),
                    _react2.default.createElement(
                        'div',
                        { style: scanOptionsStyle },
                        scanOptions
                    ),
                    scanButton
                );
            } else {
                defaultMessage = _react2.default.createElement(
                    'div',
                    null,
                    'Launch device installation from the side tree by clicking on the ',
                    _react2.default.createElement('i', { className: 'fa fa-cogs' }),
                    ' button next to the platform instance.'
                );
            }

            return _react2.default.createElement(
                'div',
                { className: 'view' },
                _react2.default.createElement(
                    'h2',
                    null,
                    'Install Devices'
                ),
                deviceContent,
                defaultMessage,
                _react2.default.createElement(
                    'div',
                    { className: 'device-box device-container' },
                    devicesContainer
                )
            );
        }
    }]);

    return ConfigureDevices;
}(_baseComponent2.default);

;

function getInitialState() {

    var state = devicesStore.getState();

    if (state.platform) {
        state.bacnetProxies = platformsStore.getRunningBacnetProxies(state.platform.uuid);
        state.deviceMethod = state.bacnetProxies.length ? "scanForDevices" : "addDevicesManually";

        state.deviceStart = "";
        state.deviceEnd = "";
        state.address = "";

        state.startedInputtingDeviceEnd = false;

        state.newScan = true;
        state.devices = [];

        if (state.deviceMethod === "scanForDevices") {
            state.selectedProxyUuid = state.bacnetProxies[0].uuid;
        }

        state.scanning = false;
        state.canceled = false;
        state.devicesLoaded = false;
        state.scanStarted = false;
        state.cancelButton = false;
    }

    return state;
}

exports.default = ConfigureDevices;

},{"../action-creators/devices-action-creators":4,"../action-creators/status-indicator-action-creators":10,"../stores/devices-store":60,"../stores/platforms-store":65,"./base-component":12,"./devices-found":27,"react":undefined}],17:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

var _editPointForm = require('./edit-point-form');

var _editPointForm2 = _interopRequireDefault(_editPointForm);

var _previewRegistryForm = require('./preview-registry-form');

var _previewRegistryForm2 = _interopRequireDefault(_previewRegistryForm);

var _newColumnForm = require('./new-column-form');

var _newColumnForm2 = _interopRequireDefault(_newColumnForm);

var _configDeviceForm = require('./config-device-form');

var _configDeviceForm2 = _interopRequireDefault(_configDeviceForm);

var _editSelectButton = require('./control_buttons/edit-select-button');

var _editSelectButton2 = _interopRequireDefault(_editSelectButton);

var _editColumnsButton = require('./control_buttons/edit-columns-button');

var _editColumnsButton2 = _interopRequireDefault(_editColumnsButton);

var _registryRow = require('./registry-row');

var _registryRow2 = _interopRequireDefault(_registryRow);

var _immutable = require('immutable');

var _immutable2 = _interopRequireDefault(_immutable);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var FilterPointsButton = require('./control_buttons/filter-points-button');
var ControlButton = require('./control-button');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');

var registryWs, registryWebsocket;
var _defaultColumnWidth = "200px";

var ConfigureRegistry = function (_BaseComponent) {
    _inherits(ConfigureRegistry, _BaseComponent);

    function ConfigureRegistry(props) {
        _classCallCheck(this, ConfigureRegistry);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(ConfigureRegistry).call(this, props));

        _this._bind("_onFilterBoxChange", "_onClearFilter", "_onAddPoint", "_onRemovePoints", "_removePoints", "_selectAll", "_onAddColumn", "_onCloneColumn", "_onRemoveColumn", "_removeColumn", "_onFindNext", "_onReplace", "_onReplaceAll", "_onClearFind", "_cancelRegistry", "_saveRegistry", "_removeFocus", "_resetState", "_addColumn", "_selectCells", "_cloneColumn", "_onStoresChange", "_fetchExtendedPoints", "_onRegistrySave", "_focusOnDevice", "_handleKeyDown", "_onSelectForDelete", "_resizeColumn");

        _this.state = _this._resetState(_this.props.device);

        _this.state.keyboardRange = [-1, -1];
        return _this;
    }

    _createClass(ConfigureRegistry, [{
        key: 'componentDidMount',
        value: function componentDidMount() {
            this.containerDiv = document.getElementsByClassName("fixed-table-container")[0];
            this.fixedHeader = document.getElementsByClassName("header-background")[0];
            this.fixedInner = document.getElementsByClassName("fixed-table-container-inner")[0];
            this.registryTable = document.getElementsByClassName("registryConfigTable")[0];

            devicesStore.addChangeListener(this._onStoresChange);
            document.addEventListener("keydown", this._handleKeyDown);
        }
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {
            devicesStore.removeChangeListener(this._onStoresChange);
            document.removeEventListener("keydown", this._handleKeyDown);
        }
    }, {
        key: 'componentDidUpdate',
        value: function componentDidUpdate() {

            if (this.scrollToBottom) {
                this.containerDiv.scrollTop = this.containerDiv.scrollHeight;

                this.scrollToBottom = false;
            }

            if (this.resizeTable) {
                this.fixedHeader.style.width = this.registryTable.clientWidth + "px";
                this.fixedInner.style.width = this.registryTable.clientWidth + "px";

                this.resizeTable = false;
            }

            if (this.state.selectedCellRow !== null) {
                var focusedCell = document.getElementsByClassName("focusedCell")[0];
                if (focusedCell) {
                    focusedCell.focus();
                }
            }
        }
    }, {
        key: 'componentWillReceiveProps',
        value: function componentWillReceiveProps(nextProps) {
            if (this.props.device !== nextProps.device) {
                var newState = this._resetState(nextProps.device);
                newState.keyboardRange = this.state.keyboardRange;

                this.setState(newState);
            }
        }
    }, {
        key: '_handleKeyDown',
        value: function _handleKeyDown(keydown) {

            if (keydown.target.nodeName !== "INPUT" && this.state.deviceHasFocus) {
                if (this.state.keyboardStarted) {
                    switch (keydown.which) {
                        case 17:
                            // Control key            
                            this.setState({ keyboardRange: this.state.keyboardRange });
                            break;
                        case 27:
                            // ESC
                            this.setState({ keyboardRange: [-1, -1] });
                            this.setState({ keyboardStarted: false });

                            break;
                        case 13:
                            // Enter

                            this._fetchExtendedPoints(this.state.keyboardRange);

                            break;
                        // case 9:    //Tab
                        case 32: //Space
                        case 40:
                            //Down
                            keydown.preventDefault();

                            if (keydown.shiftKey) // extend down
                                {
                                    var newIndex = this.state.keyboardRange[1] + 1;

                                    if (newIndex < this.state.registryValues.length) {
                                        // this.setState({ keyboardIndex: newIndex });

                                        if (newIndex > this.state.keyboardRange[1]) {
                                            this.state.keyboardRange[1] = newIndex;

                                            this.setState({ keyboardRange: this.state.keyboardRange });
                                        }
                                    }
                                } else // simple down
                                {
                                    var newIndex = this.state.keyboardRange[1] + 1;

                                    if (newIndex < this.state.registryValues.length) {
                                        // this.setState({ keyboardIndex: newIndex });
                                        this.setState({ keyboardRange: [newIndex, newIndex] });
                                    }
                                }

                            break;
                        case 38:
                            //Up
                            keydown.preventDefault();

                            if (keydown.shiftKey) // extend up
                                {
                                    var newIndex = this.state.keyboardRange[0] - 1;

                                    if (newIndex > -1) {
                                        // this.setState({ keyboardIndex: newIndex });

                                        if (newIndex < this.state.keyboardRange[0]) {
                                            this.state.keyboardRange[0] = newIndex;

                                            this.setState({ keyboardRange: this.state.keyboardRange });
                                        }
                                    }
                                } else // simple up
                                {
                                    var newIndex = this.state.keyboardRange[0] - 1;

                                    if (newIndex > -1) {
                                        // this.setState({ keyboardIndex: newIndex });
                                        this.setState({ keyboardRange: [newIndex, newIndex] });
                                    }
                                }

                            break;
                        case 46:
                            //Delete
                            _keyboard.cmd = "delete";

                            break;
                    }
                } else if (keydown.which === 17) // Control key
                    {
                        this.setState({ keyboardRange: [0, 0] });
                        this.setState({ keyboardStarted: true });
                    }
            } else {
                if (this.state.keyboardRange[0] !== -1 && this.state.keyboardRange[1] !== -1) {
                    this.setState({ keyboardRange: [-1, -1] });
                }
            }
        }
    }, {
        key: '_resizeColumn',
        value: function _resizeColumn(columnIndex, targetWidth) {

            var newRegistryValues = this.state.registryValues.map(function (row) {

                row = row.updateIn(["attributes", columnIndex], function (cell) {
                    cell.columnWidth = targetWidth;

                    return cell;
                });

                return row;
            });

            this.setState({ registryValues: newRegistryValues });
        }
    }, {
        key: '_resetState',
        value: function _resetState(device) {

            var state = {};

            state.keyPropsList = device.keyProps;
            state.filterColumn = state.keyPropsList[0];

            state.registryValues = getPointsFromStore(device, state.keyPropsList);

            state.columnNames = [];
            // state.pointNames = [];
            state.filteredList = [];

            state.deviceHasFocus = true;

            state.selectedPoints = devicesStore.getSelectedPoints(device);

            if (state.registryValues.length > 0) {
                state.columnNames = state.registryValues[0].get("attributes").map(function (column) {
                    return column.key;
                });
            }

            state.pointsToDelete = [];
            state.allSelected = false;

            state.selectedCells = [];
            state.selectedCellRow = null;
            state.selectedCellColumn = null;
            state.filterOn = false;

            this.scrollToBottom = false;
            this.resizeTable = false;

            // this.keyboardIndex = -1;

            return state;
        }
    }, {
        key: '_onStoresChange',
        value: function _onStoresChange() {

            var deviceHasFocus = devicesStore.deviceHasFocus(this.props.device.id);

            if (deviceHasFocus !== this.state.deviceHasFocus) {
                this.setState({ deviceHasFocus: deviceHasFocus });
            }
        }
    }, {
        key: '_fetchExtendedPoints',
        value: function _fetchExtendedPoints(keyboardRange) {

            var configRequests = {};

            var registryValues = this.state.registryValues.map(function (attributesList) {

                if (!attributesList.get("selected")) {
                    if (attributesList.get("virtualIndex") >= this.state.keyboardRange[0] && attributesList.get("virtualIndex") <= this.state.keyboardRange[1]) {
                        if (!configRequests.hasOwnProperty(attributesList.get("bacnetObjectType"))) {
                            configRequests[attributesList.get("bacnetObjectType")] = [];
                        }

                        configRequests[attributesList.get("bacnetObjectType")].push(attributesList.get("index"));

                        attributesList = attributesList.set("selected", true);
                    }
                }

                return attributesList;
            }, this);

            this.setState({ registryValues: registryValues });

            // _setUpRegistrySocket();

            //TODO: hook up onmessage in configure-registry.jsx or in registry-row.jsw
            // registryWs.send(JSON.stringify(configRequests));
        }
    }, {
        key: '_setUpRegistrySocket',
        value: function _setUpRegistrySocket() {

            if (typeof registryWebsocket === "undefined" || registryWebsocket === null) {
                registryWebsocket = "ws://" + window.location.host + "/vc/ws/configure";
                if (window.WebSocket) {
                    registryWs = new WebSocket(devicesWebsocket);
                } else if (window.MozWebSocket) {
                    registryWs = MozWebSocket(devicesWebsocket);
                }

                registryWS.onmessage = function (evt) {
                    // devicesActionCreators.pointDataReceived(evt.data, this.props.device);

                    // var warnings = devicesStore.getWarnings();

                    // if (!objectIsEmpty(warnings))
                    // {
                    //     for (var key in warnings)
                    //     {
                    //         var values = warnings[key].items.join(", ");

                    //         statusIndicatorActionCreators.openStatusIndicator(
                    //             "error", 
                    //             warnings[key].message + "ID: " + values, 
                    //             values, 
                    //             "left"
                    //         );
                    //     }
                    // }

                }.bind(this);
            }
        }
    }, {
        key: '_focusOnDevice',
        value: function _focusOnDevice() {
            devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);
            console.log("focused on device");
        }
    }, {
        key: '_onFilterBoxChange',
        value: function _onFilterBoxChange(filterValue, column) {
            this.setState({ filterOn: true });

            this.setState({
                registryValues: getFilteredPoints(this.state.registryValues, filterValue, column)
            });
        }
    }, {
        key: '_onClearFilter',
        value: function _onClearFilter() {
            this.setState({ filterOn: false });
        }
    }, {
        key: '_onAddPoint',
        value: function _onAddPoint() {

            var pointValues = [];

            this.state.registryValues[0].get("attributes").forEach(function (attribute) {
                pointValues.push({
                    "key": attribute.key,
                    "label": attribute.label,
                    "value": "",
                    "editable": true,
                    "keyProp": attribute.keyProp
                });
            }, this);

            modalActionCreators.openModal(_react2.default.createElement(_editPointForm2.default, {
                attributes: _immutable2.default.List(pointValues),
                selectedPoints: this.state.selectedPoints,
                deviceId: this.props.device.id,
                deviceAddress: this.props.device.address }));
        }
    }, {
        key: '_onRemovePoints',
        value: function _onRemovePoints() {

            var promptText, confirmText, confirmAction, cancelText;

            if (this.state.pointsToDelete.length > 0) {
                promptText = "Are you sure you want to delete these points? " + this.state.pointsToDelete.join(", ");
                confirmText = "Delete";
                confirmAction = this._removePoints.bind(this, this.state.pointsToDelete);
            } else {
                promptText = "Select points to delete.";
                cancelText = "OK";
            }

            modalActionCreators.openModal(_react2.default.createElement(ConfirmForm, {
                promptTitle: 'Remove Points',
                promptText: promptText,
                confirmText: confirmText,
                onConfirm: confirmAction,
                cancelText: cancelText
            }));
        }
    }, {
        key: '_removePoints',
        value: function _removePoints(pointsToDelete) {

            pointsToDelete.forEach(function (pointToDelete) {

                var index = -1;
                // var pointValue = "";

                this.state.registryValues.find(function (row, i) {
                    var pointMatched = row.getIn(["attributes", 0]).value === pointToDelete;

                    if (pointMatched) {
                        index = i;
                    }

                    return pointMatched;
                });

                if (index > -1) {
                    this.state.registryValues.splice(index, 1);
                }
            }, this);

            this.setState({ registryValues: this.state.registryValues });
            this.setState({ pointsToDelete: [] });
            // this.setState({ pointNames: this.state.pointNames });

            modalActionCreators.closeModal();
        }
    }, {
        key: '_onSelectForDelete',
        value: function _onSelectForDelete(pointName) {

            var index = this.state.pointsToDelete.indexOf(pointName);

            if (index < 0) {
                this.state.pointsToDelete.push(pointName);
            } else {
                this.state.pointsToDelete.splice(index, 1);
            }

            this.setState({ pointsToDelete: this.state.pointsToDelete });
        }
    }, {
        key: '_selectAll',
        value: function _selectAll() {
            var allSelected = !this.state.allSelected;
            this.setState({ allSelected: allSelected });
        }
    }, {
        key: '_onAddColumn',
        value: function _onAddColumn(index) {

            var newColumnLabel = this.state.registryValues[0].getIn(["attributes", index]).label + "_";

            modalActionCreators.openModal(_react2.default.createElement(_newColumnForm2.default, {
                columnNames: this.state.columnNames,
                column: index,
                onConfirm: this._addColumn
            }));
        }
    }, {
        key: '_addColumn',
        value: function _addColumn(newColumnLabel, index) {

            var newColumn = newColumnLabel.toLowerCase().replace(/ /g, "_");
            this.state.columnNames.splice(index + 1, 0, newColumn);
            this.state.keyPropsList.push(newColumn);

            this.setState({ columnNames: this.state.columnNames });
            this.setState({ keyPropsList: this.state.keyPropsList });

            var newRegistryValues = this.state.registryValues.map(function (row) {

                row = row.updateIn(["attributes"], function (columnCells) {
                    return columnCells.splice(index + 1, 0, {
                        "key": newColumn,
                        "label": newColumnLabel,
                        "value": "",
                        "editable": true,
                        "keyProp": true,
                        "columnWidth": _defaultColumnWidth
                    });
                });

                return row;
            });

            this.resizeTable = true;

            this.setState({ registryValues: newRegistryValues });
        }
    }, {
        key: '_onCloneColumn',
        value: function _onCloneColumn(index) {

            modalActionCreators.openModal(_react2.default.createElement(_newColumnForm2.default, {
                columnNames: this.state.columnNames,
                column: index,
                onConfirm: this._cloneColumn
            }));
        }
    }, {
        key: '_cloneColumn',
        value: function _cloneColumn(newColumnLabel, index) {

            var newColumn = newColumnLabel.toLowerCase().replace(/ /g, "_");
            this.state.columnNames.splice(index + 1, 0, newColumn);
            this.state.keyPropsList.push(newColumn);

            this.setState({ columnNames: this.state.columnNames });
            this.setState({ keyPropsList: this.state.keyPropsList });

            var newRegistryValues = this.state.registryValues.map(function (row) {

                var clonedCell = {};

                var columnCell = row.getIn(["attributes", index]);

                for (var key in columnCell) {
                    clonedCell[key] = columnCell[key];
                }

                clonedCell.label = newColumnLabel;
                clonedCell.key = newColumn;

                row = row.updateIn(["attributes"], function (columnCells) {
                    return columnCells.splice(index + 1, 0, clonedCell);
                });

                return row;
            });

            this.resizeTable = true;

            this.setState({ registryValues: newRegistryValues });
        }
    }, {
        key: '_onRemoveColumn',
        value: function _onRemoveColumn(index) {

            var columnHeader = this.state.registryValues[0].getIn(["attributes", index]).label;
            var promptText = "Are you sure you want to delete the column, " + columnHeader + "?";

            modalActionCreators.openModal(_react2.default.createElement(ConfirmForm, {
                promptTitle: 'Remove Column',
                promptText: promptText,
                confirmText: 'Delete',
                onConfirm: this._removeColumn.bind(this, index)
            }));
        }
    }, {
        key: '_removeColumn',
        value: function _removeColumn(index) {

            var columnName = this.state.columnNames[index];

            this.state.columnNames.splice(index, 1);

            var newValues = this.state.registryValues.map(function (row) {
                return row.updateIn(["attributes"], function (columnCells) {
                    return columnCells.splice(index, 1);
                });
            });

            index = this.state.keyPropsList.indexOf(columnName);

            if (index > -1) {
                this.state.keyPropsList.splice(index, 1);
            }

            this.setState({ keyPropsList: this.state.keyPropsList });
            this.setState({ columnNames: this.state.columnNames });
            this.setState({ registryValues: newValues });

            this.resizeTable = true;

            modalActionCreators.closeModal();
        }
    }, {
        key: '_removeFocus',
        value: function _removeFocus() {
            this.setState({ selectedCellRow: null });
        }
    }, {
        key: '_selectCells',
        value: function _selectCells(findValue, column) {
            var selectedCells = [];

            this.setState({ registryValues: this.state.registryValues.map(function (row, index) {

                    //searching i-th column in each row, and if the cell contains the target value, select it
                    row.get("attributes").get(column).selected = row.get("attributes").get(column).value.indexOf(findValue) > -1;

                    if (row.get("attributes").get(column).selected) {
                        selectedCells.push(index);
                    }

                    return row;
                })
            });

            this.setState({ selectedCells: selectedCells });

            if (selectedCells.length > 0) {
                // this.setState({ selectedCells: selectedCells });
                this.setState({ selectedCellColumn: column });

                //set focus to the first selected cell
                this.setState({ selectedCellRow: selectedCells[0] });
            }

            return selectedCells;
        }
    }, {
        key: '_onFindNext',
        value: function _onFindNext(findValue, column) {

            if (this.state.selectedCells.length === 0) {
                this._selectCells(findValue, column);
            } else {
                //we've already found the selected cells, so we need to advance focus to the next one
                if (this.state.selectedCells.length > 1) {
                    var selectedCellRow = this._goToNext(this.state.selectedCellRow, this.state.selectedCells);

                    this.setState({ selectedCellRow: selectedCellRow });
                }
            }
        }
    }, {
        key: '_onReplace',
        value: function _onReplace(findValue, replaceValue, column) {

            if (!this.state.selectedCellRow) {
                this._onFindNext(findValue, column);
            } else {
                var newValue;

                this.state.registryValues[this.state.selectedCellRow] = this.state.registryValues[this.state.selectedCellRow].updateIn(["attributes", column], function (item) {
                    newValue = item.value = item.value.replace(findValue, replaceValue);
                    return item;
                });

                //If the cell no longer has the target value, deselect it and move focus to the next selected cell
                if (newValue.indexOf(findValue) < 0) {
                    this.state.registryValues[this.state.selectedCellRow] = this.state.registryValues[this.state.selectedCellRow].updateIn(["attributes", column], function (item) {
                        item.selected = false;
                        return item;
                    });

                    //see if there will even be another selected cell to move to
                    var selectedCells = this.state.selectedCells.slice();
                    var index = selectedCells.indexOf(this.state.selectedCellRow);

                    if (index > -1) {
                        selectedCells.splice(index, 1);
                    }

                    if (selectedCells.length > 0) {
                        var selectedCellRow = this._goToNext(this.state.selectedCellRow, this.state.selectedCells);

                        this.setState({ selectedCellRow: selectedCellRow });
                        this.setState({ selectedCells: selectedCells });
                    } else {
                        //there were no more selected cells, so clear everything out
                        this.setState({ selectedCells: [] });
                        this.setState({ selectedCellRow: null });
                        this.setState({ selectedCellColumn: null });
                    }
                }

                this.setState({ registryValues: this.state.registryValues });
            }
        }
    }, {
        key: '_onReplaceAll',
        value: function _onReplaceAll(findValue, replaceValue, column) {
            var _this2 = this;

            var selectedCellsToKeep = [];

            this.state.selectedCells.forEach(function (selectedCell) {

                // var newValue = this.state.registryValues[selectedCell].attributes[column].value.replace(findValue, replaceValue);

                var newValue;

                _this2.state.registryValues[selectedCell] = _this2.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                    newValue = item.value = item.value.replace(findValue, replaceValue);
                    return item;
                });

                if (newValue.indexOf(findValue) < 0) {
                    _this2.state.registryValues[selectedCell] = _this2.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                        item.selected = false;
                        selectedCellsToKeep.push(selectedCell);
                        return item;
                    });
                }
            });

            this.setState({ selectedCellRow: null });
            this.setState({ selectedCells: selectedCellsToKeep });
            this.setState({ selectedCellColumn: null });
            this.setState({ registryValues: this.state.registryValues });
        }
    }, {
        key: '_onClearFind',
        value: function _onClearFind(column) {
            var _this3 = this;

            // var registryValues = this.state.registryValues.slice();

            this.state.selectedCells.forEach(function (row) {
                _this3.state.registryValues[row] = _this3.state.registryValues[row].updateIn(["attributes", column], function (item) {
                    item.selected = false;
                    return item;
                });
            }, this);

            this.setState({ registryValues: this.state.registryValues });
            this.setState({ selectedCells: [] });
            this.setState({ selectedCellRow: null });
            this.setState({ selectedCellColumn: null });
        }
    }, {
        key: '_goToNext',
        value: function _goToNext(selectedCellRow, selectedCells) {

            //this is the row with current focus
            var rowIndex = selectedCells.indexOf(selectedCellRow);

            if (rowIndex > -1) {
                //either set focus to the next one in the selected cells list
                if (rowIndex < selectedCells.length - 1) {
                    selectedCellRow = selectedCells[++rowIndex];
                } else //or if we're at the end of the list, go back to the first one
                    {
                        selectedCellRow = selectedCells[0];
                    }
            }

            return selectedCellRow;
        }
    }, {
        key: '_cancelRegistry',
        value: function _cancelRegistry() {
            devicesActionCreators.cancelRegistry(this.props.device);
        }
    }, {
        key: '_onRegistrySave',
        value: function _onRegistrySave() {
            modalActionCreators.openModal(_react2.default.createElement(_previewRegistryForm2.default, {
                deviceId: this.props.device.id,
                deviceAddress: this.props.device.address,
                deviceName: this.props.device.name,
                attributes: this.state.registryValues.map(function (row) {
                    return row.get("attributes");
                }),
                onsaveregistry: this._saveRegistry }));
        }
    }, {
        key: '_saveRegistry',
        value: function _saveRegistry() {

            devicesActionCreators.saveRegistry(this.props.device.id, this.props.device.address, this.state.registryValues.map(function (row) {
                return row.get("attributes");
            }));

            modalActionCreators.openModal(_react2.default.createElement(_configDeviceForm2.default, { device: this.props.device }));
        }
    }, {
        key: 'render',
        value: function render() {

            var registryRows, registryHeader, registryButtons;

            if (this.state.registryValues.length) {
                registryRows = this.state.registryValues.map(function (attributesList, rowIndex) {

                    var virtualRow = attributesList.get("virtualIndex");

                    var keyboardSelected;

                    if (this.state.keyboardRange[0] !== -1 && this.state.keyboardRange[1] !== -1) {
                        keyboardSelected = virtualRow >= this.state.keyboardRange[0] && virtualRow <= this.state.keyboardRange[1];
                    }

                    var immutableProps = _immutable2.default.fromJS({
                        rowIndex: rowIndex,
                        deviceId: this.props.device.id,
                        deviceAddress: this.props.device.address,
                        deviceName: this.props.device.name,
                        keyProps: this.props.device.keyProps,
                        selectedCell: this.state.selectedCellRow === rowIndex,
                        selectedCellColumn: this.state.selectedCellColumn,
                        filterOn: this.state.filterOn,
                        keyboardSelected: keyboardSelected
                    });

                    return _react2.default.createElement(_registryRow2.default, {
                        key: "registryRow-" + attributesList.get("attributes").get(0).value,
                        attributesList: attributesList,
                        immutableProps: immutableProps,
                        allSelected: this.state.allSelected,
                        oncheckselect: this._onSelectForDelete,
                        onresizecolumn: this._resizeColumn });
                }, this);

                var headerColumns = [];
                var tableIndex = 0;

                this.state.registryValues[0].get("attributes").forEach(function (item, index) {

                    if (item.keyProp) {
                        var editSelectButton = _react2.default.createElement(_editSelectButton2.default, {
                            onremove: this._onRemoveColumn,
                            onadd: this._onAddColumn,
                            onclone: this._onCloneColumn,
                            column: index,
                            name: this.props.device.id + "-" + item.key });

                        var editColumnButton = _react2.default.createElement(_editColumnsButton2.default, {
                            column: index,
                            tooltipMsg: 'Edit Column',
                            findnext: this._onFindNext,
                            replace: this._onReplace,
                            replaceall: this._onReplaceAll,
                            replaceEnabled: this.state.selectedCells.length > 0,
                            onclear: this._onClearFind,
                            onhide: this._removeFocus,
                            name: this.props.device.id + "-" + item.key });

                        var headerCell;

                        var columnWidth = {
                            width: item.columnWidth
                        };

                        if (tableIndex === 0) {
                            // var firstColumnWidth = {
                            //     width: (item.length * 10) + "px"
                            // }

                            var filterPointsTooltip = {
                                content: "Filter Points",
                                "x": 80,
                                "y": -60
                            };

                            var filterButton = _react2.default.createElement(FilterPointsButton, {
                                name: "filterRegistryPoints-" + this.props.device.id,
                                tooltipMsg: filterPointsTooltip,
                                onfilter: this._onFilterBoxChange,
                                onclear: this._onClearFilter,
                                column: index });

                            var addPointTooltip = {
                                content: "Add New Point",
                                "x": 80,
                                "y": -60
                            };

                            var addPointButton = _react2.default.createElement(ControlButton, {
                                name: "addRegistryPoint-" + this.props.device.id,
                                tooltip: addPointTooltip,
                                controlclass: 'add_point_button',
                                fontAwesomeIcon: 'plus',
                                clickAction: this._onAddPoint });

                            var removePointTooltip = {
                                content: "Remove Points",
                                "x": 80,
                                "y": -60
                            };

                            var removePointsButton = _react2.default.createElement(ControlButton, {
                                name: "removeRegistryPoints-" + this.props.device.id,
                                fontAwesomeIcon: 'minus',
                                tooltip: removePointTooltip,
                                controlclass: 'remove_point_button',
                                clickAction: this._onRemovePoints });

                            if (item.editable) {
                                headerCell = _react2.default.createElement(
                                    'th',
                                    { key: "header-" + item.key + "-" + index, style: columnWidth },
                                    _react2.default.createElement(
                                        'div',
                                        { className: 'th-inner zztop' },
                                        item.label,
                                        filterButton,
                                        addPointButton,
                                        removePointsButton,
                                        editSelectButton,
                                        editColumnButton
                                    )
                                );
                            } else {
                                headerCell = _react2.default.createElement(
                                    'th',
                                    { key: "header-" + item.key + "-" + index, style: columnWidth },
                                    _react2.default.createElement(
                                        'div',
                                        { className: 'th-inner zztop' },
                                        item.label,
                                        filterButton,
                                        addPointButton,
                                        removePointsButton
                                    )
                                );
                            }
                        } else {
                            if (item.editable) {
                                headerCell = _react2.default.createElement(
                                    'th',
                                    { key: "header-" + item.key + "-" + index, style: columnWidth },
                                    _react2.default.createElement(
                                        'div',
                                        { className: 'th-inner' },
                                        item.label,
                                        editSelectButton,
                                        editColumnButton
                                    )
                                );
                            } else {
                                headerCell = _react2.default.createElement(
                                    'th',
                                    { key: "header-" + item.key + "-" + index, style: columnWidth },
                                    _react2.default.createElement(
                                        'div',
                                        { className: 'th-inner' },
                                        item.label
                                    )
                                );
                            }
                        }

                        ++tableIndex;
                        headerColumns.push(headerCell);

                        if (index + 1 < this.state.registryValues[0].get("attributes").size) {
                            var resizeHandle = _react2.default.createElement('th', { className: 'resize-handle-th' });
                            headerColumns.push(resizeHandle);
                        }
                    }
                }, this);

                var checkboxColumnStyle = {
                    width: "24px"
                };

                registryHeader = _react2.default.createElement(
                    'tr',
                    { key: 'header-values' },
                    _react2.default.createElement(
                        'th',
                        { style: checkboxColumnStyle, key: 'header-checkbox' },
                        _react2.default.createElement(
                            'div',
                            { className: 'th-inner' },
                            _react2.default.createElement('input', { type: 'checkbox',
                                onChange: this._selectAll,
                                checked: this.state.allSelected })
                        )
                    ),
                    headerColumns
                );

                var wideDiv = {
                    width: "100%",
                    textAlign: "center",
                    paddingTop: "20px"
                };

                var tooltipX = 320;
                var tooltipY = 150;

                var saveTooltip = {
                    "content": "Save Configuration",
                    "xOffset": tooltipX,
                    "yOffset": tooltipY
                };

                var saveButton = _react2.default.createElement(ControlButton, {
                    name: 'saveConfigButton',
                    tooltip: saveTooltip,
                    fontAwesomeIcon: 'save',
                    clickAction: this._onRegistrySave });

                var cancelTooltip = {
                    "content": "Cancel Configuration",
                    "xOffset": tooltipX,
                    "yOffset": tooltipY
                };

                var cancelIcon = _react2.default.createElement(
                    'span',
                    null,
                    '✘'
                );
                var cancelButton = _react2.default.createElement(ControlButton, {
                    name: 'cancelConfigButton',
                    tooltip: cancelTooltip,
                    icon: cancelIcon,
                    clickAction: this._cancelRegistry });

                registryButtons = _react2.default.createElement(
                    'div',
                    { className: 'registry-buttons', style: wideDiv },
                    _react2.default.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        cancelButton
                    ),
                    _react2.default.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        saveButton
                    )
                );
            };

            var visibilityClass = this.props.device.showPoints ? "collapsible-registry-values slow-show" : "collapsible-registry-values slow-hide";

            return _react2.default.createElement(
                'div',
                { className: visibilityClass,
                    tabIndex: 1,
                    onFocus: this._focusOnDevice },
                _react2.default.createElement(
                    'div',
                    { className: 'fixed-table-container' },
                    _react2.default.createElement('div', { className: 'header-background' }),
                    _react2.default.createElement(
                        'div',
                        { className: 'fixed-table-container-inner' },
                        _react2.default.createElement(
                            'table',
                            { className: 'registryConfigTable' },
                            _react2.default.createElement(
                                'thead',
                                null,
                                registryHeader
                            ),
                            _react2.default.createElement(
                                'tbody',
                                null,
                                registryRows
                            )
                        )
                    )
                ),
                registryButtons
            );
        }
    }]);

    return ConfigureRegistry;
}(_baseComponent2.default);

;

function getFilteredPoints(registryValues, filterStr, column) {

    var virtualCount = 0;

    return registryValues.map(function (row, rowIndex) {

        row = row.set("visible", filterStr === "" || row.get("attributes").get(column).value.trim().toUpperCase().indexOf(filterStr.trim().toUpperCase()) > -1);

        if (row.get("visible")) {
            row = row.set("virtualIndex", virtualCount);
            ++virtualCount;
        } else {
            row = row.set("virtualIndex", -2);
        }

        return row;
    });
}

function getPointsFromStore(device, keyPropsList) {
    return initializeList(devicesStore.getRegistryValues(device), keyPropsList);
}

function initializeList(registryConfig, keyPropsList) {
    return registryConfig.map(function (row, rowIndex) {

        var bacnetObjectType, objectIndex;

        row.forEach(function (cell) {
            cell.keyProp = keyPropsList.indexOf(cell.key) > -1;

            if (cell.keyProp) {
                if (rowIndex === 0) {
                    var minWidth = cell.value.length * 10;

                    cell.columnWidth = (minWidth > 200 ? minWidth : 200) + "px";
                } else {
                    cell.columnWidth = cell.hasOwnProperty("columnWidth") ? cell.columnWidth : _defaultColumnWidth;
                }
            }

            if (cell.key === "bacnet_object_type") {
                bacnetObjectType = cell.value;
            } else if (cell.key === "index") {
                objectIndex = cell.value;
            }
        });

        return _immutable2.default.fromJS({
            visible: true,
            virtualIndex: rowIndex,
            bacnetObjectType: bacnetObjectType,
            index: objectIndex,
            attributes: row,
            selected: false
        });
    });
}

exports.default = ConfigureRegistry;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"../stores/devices-store":60,"./base-component":12,"./config-device-form":15,"./confirm-form":18,"./control-button":20,"./control_buttons/edit-columns-button":21,"./control_buttons/edit-select-button":22,"./control_buttons/filter-points-button":23,"./edit-point-form":28,"./new-column-form":34,"./preview-registry-form":43,"./registry-row":45,"immutable":undefined,"react":undefined}],18:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var ConfirmForm = React.createClass({
    displayName: 'ConfirmForm',

    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function _onSubmit(e) {
        e.preventDefault();
        this.props.onConfirm();
    },
    render: function render() {

        var promptText = this.props.promptText;

        if (this.props.hasOwnProperty("preText") && this.props.hasOwnProperty("postText")) {
            promptText = React.createElement(
                'b',
                null,
                promptText
            );
        }

        var confirmButton = this.props.confirmText ? React.createElement(
            'button',
            { className: 'button' },
            this.props.confirmText
        ) : "";

        var cancelText = this.props.cancelText ? this.props.cancelText : "Cancel";

        return React.createElement(
            'form',
            { className: 'confirmation-form', onSubmit: this._onSubmit },
            React.createElement(
                'h1',
                null,
                this.props.promptTitle
            ),
            React.createElement(
                'p',
                null,
                this.props.preText,
                promptText,
                this.props.postText
            ),
            React.createElement(
                'div',
                { className: 'form__actions' },
                React.createElement(
                    'button',
                    {
                        className: 'button button--secondary',
                        type: 'button',
                        onClick: this._onCancelClick,
                        autoFocus: true
                    },
                    cancelText
                ),
                confirmButton
            )
        );
    }
});

module.exports = ConfirmForm;

},{"../action-creators/modal-action-creators":5,"react":undefined}],19:[function(require,module,exports){
'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');

var Console = React.createClass({
    displayName: 'Console',

    render: function render() {
        return React.createElement(
            'div',
            { className: 'console' },
            React.createElement(Conversation, null),
            React.createElement(Composer, null)
        );
    }
});

module.exports = Console;

},{"./composer":14,"./conversation":24,"react":undefined}],20:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var controlButtonStore = require('../stores/control-button-store');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');
var OutsideClick = require('react-click-outside');

var ControlButton = React.createClass({
    displayName: 'ControlButton',

    getInitialState: function getInitialState() {
        var state = {};

        state.showTaptip = false;
        state.showTooltip = false;
        state.deactivateTooltip = false;

        state.selected = this.props.selected === true;

        state.taptipX = 0;
        state.taptipY = 0;
        state.tooltipX = 0;
        state.tooltipY = 0;

        state.tooltipOffsetX = 0;
        state.tooltipOffsetY = 0;
        state.taptipOffsetX = 0;
        state.taptipOffsetY = 0;

        if (this.props.hasOwnProperty("tooltip")) {
            if (this.props.tooltip.hasOwnProperty("x")) state.tooltipX = this.props.tooltip.x;

            if (this.props.tooltip.hasOwnProperty("y")) state.tooltipY = this.props.tooltip.y;

            if (this.props.tooltip.hasOwnProperty("xOffset")) state.tooltipOffsetX = this.props.tooltip.xOffset;

            if (this.props.tooltip.hasOwnProperty("yOffset")) state.tooltipOffsetY = this.props.tooltip.yOffset;
        }

        if (this.props.hasOwnProperty("taptip")) {
            if (this.props.taptip.hasOwnProperty("x")) state.taptipX = this.props.taptip.x;

            if (this.props.taptip.hasOwnProperty("y")) state.taptipY = this.props.taptip.y;

            if (this.props.taptip.hasOwnProperty("xOffset")) state.taptipOffsetX = this.props.taptip.xOffset;

            if (this.props.taptip.hasOwnProperty("yOffset")) state.taptipOffsetY = this.props.taptip.yOffset;
        }

        return state;
    },
    componentDidMount: function componentDidMount() {
        controlButtonStore.addChangeListener(this._onStoresChange);

        window.addEventListener('keydown', this._hideTaptip);
    },
    componentWillUnmount: function componentWillUnmount() {
        controlButtonStore.removeChangeListener(this._onStoresChange);

        window.removeEventListener('keydown', this._hideTaptip);
    },
    componentWillReceiveProps: function componentWillReceiveProps(nextProps) {
        this.setState({ selected: nextProps.selected === true });

        if (nextProps.selected === true) {
            this.setState({ showTooltip: false });
        }
    },
    _onStoresChange: function _onStoresChange() {

        var showTaptip = controlButtonStore.getTaptip(this.props.name);

        if (showTaptip !== null) {
            if (showTaptip !== this.state.showTaptip) {
                this.setState({ showTaptip: showTaptip });
            }

            this.setState({ selected: showTaptip === true });

            if (showTaptip === true) {
                this.setState({ showTooltip: false });
            } else {
                if (typeof this.props.closeAction == 'function') {
                    this.props.closeAction();
                }
            }
        }
    },
    handleClickOutside: function handleClickOutside() {
        if (this.state.showTaptip) {
            controlButtonActionCreators.hideTaptip(this.props.name);
        }
    },
    _showTaptip: function _showTaptip(evt) {

        if (!this.state.showTaptip) {
            if (!(this.props.taptip.hasOwnProperty("x") && this.props.taptip.hasOwnProperty("y"))) {
                this.setState({ taptipX: evt.clientX - this.state.taptipOffsetX });
                this.setState({ taptipY: evt.clientY - this.state.taptipOffsetY });
            }
        }

        controlButtonActionCreators.toggleTaptip(this.props.name);
    },
    _hideTaptip: function _hideTaptip(evt) {
        if (evt.keyCode === 27) {
            controlButtonActionCreators.hideTaptip(this.props.name);
        }
    },
    _showTooltip: function _showTooltip(evt) {
        this.setState({ showTooltip: true });

        if (!(this.props.tooltip.hasOwnProperty("x") && this.props.tooltip.hasOwnProperty("y"))) {
            this.setState({ tooltipX: evt.clientX - this.state.tooltipOffsetX });
            this.setState({ tooltipY: evt.clientY - this.state.tooltipOffsetY });
        }
    },
    _hideTooltip: function _hideTooltip() {
        this.setState({ showTooltip: false });
    },
    render: function render() {

        var taptip;
        var tooltip;
        var clickAction;
        var selectedStyle;

        var tooltipShow;
        var tooltipHide;

        var buttonIcon = this.props.icon ? this.props.icon : this.props.fontAwesomeIcon ? React.createElement('i', { className: "fa fa-" + this.props.fontAwesomeIcon }) : React.createElement(
            'div',
            { className: this.props.buttonClass },
            React.createElement(
                'span',
                null,
                this.props.unicodeIcon
            )
        );

        if (this.props.staySelected || this.state.selected === true || this.state.showTaptip === true) {
            selectedStyle = {
                backgroundColor: "#ccc"
            };
        } else if (this.props.tooltip) {
            var tooltipStyle = {
                display: this.state.showTooltip ? "block" : "none",
                position: "absolute",
                top: this.state.tooltipY + "px",
                left: this.state.tooltipX + "px"
            };

            var toolTipClasses = this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer";

            tooltipShow = this._showTooltip;
            tooltipHide = this._hideTooltip;

            tooltip = React.createElement(
                'div',
                { className: toolTipClasses,
                    style: tooltipStyle },
                React.createElement(
                    'div',
                    { className: 'tooltip_inner' },
                    React.createElement(
                        'div',
                        { className: 'opaque_inner' },
                        this.props.tooltip.content
                    )
                )
            );
        }

        if (this.props.taptip) {
            var taptipStyle = {
                display: this.state.showTaptip ? "block" : "none",
                position: "absolute",
                left: this.state.taptipX + "px",
                top: this.state.taptipY + "px"
            };

            if (this.props.taptip.styles) {
                this.props.taptip.styles.forEach(function (styleToAdd) {
                    taptipStyle[styleToAdd.key] = styleToAdd.value;
                });
            }

            var tapTipClasses = "taptip_outer";

            var taptipBreak = this.props.taptip.hasOwnProperty("break") ? this.props.taptip.break : React.createElement('br', null);
            var taptipTitle = this.props.taptip.hasOwnProperty("title") ? React.createElement(
                'h4',
                null,
                this.props.taptip.title
            ) : "";

            var innerStyle = {};

            if (this.props.taptip.hasOwnProperty("padding")) {
                innerStyle = {
                    padding: this.props.taptip.padding
                };
            }

            taptip = React.createElement(
                'div',
                { className: tapTipClasses,
                    style: taptipStyle },
                React.createElement(
                    'div',
                    { className: 'taptip_inner',
                        style: innerStyle },
                    React.createElement(
                        'div',
                        { className: 'opaque_inner' },
                        taptipTitle,
                        taptipBreak,
                        this.props.taptip.content
                    )
                )
            );

            clickAction = this.props.taptip.action ? this.props.taptip.action : this._showTaptip;
        } else if (this.props.clickAction) {
            clickAction = this.props.clickAction;
        }

        var controlButtonClass = this.props.controlclass ? this.props.controlclass : "control_button";

        var centering = this.props.hasOwnProperty("nocentering") && this.props.nocentering === true ? "" : "centeredDiv";

        var outerClasses = this.props.hasOwnProperty("floatleft") && this.props.floatleft === true ? "floatLeft" : "inlineBlock";

        return React.createElement(
            'div',
            { className: outerClasses },
            taptip,
            tooltip,
            React.createElement(
                'div',
                { className: controlButtonClass,
                    onClick: clickAction,
                    onMouseEnter: tooltipShow,
                    onMouseLeave: tooltipHide,
                    style: selectedStyle },
                React.createElement(
                    'div',
                    { className: centering },
                    buttonIcon
                )
            )
        );
    }
});

module.exports = OutsideClick(ControlButton);

},{"../action-creators/control-button-action-creators":3,"../stores/control-button-store":59,"react":undefined,"react-click-outside":undefined,"react-router":undefined}],21:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('../base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var ControlButton = require('../control-button');
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');

var EditColumnButton = function (_BaseComponent) {
    _inherits(EditColumnButton, _BaseComponent);

    function EditColumnButton(props) {
        _classCallCheck(this, EditColumnButton);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(EditColumnButton).call(this, props));

        _this._bind("_onFindBoxChange", "_onReplaceBoxChange", "_findNext", "_onClearEdit", "_replace", "_replaceAll", "_onKeyDown");

        _this.state = getStateFromStores(_this.props.name);
        return _this;
    }

    _createClass(EditColumnButton, [{
        key: '_onFindBoxChange',
        value: function _onFindBoxChange(e) {
            var findValue = e.target.value;

            this.setState({ findValue: findValue });

            this.props.onclear(this.props.column);
        }
    }, {
        key: '_onKeyDown',
        value: function _onKeyDown(callback, e) {

            if (e.keyCode === 13) //Enter
                {
                    callback();
                }
        }
    }, {
        key: '_onReplaceBoxChange',
        value: function _onReplaceBoxChange(e) {
            var replaceValue = e.target.value;

            this.setState({ replaceValue: replaceValue });
        }
    }, {
        key: '_findNext',
        value: function _findNext() {

            if (this.state.findValue === "") {
                this.props.onclear(this.props.column);
            } else {
                this.props.findnext(this.state.findValue, this.props.column);
            }
        }
    }, {
        key: '_onClearEdit',
        value: function _onClearEdit(e) {

            this.props.onclear(this.props.column);
            this.setState({ findValue: "" });
            this.setState({ replaceValue: "" });
            controlButtonActionCreators.hideTaptip(this.state.buttonName);
        }
    }, {
        key: '_replace',
        value: function _replace() {
            if (this.props.replaceEnabled) {
                this.props.replace(this.state.findValue, this.state.replaceValue, this.props.column);
            }
        }
    }, {
        key: '_replaceAll',
        value: function _replaceAll() {
            if (this.props.replaceEnabled) {
                this.props.replaceall(this.state.findValue, this.state.replaceValue, this.props.column);
            }
        }
    }, {
        key: 'render',
        value: function render() {

            var editBoxContainer = {
                position: "relative"
            };

            var inputStyle = {
                width: "100%",
                marginLeft: "10px",
                fontWeight: "normal"
            };

            var divWidth = {
                width: "85%"
            };

            var clearTooltip = {
                content: "Clear Search",
                x: 50,
                y: 0
            };

            var findTooltip = {
                content: "Find Next",
                x: 100,
                y: 0
            };

            var replaceTooltip = {
                content: "Replace",
                x: 100,
                y: 80
            };

            var replaceAllTooltip = {
                content: "Replace All",
                x: 100,
                y: 80
            };

            var buttonsStyle = {
                marginTop: "8px"
            };

            var replaceEnabled = !this.props.replaceEnabled ? "disableReplace" : "";

            var editBox = _react2.default.createElement(
                'div',
                { style: editBoxContainer },
                _react2.default.createElement(ControlButton, {
                    fontAwesomeIcon: 'ban',
                    tooltip: clearTooltip,
                    clickAction: this._onClearEdit }),
                _react2.default.createElement(
                    'div',
                    null,
                    _react2.default.createElement(
                        'table',
                        null,
                        _react2.default.createElement(
                            'tbody',
                            null,
                            _react2.default.createElement(
                                'tr',
                                null,
                                _react2.default.createElement(
                                    'td',
                                    { colSpan: '2' },
                                    'Find in Column'
                                )
                            ),
                            _react2.default.createElement(
                                'tr',
                                null,
                                _react2.default.createElement(
                                    'td',
                                    { width: '70%' },
                                    _react2.default.createElement('input', {
                                        type: 'text',
                                        style: inputStyle,
                                        onChange: this._onFindBoxChange,
                                        onKeyDown: this._onKeyDown.bind(this, this._findNext),
                                        value: this.state.findValue
                                    })
                                ),
                                _react2.default.createElement(
                                    'td',
                                    null,
                                    _react2.default.createElement(
                                        'div',
                                        { style: buttonsStyle },
                                        _react2.default.createElement(ControlButton, {
                                            fontAwesomeIcon: 'step-forward',
                                            tooltip: findTooltip,
                                            clickAction: this._findNext })
                                    )
                                )
                            ),
                            _react2.default.createElement(
                                'tr',
                                null,
                                _react2.default.createElement(
                                    'td',
                                    { className: replaceEnabled,
                                        colSpan: '2' },
                                    'Replace With'
                                )
                            ),
                            _react2.default.createElement(
                                'tr',
                                null,
                                _react2.default.createElement(
                                    'td',
                                    { className: replaceEnabled },
                                    _react2.default.createElement('input', {
                                        type: 'text',
                                        style: inputStyle,
                                        onChange: this._onReplaceBoxChange,
                                        onKeyDown: this._onKeyDown.bind(this, this._replace),
                                        value: this.state.replaceValue,
                                        disabled: !this.props.replaceEnabled
                                    })
                                ),
                                _react2.default.createElement(
                                    'td',
                                    { className: replaceEnabled },
                                    _react2.default.createElement(
                                        'div',
                                        { className: 'inlineBlock',
                                            style: buttonsStyle },
                                        _react2.default.createElement(ControlButton, {
                                            fontAwesomeIcon: 'step-forward',
                                            tooltip: replaceTooltip,
                                            clickAction: this._replace }),
                                        _react2.default.createElement(ControlButton, {
                                            fontAwesomeIcon: 'fast-forward',
                                            tooltip: replaceAllTooltip,
                                            clickAction: this._replaceAll })
                                    )
                                )
                            )
                        )
                    )
                )
            );

            var editTaptip = {
                "title": "Search Column",
                "content": editBox,
                "x": 80,
                "y": -150,
                "styles": [{ "key": "width", "value": "250px" }]
            };

            var editTooltip = {
                "content": this.props.tooltipMsg,
                "x": 160,
                "y": 0
            };

            var columnIndex = this.props.column;

            return _react2.default.createElement(ControlButton, {
                name: this.state.buttonName,
                taptip: editTaptip,
                tooltip: editTooltip,
                fontAwesomeIcon: 'pencil',
                controlclass: 'edit_column_button',
                closeAction: this.props.onhide });
        }
    }]);

    return EditColumnButton;
}(_baseComponent2.default);

;

var getStateFromStores = function getStateFromStores(buttonName) {
    return {
        findValue: "",
        replaceValue: "",
        buttonName: "editColumn-" + buttonName + "-controlButton"
    };
};

exports.default = EditColumnButton;

},{"../../action-creators/control-button-action-creators":3,"../base-component":12,"../control-button":20,"react":undefined}],22:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('../base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var ControlButton = require('../control-button');
var EditColumnButton = require('./edit-columns-button');
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');

var EditSelectButton = function (_BaseComponent) {
    _inherits(EditSelectButton, _BaseComponent);

    function EditSelectButton(props) {
        _classCallCheck(this, EditSelectButton);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(EditSelectButton).call(this, props));

        _this._bind("_onCloneColumn", "_onAddColumn", "_onRemoveColumn", "_onEditColumn");

        _this.state = {};

        _this.state.buttonName = "editSelect-" + _this.props.name + "-controlButton";
        _this.state.editColumnButton = "editColumn-" + _this.props.name + "-controlButton";
        return _this;
    }

    _createClass(EditSelectButton, [{
        key: '_onClose',
        value: function _onClose() {}
    }, {
        key: '_onCloneColumn',
        value: function _onCloneColumn() {
            this.props.onclone(this.props.column);
            controlButtonActionCreators.hideTaptip(this.state.buttonName);
        }
    }, {
        key: '_onAddColumn',
        value: function _onAddColumn() {
            this.props.onadd(this.props.column);
            controlButtonActionCreators.hideTaptip(this.state.buttonName);
        }
    }, {
        key: '_onRemoveColumn',
        value: function _onRemoveColumn() {
            this.props.onremove(this.props.column);
            controlButtonActionCreators.hideTaptip(this.state.buttonName);
        }
    }, {
        key: '_onEditColumn',
        value: function _onEditColumn() {
            controlButtonActionCreators.hideTaptip(this.state.buttonName);
            controlButtonActionCreators.toggleTaptip(this.state.editColumnButton);
        }
    }, {
        key: 'render',
        value: function render() {

            var editBoxContainer = {
                position: "relative"
            };

            var editBox = _react2.default.createElement(
                'div',
                { style: editBoxContainer },
                _react2.default.createElement(
                    'ul',
                    {
                        className: 'opList' },
                    _react2.default.createElement(
                        'li',
                        {
                            className: 'opListItem edit',
                            onClick: this._onEditColumn },
                        'Find and Replace'
                    ),
                    _react2.default.createElement(
                        'li',
                        {
                            className: 'opListItem clone',
                            onClick: this._onCloneColumn },
                        'Duplicate'
                    ),
                    _react2.default.createElement(
                        'li',
                        {
                            className: 'opListItem add',
                            onClick: this._onAddColumn },
                        'Add'
                    ),
                    _react2.default.createElement(
                        'li',
                        {
                            className: 'opListItem remove',
                            onClick: this._onRemoveColumn },
                        'Remove'
                    )
                )
            );

            var editSelectTaptip = {
                "content": editBox,
                "x": 80,
                "y": -80,
                "styles": [{ "key": "width", "value": "120px" }],
                "break": "",
                "padding": "0px"
            };

            var editSelectTooltip = {
                content: "Edit Column",
                "x": 80,
                "y": -60
            };

            return _react2.default.createElement(ControlButton, {
                name: this.state.buttonName,
                taptip: editSelectTaptip,
                tooltip: editSelectTooltip,
                controlclass: 'edit_button',
                fontAwesomeIcon: 'pencil',
                closeAction: this._onClose });
        }
    }]);

    return EditSelectButton;
}(_baseComponent2.default);

;

exports.default = EditSelectButton;

},{"../../action-creators/control-button-action-creators":3,"../base-component":12,"../control-button":20,"./edit-columns-button":21,"react":undefined}],23:[function(require,module,exports){
'use strict';

var React = require('react');

var ControlButton = require('../control-button');

var FilterPointsButton = React.createClass({
    displayName: 'FilterPointsButton',

    getInitialState: function getInitialState() {
        return getStateFromStores();
    },
    _onFilterBoxChange: function _onFilterBoxChange(e) {
        var filterValue = e.target.value;

        this.setState({ filterValue: filterValue });

        if (filterValue !== "") {
            this.props.onfilter(e.target.value, this.props.column);
        } else {
            this.props.onclear();
        }
    },
    _onClearFilter: function _onClearFilter(e) {
        this.setState({ filterValue: "" });
        this.props.onclear();
    },
    render: function render() {

        var filterBoxContainer = {
            position: "relative"
        };

        var inputStyle = {
            width: "100%",
            marginLeft: "10px",
            fontWeight: "normal"
        };

        var divWidth = {
            width: "85%"
        };

        var clearTooltip = {
            content: "Clear Filter",
            "x": 80,
            "y": 0
        };

        var filterBox = React.createElement(
            'div',
            { style: filterBoxContainer },
            React.createElement(ControlButton, {
                fontAwesomeIcon: 'ban',
                tooltip: clearTooltip,
                clickAction: this._onClearFilter }),
            React.createElement(
                'div',
                { className: 'inlineBlock' },
                React.createElement(
                    'div',
                    { className: 'inlineBlock' },
                    React.createElement('span', { className: 'fa fa-filter' })
                ),
                React.createElement(
                    'div',
                    { className: 'inlineBlock', style: divWidth },
                    React.createElement('input', {
                        type: 'search',
                        style: inputStyle,
                        onChange: this._onFilterBoxChange,
                        value: this.state.filterValue
                    })
                )
            )
        );

        var filterTaptip = {
            "title": "Filter Points",
            "content": filterBox,
            "x": 80,
            "y": -150,
            "styles": [{ "key": "width", "value": "200px" }]
        };

        var filterIcon = React.createElement('i', { className: 'fa fa-filter' });

        var holdSelect = this.state.filterValue !== "";

        return React.createElement(ControlButton, {
            name: this.props.name + "-ControlButton",
            taptip: filterTaptip,
            tooltip: this.props.tooltipMsg,
            controlclass: 'filter_button',
            staySelected: holdSelect,
            icon: filterIcon });
    }
});

function getStateFromStores() {
    return {
        filterValue: ""
    };
}

module.exports = FilterPointsButton;

},{"../control-button":20,"react":undefined}],24:[function(require,module,exports){
'use strict';

var $ = require('jquery');
var React = require('react');
var ReactDOM = require('react-dom');

var Exchange = require('./exchange');
var consoleStore = require('../stores/console-store');

var Conversation = React.createClass({
    displayName: 'Conversation',

    getInitialState: getStateFromStores,
    componentDidMount: function componentDidMount() {
        var $conversation = $(ReactDOM.findDOMNode(this.refs.conversation));

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }

        consoleStore.addChangeListener(this._onChange);
    },
    componentDidUpdate: function componentDidUpdate() {
        var $conversation = $(ReactDOM.findDOMNode(this.refs.conversation));

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    componentWillUnmount: function componentWillUnmount() {
        consoleStore.removeChangeListener(this._onChange);
    },
    _onChange: function _onChange() {
        this.setState(getStateFromStores());
    },
    render: function render() {
        return React.createElement(
            'div',
            { ref: 'conversation', className: 'conversation' },
            this.state.exchanges.map(function (exchange, index) {
                return React.createElement(Exchange, { key: index, exchange: exchange });
            })
        );
    }
});

function getStateFromStores() {
    return { exchanges: consoleStore.getExchanges() };
}

module.exports = Conversation;

},{"../stores/console-store":58,"./exchange":29,"jquery":undefined,"react":undefined,"react-dom":undefined}],25:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');
var platformChartStore = require('../stores/platform-chart-store');

var PlatformChart = require('./platform-chart');

var Dashboard = React.createClass({
    displayName: 'Dashboard',

    getInitialState: function getInitialState() {
        var state = getStateFromStores();
        return state;
    },
    componentDidMount: function componentDidMount() {
        platformChartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        platformChartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function _onStoreChange() {
        this.setState(getStateFromStores());
    },
    render: function render() {

        var pinnedCharts = this.state.platformCharts;

        var platformCharts = [];

        pinnedCharts.forEach(function (pinnedChart) {
            if (pinnedChart.data.length > 0) {
                var platformChart = React.createElement(PlatformChart, { key: pinnedChart.chartKey, chart: pinnedChart, chartKey: pinnedChart.chartKey, hideControls: true });
                platformCharts.push(platformChart);
            }
        });

        if (pinnedCharts.length === 0) {
            platformCharts = React.createElement(
                'p',
                { className: 'empty-help' },
                'Pin a chart to have it appear on the dashboard'
            );
        }

        return React.createElement(
            'div',
            { className: 'view' },
            React.createElement(
                'h2',
                null,
                'Dashboard'
            ),
            platformCharts
        );
    }
});

function getStateFromStores() {
    return {
        platformCharts: platformChartStore.getPinnedCharts()
    };
}

module.exports = Dashboard;

},{"../stores/platform-chart-store":62,"./platform-chart":36,"react":undefined,"react-router":undefined}],26:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var RegisterPlatformForm = React.createClass({
    displayName: 'RegisterPlatformForm',

    getInitialState: function getInitialState() {
        return {};
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function _onSubmit(e) {
        e.preventDefault();
        platformManagerActionCreators.deregisterPlatform(this.props.platform);
    },
    render: function render() {
        return React.createElement(
            'form',
            { className: 'register-platform-form', onSubmit: this._onSubmit },
            React.createElement(
                'h1',
                null,
                'Deregister platform'
            ),
            React.createElement(
                'p',
                null,
                'Deregister ',
                React.createElement(
                    'strong',
                    null,
                    this.props.platform.name
                ),
                '?'
            ),
            React.createElement(
                'div',
                { className: 'form__actions' },
                React.createElement(
                    'button',
                    {
                        className: 'button button--secondary',
                        type: 'button',
                        onClick: this._onCancelClick,
                        autoFocus: true
                    },
                    'Cancel'
                ),
                React.createElement(
                    'button',
                    { className: 'button' },
                    'Deregister'
                )
            )
        );
    }
});

module.exports = RegisterPlatformForm;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-manager-action-creators":8,"react":undefined}],27:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

var _configureRegistry = require('./configure-registry');

var _configureRegistry2 = _interopRequireDefault(_configureRegistry);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var ConfirmForm = require('./confirm-form');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');

var CsvParse = require('babyparse');

var devicesWs, devicesWebsocket;
var pointsWs, pointsWebsocket;

var DevicesFound = function (_BaseComponent) {
    _inherits(DevicesFound, _BaseComponent);

    function DevicesFound(props) {
        _classCallCheck(this, DevicesFound);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(DevicesFound).call(this, props));

        _this._bind('_onStoresChange', '_uploadRegistryFile', '_setUpDevicesSocket', '_setUpPointsSocket', '_focusOnDevice');

        _this.state = {};
        return _this;
    }

    _createClass(DevicesFound, [{
        key: 'componentDidMount',
        value: function componentDidMount() {
            // devicesStore.addChangeListener(this._onStoresChange);
            this._setUpDevicesSocket();
        }
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {
            // devicesStore.removeChangeListener(this._onStoresChange);
        }
    }, {
        key: 'componentWillReceiveProps',
        value: function componentWillReceiveProps(nextProps) {
            if (this.props.canceled !== nextProps.canceled) {
                if (nextProps.canceled) {
                    if (typeof devicesWs !== "undefined" && devicesWs !== null) {
                        devicesWs.close();
                        devicesWs = null;
                    }
                } else {
                    this._setUpDevicesSocket();
                }
            }

            if (nextProps.devices !== this.props.devices) {
                this.props.devicesloaded(nextProps.devices.length > 0);
            }
        }
    }, {
        key: '_setUpDevicesSocket',
        value: function _setUpDevicesSocket() {

            if (typeof pointsWs !== "undefined" && pointsWs !== null) {
                pointsWs.close();
                pointsWs = null;
            }

            devicesWebsocket = "ws://" + window.location.host + "/vc/ws/iam";
            if (window.WebSocket) {
                devicesWs = new WebSocket(devicesWebsocket);
            } else if (window.MozWebSocket) {
                devicesWs = MozWebSocket(devicesWebsocket);
            }

            devicesWs.onmessage = function (evt) {
                devicesActionCreators.deviceDetected(evt.data, this.props.platform, this.props.bacnet);

                var warnings = devicesStore.getWarnings();

                if (!objectIsEmpty(warnings)) {
                    for (var key in warnings) {
                        var values = warnings[key].items.join(", ");

                        statusIndicatorActionCreators.openStatusIndicator("error", warnings[key].message + "ID: " + values, values, "left");
                    }
                }
            }.bind(this);
        }
    }, {
        key: '_setUpPointsSocket',
        value: function _setUpPointsSocket() {

            if (typeof devicesWs !== "undefined" && devicesWs !== null) {
                devicesWs.close();
                devicesWs = null;
            }

            pointsWebsocket = "ws://" + window.location.host + "/vc/ws/configure";
            if (window.WebSocket) {
                pointsWs = new WebSocket(pointsWebsocket);
            } else if (window.MozWebSocket) {
                pointsWs = MozWebSocket(pointsWebsocket);
            }

            pointsWs.onmessage = function (evt) {
                devicesActionCreators.pointReceived(evt.data, this.props.platform, this.props.bacnet);

                var warnings = devicesStore.getWarnings();

                if (!objectIsEmpty(warnings)) {
                    for (var key in warnings) {
                        var values = warnings[key].items.join(", ");

                        statusIndicatorActionCreators.openStatusIndicator("error", warnings[key].message + "ID: " + values, values, "left");
                    }
                }
            }.bind(this);
        }
    }, {
        key: '_onStoresChange',
        value: function _onStoresChange() {
            // var devices = devicesStore.getDevices(this.props.platform, this.props.bacnet); 
        }
    }, {
        key: '_configureDevice',
        value: function _configureDevice(device) {

            devicesActionCreators.focusOnDevice(device.id, device.address);

            device.showPoints = !device.showPoints;

            // Don't set up the socket again if we've already set it up once.
            // So before setting device.configuring to true, first check
            // if we're going to show points but haven't started configuring yet.
            // If so, set up the socket and set configuring to true.
            if (device.showPoints && !device.configuring) {
                this._setUpPointsSocket();
                device.configuring = true;
                devicesActionCreators.configureDevice(device);
            } else {
                devicesActionCreators.toggleShowPoints(device);
            }
        }
    }, {
        key: '_focusOnDevice',
        value: function _focusOnDevice(evt) {
            var deviceId = evt.target.dataset.id;
            var address = evt.target.dataset.address;
            devicesActionCreators.focusOnDevice(deviceId, address);
        }
    }, {
        key: '_uploadRegistryFile',
        value: function _uploadRegistryFile(evt) {

            var csvFile = evt.target.files[0];

            if (!csvFile) {
                return;
            }

            var deviceId = evt.target.dataset.id;
            var deviceAddress = evt.target.dataset.address;

            var device = this.props.devices.find(function (device) {
                return device.id === deviceId && device.address === deviceAddress;
            });

            if (device) {
                var fileName = evt.target.value;

                var reader = new FileReader();

                reader.onload = function (e) {

                    var contents = e.target.result;

                    var results = parseCsvFile(contents);

                    if (results.errors.length) {
                        var errorMsg = "The file wasn't in a valid CSV format.";

                        modalActionCreators.openModal(_react2.default.createElement(ConfirmForm, {
                            promptTitle: 'Error Reading File',
                            promptText: errorMsg,
                            cancelText: 'OK'
                        }));
                    } else {
                        if (results.warnings.length) {
                            var warningMsg = results.warnings.map(function (warning) {
                                return warning.message;
                            });

                            modalActionCreators.openModal(_react2.default.createElement(ConfirmForm, {
                                promptTitle: 'File Upload Notes',
                                promptText: warningMsg,
                                cancelText: 'OK'
                            }));
                        }

                        if (!results.meta.aborted) {
                            // this.setState({registry_config: fileName});       
                            devicesActionCreators.loadRegistry(device.id, device.address, results.data, fileName);
                        }
                    }
                }.bind(this);

                reader.readAsText(csvFile);
            } else {
                alert("Couldn't find device by ID " + deviceId + " and address " + deviceAddress);
            }
        }
    }, {
        key: 'render',
        value: function render() {

            var devicesContainer;
            if (this.props.devices.length) {
                var devices = this.props.devices.map(function (device) {

                    var deviceId = device.id;
                    var deviceAddress = device.address;

                    var tds = device.items.map(function (d, i) {
                        return _react2.default.createElement(
                            'td',
                            {
                                key: d.key + "-" + i,
                                className: 'plain',
                                'data-id': deviceId,
                                'data-address': deviceAddress,
                                onClick: this._focusOnDevice },
                            d.value
                        );
                    }, this);

                    return _react2.default.createElement(
                        'tr',
                        { key: deviceId + deviceAddress },
                        _react2.default.createElement(
                            'td',
                            { key: "config-arrow-" + deviceId + deviceAddress, className: 'plain' },
                            _react2.default.createElement(
                                'div',
                                { className: device.showPoints ? "configure-arrow rotateConfigure" : "configure-arrow",
                                    onClick: this._configureDevice.bind(this, device) },
                                '▶'
                            )
                        ),
                        tds,
                        _react2.default.createElement(
                            'td',
                            { key: "file-upload-" + deviceId + deviceAddress, className: 'plain' },
                            _react2.default.createElement(
                                'div',
                                { className: 'fileButton' },
                                _react2.default.createElement(
                                    'div',
                                    null,
                                    _react2.default.createElement('i', { className: 'fa fa-file' })
                                ),
                                _react2.default.createElement('input', {
                                    className: 'uploadButton',
                                    type: 'file',
                                    'data-id': deviceId,
                                    'data-address': deviceAddress,
                                    onChange: this._uploadRegistryFile,
                                    onFocus: this._focusOnDevice })
                            )
                        )
                    );
                }, this);

                var ths = this.props.devices[0].items.map(function (d, i) {
                    return _react2.default.createElement(
                        'th',
                        { key: d.key + "-" + i + "-th", className: 'plain' },
                        d.label
                    );
                });

                if (devices.length) {
                    for (var i = devices.length - 1; i >= 0; i--) {
                        var device = this.props.devices.find(function (dev) {
                            return dev.id + dev.address === devices[i].key;
                        });

                        if (device) {

                            var configureRegistry = _react2.default.createElement(
                                'tr',
                                { key: "config-" + device.id + device.address },
                                _react2.default.createElement(
                                    'td',
                                    { colSpan: 7 },
                                    _react2.default.createElement(_configureRegistry2.default, { device: device })
                                )
                            );

                            devices.splice(i + 1, 0, configureRegistry);
                        }
                    }
                }

                devicesContainer = _react2.default.createElement(
                    'table',
                    null,
                    _react2.default.createElement(
                        'tbody',
                        null,
                        _react2.default.createElement(
                            'tr',
                            null,
                            _react2.default.createElement('th', { className: 'plain' }),
                            ths,
                            _react2.default.createElement('th', { className: 'plain' })
                        ),
                        devices
                    )
                );
            } else {
                if (this.props.canceled) {
                    devicesContainer = _react2.default.createElement(
                        'div',
                        { className: 'no-devices' },
                        'No devices were detected.'
                    );
                } else {
                    devicesContainer = _react2.default.createElement(
                        'div',
                        { className: 'no-devices' },
                        'Searching for devices ...'
                    );
                }
            }

            return _react2.default.createElement(
                'div',
                { className: 'devicesFoundContainer' },
                _react2.default.createElement(
                    'div',
                    { className: 'devicesFoundBox' },
                    devicesContainer
                )
            );
        }
    }]);

    return DevicesFound;
}(_baseComponent2.default);

;

var parseCsvFile = function parseCsvFile(contents) {

    var results = CsvParse.parse(contents);

    var registryValues = [];

    var header = [];

    var data = results.data;

    results.warnings = [];

    if (data.length) {
        header = data.slice(0, 1);
    }

    var template = [];

    if (header[0].length) {
        header[0].forEach(function (column) {
            template.push({ "key": column.replace(/ /g, "_"), "value": null, "label": column });
        });

        var templateLength = template.length;

        if (data.length > 1) {
            var rows = data.slice(1);

            var rowsCount = rows.length;

            rows.forEach(function (r, num) {

                if (r.length) {
                    if (r.length !== templateLength) {
                        if (num === rowsCount - 1 && (r.length === 0 || r.length === 1 && r[0] === "")) {
                            // Suppress the warning message if the out-of-sync row is the last one and it has no elements
                            // or all it has is an empty point name -- which can happen naturally when reading the csv file
                        } else {
                            results.warnings.push({ message: "Row " + num + " was omitted for having the wrong number of columns." });
                        }
                    } else {
                        if (r.length === templateLength) // Have to check again, to keep from adding the empty point name
                            {
                                // in the last row
                                var newTemplate = JSON.parse(JSON.stringify(template));

                                var newRow = [];

                                r.forEach(function (value, i) {
                                    newTemplate[i].value = value;

                                    newRow.push(newTemplate[i]);
                                });

                                registryValues.push(newRow);
                            }
                    }
                }
            });
        } else {
            registryValues = template;
        }
    }

    results.data = registryValues;

    return results;
};

function objectIsEmpty(obj) {
    return Object.keys(obj).length === 0;
}

exports.default = DevicesFound;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"../action-creators/status-indicator-action-creators":10,"../stores/devices-store":60,"./base-component":12,"./configure-registry":17,"./confirm-form":18,"babyparse":undefined,"react":undefined}],28:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

var EditPointForm = function (_BaseComponent) {
    _inherits(EditPointForm, _BaseComponent);

    function EditPointForm(props) {
        _classCallCheck(this, EditPointForm);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(EditPointForm).call(this, props));

        _this._bind("_toggleKeyProp", "_updateAttribute", "_onSubmit");

        _this.state = {};
        _this.state.attributes = _this.props.attributes;
        return _this;
    }

    _createClass(EditPointForm, [{
        key: '_toggleKeyProp',
        value: function _toggleKeyProp(itemKey) {

            var itemToUpdate = this.state.attributes.find(function (item) {
                return item.key === itemKey;
            });

            if (itemToUpdate) {
                itemToUpdate.keyProp = !itemToUpdate.keyProp;
            }

            this.setState({ attributes: this.state.attributes });
        }
    }, {
        key: '_updateAttribute',
        value: function _updateAttribute(e) {
            var itemKey = e.target.dataset.key;

            var itemToUpdate = this.state.attributes.find(function (item) {
                return item.key === itemKey;
            });

            if (itemToUpdate) {
                itemToUpdate.value = e.target.value;
            }

            this.setState({ attributes: this.state.attributes });
        }
    }, {
        key: '_onCancelClick',
        value: function _onCancelClick(e) {
            modalActionCreators.closeModal();
        }
    }, {
        key: '_onSubmit',
        value: function _onSubmit(e) {
            e.preventDefault();
            devicesActionCreators.updateRegistry(this.props.deviceId, this.props.deviceAddress, this.props.selectedPoints, this.state.attributes);
            modalActionCreators.closeModal();
        }
    }, {
        key: 'render',
        value: function render() {

            var attributes = this.state.attributes.map(function (item, index) {

                var attributeInput = item.editable ? _react2.default.createElement('input', { type: 'text',
                    'data-key': item.key,
                    value: item.value,
                    onChange: this._updateAttribute }) : _react2.default.createElement(
                    'label',
                    null,
                    item.value
                );

                var itemRow = _react2.default.createElement(
                    'tr',
                    { key: item.key + "-" + index },
                    _react2.default.createElement(
                        'td',
                        null,
                        item.label
                    ),
                    _react2.default.createElement(
                        'td',
                        null,
                        attributeInput
                    ),
                    _react2.default.createElement(
                        'td',
                        { className: 'centerContent' },
                        _react2.default.createElement('input', { type: 'checkbox',
                            checked: item.keyProp,
                            onChange: this._toggleKeyProp.bind(this, item.key) })
                    )
                );

                return itemRow;
            }, this);

            return _react2.default.createElement(
                'form',
                { className: 'edit-registry-form', onSubmit: this._onSubmit },
                _react2.default.createElement(
                    'h1',
                    null,
                    attributes.get(0).value
                ),
                _react2.default.createElement(
                    'table',
                    null,
                    _react2.default.createElement(
                        'thead',
                        null,
                        _react2.default.createElement(
                            'tr',
                            null,
                            _react2.default.createElement(
                                'th',
                                null,
                                'Point'
                            ),
                            _react2.default.createElement(
                                'th',
                                null,
                                'Value'
                            ),
                            _react2.default.createElement(
                                'th',
                                null,
                                'Show in Table'
                            )
                        )
                    ),
                    _react2.default.createElement(
                        'tbody',
                        null,
                        attributes
                    )
                ),
                _react2.default.createElement(
                    'div',
                    { className: 'form__actions' },
                    _react2.default.createElement(
                        'button',
                        {
                            className: 'button button--secondary',
                            type: 'button',
                            onClick: this._onCancelClick
                        },
                        'Cancel'
                    ),
                    _react2.default.createElement(
                        'button',
                        { className: 'button' },
                        'Apply'
                    )
                )
            );
        }
    }]);

    return EditPointForm;
}(_baseComponent2.default);

;

exports.default = EditPointForm;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"./base-component":12,"react":undefined}],29:[function(require,module,exports){
'use strict';

var React = require('react');

var Exchange = React.createClass({
    displayName: 'Exchange',

    _formatTime: function _formatTime(time) {
        var d = new Date();

        d.setTime(time);

        return d.toLocaleString();
    },
    _formatMessage: function _formatMessage(message) {
        return JSON.stringify(message, null, '    ');
    },
    render: function render() {
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

        return React.createElement(
            'div',
            { className: 'exchange' },
            React.createElement(
                'div',
                { className: 'request' },
                React.createElement(
                    'div',
                    { className: 'time' },
                    this._formatTime(exchange.initiated)
                ),
                React.createElement(
                    'pre',
                    null,
                    this._formatMessage(exchange.request)
                )
            ),
            React.createElement(
                'div',
                { className: classes.join(' ') },
                exchange.completed && React.createElement(
                    'div',
                    { className: 'time' },
                    this._formatTime(exchange.completed)
                ),
                React.createElement(
                    'pre',
                    null,
                    responseText
                )
            )
        );
    }
});

module.exports = Exchange;

},{"react":undefined}],30:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LoginForm = React.createClass({
    displayName: 'LoginForm',

    getInitialState: function getInitialState() {
        var state = {};

        return state;
    },
    _onUsernameChange: function _onUsernameChange(e) {
        this.setState({
            username: e.target.value,
            error: null
        });
    },
    _onPasswordChange: function _onPasswordChange(e) {
        this.setState({
            password: e.target.value,
            error: null
        });
    },
    _onSubmit: function _onSubmit(e) {
        e.preventDefault();
        platformManagerActionCreators.requestAuthorization(this.state.username, this.state.password);
    },
    render: function render() {
        return React.createElement(
            'form',
            { className: 'login-form', onSubmit: this._onSubmit },
            React.createElement('input', {
                className: 'login-form__field',
                type: 'text',
                placeholder: 'Username',
                autoFocus: true,
                onChange: this._onUsernameChange
            }),
            React.createElement('input', {
                className: 'login-form__field',
                type: 'password',
                placeholder: 'Password',
                onChange: this._onPasswordChange
            }),
            React.createElement('input', {
                className: 'button login-form__submit',
                type: 'submit',
                value: 'Log in',
                disabled: !this.state.username || !this.state.password
            })
        );
    }
});

module.exports = LoginForm;

},{"../action-creators/platform-manager-action-creators":8,"react":undefined,"react-router":undefined}],31:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var Modal = React.createClass({
	displayName: 'Modal',

	_onClick: function _onClick(e) {
		if (e.target === e.currentTarget) {
			modalActionCreators.closeModal();
		}
	},
	render: function render() {
		return React.createElement(
			'div',
			{ className: 'modal__overlay', onClick: this._onClick },
			React.createElement(
				'div',
				{ className: 'modal__dialog' },
				this.props.children
			)
		);
	}
});

module.exports = Modal;

},{"../action-creators/modal-action-creators":5,"react":undefined}],32:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var authorizationStore = require('../stores/authorization-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var Navigation = React.createClass({
    displayName: 'Navigation',

    getInitialState: getStateFromStores,
    componentDidMount: function componentDidMount() {
        authorizationStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        authorizationStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function _onStoreChange() {
        this.setState(getStateFromStores());
    },
    _onLogOutClick: function _onLogOutClick() {
        platformManagerActionCreators.clearAuthorization();
    },
    render: function render() {
        var navItems;

        if (this.state.loggedIn) {
            navItems = ['Dashboard', 'Platforms', 'Charts'].map(function (navItem) {
                var route = navItem.toLowerCase();

                return React.createElement(
                    Router.Link,
                    {
                        key: route,
                        to: route,
                        className: 'navigation__item',
                        activeClassName: 'navigation__item--active'
                    },
                    navItem
                );
            });

            navItems.push(React.createElement(
                'a',
                {
                    key: 'logout',
                    className: 'navigation__item',
                    tabIndex: '0',
                    onClick: this._onLogOutClick
                },
                'Log out'
            ));
        }

        return React.createElement(
            'nav',
            { className: 'navigation' },
            React.createElement(
                'h1',
                { className: 'logo' },
                React.createElement(
                    'span',
                    { className: 'logo__name' },
                    'VOLTTRON'
                ),
                React.createElement(
                    'span',
                    { className: 'logo__tm' },
                    '™'
                ),
                React.createElement(
                    'span',
                    { className: 'logo__central' },
                    ' Central'
                ),
                React.createElement(
                    'span',
                    { className: 'logo__beta' },
                    'BETA'
                ),
                React.createElement(
                    'span',
                    { className: 'logo__funding' },
                    'Funded by DOE EERE BTO'
                )
            ),
            navItems
        );
    }
});

function getStateFromStores() {
    return {
        loggedIn: !!authorizationStore.getAuthorization()
    };
}

module.exports = Navigation;

},{"../action-creators/platform-manager-action-creators":8,"../action-creators/platforms-panel-action-creators":9,"../stores/authorization-store":57,"react":undefined,"react-router":undefined}],33:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var chartStore = require('../stores/platform-chart-store');
var ComboBox = require('./combo-box');

var NewChartForm = React.createClass({
    displayName: 'NewChartForm',

    getInitialState: function getInitialState() {
        var state = {};

        state.refreshInterval = 15000;

        state.topics = chartStore.getChartTopics();

        state.selectedTopic = "";

        return state;
    },
    componentDidMount: function componentDidMount() {
        chartStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        chartStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function _onStoresChange() {
        this.setState({ topics: chartStore.getChartTopics() });
    },
    _onPropChange: function _onPropChange(e) {
        var state = {};

        for (key in this.state) {
            state[key] = this.state[key];
        }

        var key = e.target.id;

        switch (e.target.type) {
            case 'checkbox':
                state[key] = e.target.checked;
                break;
            case 'number':
                state[key] = parseFloat(e.target.value);
                break;
            default:
                state[key] = e.target.value;
        }

        this.setState(state);
    },
    _onTopicChange: function _onTopicChange(value) {
        this.setState({ selectedTopic: value });
    },
    _onCancelClick: function _onCancelClick() {
        modalActionCreators.closeModal();
    },
    _onSubmit: function _onSubmit(e) {

        e.preventDefault();

        var selectedTopic = this.state.topics.find(function (topic) {
            return topic.value === this.state.selectedTopic;
        }, this);

        if (selectedTopic) {
            selectedTopic.uuid = selectedTopic.value;
            selectedTopic.topic = selectedTopic.value;
            selectedTopic.pinned = this.state.pin ? true : false;
            selectedTopic.refreshInterval = this.state.refreshInterval;
            selectedTopic.chartType = this.state.chartType;
            selectedTopic.path = platformsPanelItemsStore.findTopicInTree(selectedTopic.topic);
            selectedTopic.max = this.state.max;
            selectedTopic.min = this.state.min;

            if (selectedTopic.path && selectedTopic.path.length > 1) {
                selectedTopic.parentUuid = selectedTopic.path[selectedTopic.path.length - 2];
            }
        }

        var notifyRouter = false;

        platformChartActionCreators.addToChart(selectedTopic, notifyRouter);

        if (selectedTopic.path) {
            platformsPanelActionCreators.checkItem(selectedTopic.path, true);
        }

        modalActionCreators.closeModal();
    },
    render: function render() {
        var topicsSelector;

        if (this.state.topics.length) {
            topicsSelector = React.createElement(ComboBox, { items: this.state.topics, itemskey: 'key', itemsvalue: 'value', itemslabel: 'label', onselect: this._onTopicChange });
        } else {
            topicsSelector = React.createElement(
                'div',
                null,
                'Loading topics ...'
            );
        }

        return React.createElement(
            'form',
            { className: 'edit-chart-form', onSubmit: this._onSubmit },
            React.createElement(
                'h1',
                null,
                'Add Chart'
            ),
            this.state.error && React.createElement(
                'div',
                { className: 'error' },
                this.state.error.message
            ),
            React.createElement(
                'div',
                { className: 'form__control-group' },
                React.createElement(
                    'label',
                    { htmlFor: 'topic' },
                    'Topics'
                ),
                topicsSelector
            ),
            React.createElement(
                'div',
                { className: 'form__control-group' },
                React.createElement(
                    'label',
                    null,
                    'Dashboard'
                ),
                React.createElement('input', {
                    className: 'form__control form__control--inline',
                    type: 'checkbox',
                    id: 'pin',
                    onChange: this._onPropChange,
                    checked: this.state.pin
                }),
                ' ',
                React.createElement(
                    'label',
                    { htmlFor: 'pin' },
                    'Pin to dashboard'
                )
            ),
            React.createElement(
                'div',
                { className: 'form__control-group' },
                React.createElement(
                    'label',
                    { htmlFor: 'refreshInterval' },
                    'Refresh interval (ms)'
                ),
                React.createElement('input', {
                    className: 'form__control form__control--inline',
                    type: 'number',
                    id: 'refreshInterval',
                    onChange: this._onPropChange,
                    value: this.state.refreshInterval,
                    min: '250',
                    step: '1',
                    placeholder: 'disabled'
                }),
                React.createElement(
                    'span',
                    { className: 'form__control-help' },
                    'Omit to disable'
                )
            ),
            React.createElement(
                'div',
                { className: 'form__control-group' },
                React.createElement(
                    'label',
                    { htmlFor: 'chartType' },
                    'Chart type'
                ),
                React.createElement(
                    'select',
                    {
                        id: 'chartType',
                        onChange: this._onPropChange,
                        value: this.state.chartType,
                        autoFocus: true,
                        required: true
                    },
                    React.createElement(
                        'option',
                        { value: '' },
                        '-- Select type --'
                    ),
                    React.createElement(
                        'option',
                        { value: 'line' },
                        'Line'
                    ),
                    React.createElement(
                        'option',
                        { value: 'lineWithFocus' },
                        'Line with View Finder'
                    ),
                    React.createElement(
                        'option',
                        { value: 'stackedArea' },
                        'Stacked Area'
                    ),
                    React.createElement(
                        'option',
                        { value: 'cumulativeLine' },
                        'Cumulative Line'
                    )
                )
            ),
            React.createElement(
                'div',
                { className: 'form__control-group' },
                React.createElement(
                    'label',
                    null,
                    'Y-axis range'
                ),
                React.createElement(
                    'label',
                    { htmlFor: 'min' },
                    'Min:'
                ),
                ' ',
                React.createElement('input', {
                    className: 'form__control form__control--inline',
                    type: 'number',
                    id: 'min',
                    onChange: this._onPropChange,
                    value: this.state.min,
                    placeholder: 'auto'
                }),
                ' ',
                React.createElement(
                    'label',
                    { htmlFor: 'max' },
                    'Max:'
                ),
                ' ',
                React.createElement('input', {
                    className: 'form__control form__control--inline',
                    type: 'number',
                    id: 'max',
                    onChange: this._onPropChange,
                    value: this.state.max,
                    placeholder: 'auto'
                }),
                React.createElement('br', null),
                React.createElement(
                    'span',
                    { className: 'form__control-help' },
                    'Omit either to determine from data'
                )
            ),
            React.createElement(
                'div',
                { className: 'form__actions' },
                React.createElement(
                    'button',
                    {
                        className: 'button button--secondary',
                        type: 'button',
                        onClick: this._onCancelClick
                    },
                    'Cancel'
                ),
                React.createElement(
                    'button',
                    {
                        className: 'button',
                        disabled: !this.state.selectedTopic || !this.state.chartType
                    },
                    'Load Chart'
                )
            )
        );
    }
});

module.exports = NewChartForm;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-action-creators":6,"../action-creators/platform-chart-action-creators":7,"../action-creators/platforms-panel-action-creators":9,"../stores/platform-chart-store":62,"../stores/platforms-panel-items-store":63,"./combo-box":13,"react":undefined}],34:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

var NewColumnForm = function (_BaseComponent) {
    _inherits(NewColumnForm, _BaseComponent);

    function NewColumnForm(props) {
        _classCallCheck(this, NewColumnForm);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(NewColumnForm).call(this, props));

        _this._bind("_onNameChange", "_onCancelClick", "_onSubmit");

        _this.state = {
            columnName: "",
            warningMessage: ""
        };
        return _this;
    }

    _createClass(NewColumnForm, [{
        key: '_onNameChange',
        value: function _onNameChange(evt) {

            if (this.state.warningMessage !== "") {
                this.setState({ warningMessage: "" });
            }

            var newName = evt.target.value;
            this.setState({ columnName: newName });
        }
    }, {
        key: '_onCancelClick',
        value: function _onCancelClick(e) {
            modalActionCreators.closeModal();
        }
    }, {
        key: '_onSubmit',
        value: function _onSubmit(e) {
            e.preventDefault();

            var alreadyInList = this.props.columnNames.find(function (name) {
                return name === this.state.columnName.toLowerCase().replace(/ /g, "_");
            }, this);

            if (typeof alreadyInList !== "undefined") {
                this.setState({ warningMessage: "Column names must be unique." });
            } else {
                this.props.onConfirm(this.state.columnName, this.props.column);
                modalActionCreators.closeModal();
            }
        }
    }, {
        key: 'render',
        value: function render() {

            var warningMessage;

            if (this.state.warningMessage) {
                var warningStyle = {
                    color: "red",
                    textAlign: "center"
                };

                warningMessage = _react2.default.createElement(
                    'div',
                    { style: warningStyle },
                    this.state.warningMessage
                );
            }

            return _react2.default.createElement(
                'form',
                { className: 'new-registry-column-form', onSubmit: this._onSubmit },
                _react2.default.createElement(
                    'div',
                    { className: 'centerContent' },
                    _react2.default.createElement(
                        'h3',
                        null,
                        'New Column'
                    )
                ),
                _react2.default.createElement(
                    'div',
                    { className: 'newColumnContainer' },
                    _react2.default.createElement(
                        'div',
                        null,
                        'Column Name: '
                    ),
                    _react2.default.createElement(
                        'div',
                        null,
                        _react2.default.createElement('input', {
                            type: 'text',
                            value: this.state.columnName,
                            onChange: this._onNameChange })
                    )
                ),
                warningMessage,
                _react2.default.createElement(
                    'div',
                    { className: 'form__actions' },
                    _react2.default.createElement(
                        'button',
                        {
                            className: 'button button--secondary',
                            type: 'button',
                            onClick: this._onCancelClick
                        },
                        'Cancel'
                    ),
                    _react2.default.createElement(
                        'button',
                        {
                            disabled: this.state.warningMessage || !this.state.columnName,
                            className: 'button' },
                        'Add Column'
                    )
                )
            );
        }
    }]);

    return NewColumnForm;
}(_baseComponent2.default);

;

exports.default = NewColumnForm;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"./base-component":12,"react":undefined}],35:[function(require,module,exports){
'use strict';

var React = require('react');

var PageNotFound = React.createClass({
    displayName: 'PageNotFound',

    render: function render() {
        return React.createElement(
            'div',
            { className: 'view' },
            React.createElement(
                'h2',
                null,
                'Page not found'
            )
        );
    }
});

module.exports = PageNotFound;

},{"react":undefined}],36:[function(require,module,exports){
'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');
var moment = require('moment');
var OutsideClick = require('react-click-outside');

var chartStore = require('../stores/platform-chart-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var ConfirmForm = require('./confirm-form');
var ControlButton = require('./control-button');

var PlatformChart = React.createClass({
    displayName: 'PlatformChart',

    getInitialState: function getInitialState() {
        var state = {};

        state.refreshInterval = this.props.chart.refreshInterval;
        state.pinned = this.props.chart.pinned;

        state.refreshing = false;

        return state;
    },
    componentDidMount: function componentDidMount() {
        this._refreshChartTimeout = setTimeout(this._refreshChart, 0);
        platformChartStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        clearTimeout(this._refreshChartTimeout);
        platformChartStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function _onStoresChange() {

        this.setState({ refreshing: false });

        if (this.props.chart.data.length > 0) {

            var refreshInterval = platformChartStore.getRefreshRate(this.props.chart.data[0].name);

            if (refreshInterval !== this.state.refreshInterval) {
                this.setState({ refreshInterval: refreshInterval });

                clearTimeout(this._refreshChartTimeout);
                this._refreshChartTimeout = setTimeout(this._refreshChart, refreshInterval);
            }
        }
    },
    _refreshChart: function _refreshChart() {

        if (this.props.hasOwnProperty("chart")) {
            this.setState({ refreshing: true });

            platformChartActionCreators.refreshChart(this.props.chart.series);

            if (this.state.refreshInterval) {
                this._refreshChartTimeout = setTimeout(this._refreshChart, this.state.refreshInterval);
            }
        }
    },
    _removeChart: function _removeChart() {

        var deleteChart = function deleteChart() {
            modalActionCreators.closeModal();

            this.props.chart.series.forEach(function (series) {
                if (series.hasOwnProperty("path")) {
                    platformsPanelActionCreators.checkItem(series.path, false);
                }
            });

            platformChartActionCreators.removeChart(this.props.chartKey);
            platformActionCreators.saveCharts();
        };

        modalActionCreators.openModal(React.createElement(ConfirmForm, {
            promptTitle: 'Delete chart',
            preText: 'Remove ',
            promptText: this.props.chartKey,
            postText: ' chart from here and from Dashboard?',
            confirmText: 'Delete',
            onConfirm: deleteChart.bind(this) }));
    },
    render: function render() {
        var chartData = this.props.chart;
        var platformChart;

        var removeButton;

        if (!this.props.hideControls) {
            removeButton = React.createElement(
                'div',
                { className: 'remove-chart',
                    onClick: this._removeChart },
                React.createElement('i', { className: 'fa fa-remove' })
            );
        }

        var refreshingIcon;

        if (this.state.refreshing) {
            refreshingIcon = React.createElement(
                'span',
                { className: 'refreshIcon' },
                React.createElement('i', { className: 'fa fa-refresh fa-spin fa-fw' })
            );
        }

        var containerStyle = {
            width: "100%",
            textAlign: "center"
        };

        var innerStyle = {
            width: (chartData.data[0].name.length > 10 ? chartData.data[0].name.length * 10 : 100) + "px",
            marginLeft: "auto",
            marginRight: "auto"
        };

        if (chartData) {
            if (chartData.data.length > 0) {
                platformChart = React.createElement(
                    'div',
                    { className: 'platform-chart with-3d-shadow with-transitions absolute_anchor' },
                    React.createElement(
                        'div',
                        { style: containerStyle },
                        React.createElement(
                            'div',
                            { className: 'absolute_anchor', style: innerStyle },
                            React.createElement(
                                'label',
                                { className: 'chart-title' },
                                chartData.data[0].name
                            ),
                            refreshingIcon
                        )
                    ),
                    removeButton,
                    React.createElement(
                        'div',
                        null,
                        React.createElement(
                            'div',
                            { className: 'viz' },
                            chartData.data.length != 0 ? React.createElement(GraphLineChart, {
                                key: this.props.chartKey,
                                data: chartData.data,
                                name: this.props.chartKey,
                                hideControls: this.props.hideControls,
                                refreshInterval: this.props.chart.refreshInterval,
                                max: chartData.max,
                                min: chartData.min,
                                pinned: this.props.chart.pinned,
                                chartType: this.props.chart.type }) : null
                        ),
                        React.createElement('br', null)
                    )
                );
            }
        }

        return React.createElement(
            'div',
            null,
            platformChart
        );
    }
});

var GraphLineChart = OutsideClick(React.createClass({
    displayName: 'GraphLineChart',

    getInitialState: function getInitialState() {

        var pattern = /[!@#$%^&*()+\-=\[\]{};':"\\|, .<>\/?]/g;

        var state = {};

        state.chartName = this.props.name.replace(" / ", "_") + '_chart';
        state.chartName = state.chartName.replace(pattern, "_");
        state.lineChart = null;
        state.pinned = this.props.pinned;
        state.chartType = this.props.chartType;
        state.showTaptip = false;
        state.taptipX = 0;
        state.taptipY = 0;
        state.min = this.props.min ? this.props.min : d3.min(this.props.data, function (d) {
            return d["1"];
        });
        state.max = this.props.max ? this.props.max : d3.max(this.props.data, function (d) {
            return d["1"];
        });

        return state;
    },
    componentDidMount: function componentDidMount() {
        platformChartStore.addChangeListener(this._onStoresChange);
        var lineChart = this._drawLineChart(this.state.chartName, this.state.chartType, this._lineData(this._getNested(this.props.data)), this.state.min, this.state.max);
        this.setState({ lineChart: lineChart });

        this.chart = ReactDOM.findDOMNode(this.refs[this.state.chartName]);
    },
    componentWillUnmount: function componentWillUnmount() {
        platformChartStore.removeChangeListener(this._onStoresChange);
        if (this.lineChart) {
            delete this.lineChart;
        }
    },
    componentDidUpdate: function componentDidUpdate() {
        if (this.state.lineChart) {
            this._updateLineChart(this.state.lineChart, this.state.chartName, this._lineData(this._getNested(this.props.data)));
        }
    },
    _onStoresChange: function _onStoresChange() {
        this.setState({ pinned: platformChartStore.getPinned(this.props.name) });
        this.setState({ chartType: platformChartStore.getType(this.props.name) });

        var min = platformChartStore.getMin(this.props.name);
        var max = platformChartStore.getMax(this.props.name);

        this.setState({ min: min ? min : d3.min(this.props.data, function (d) {
                return d["1"];
            }) });
        this.setState({ max: max ? max : d3.max(this.props.data, function (d) {
                return d["1"];
            }) });
    },
    handleClickOutside: function handleClickOutside() {

        if (this.chart) {
            this.nvtooltip = this.chart.querySelector(".nvtooltip");

            if (this.nvtooltip) {
                this.nvtooltip.style.opacity = 0;
            }
        }
    },
    _onChartChange: function _onChartChange(e) {
        var chartType = e.target.value;

        var lineChart = this._drawLineChart(this.state.chartName, chartType, this._lineData(this._getNested(this.props.data)), this.state.min, this.state.max);

        this.setState({ lineChart: lineChart });
        this.setState({ showTaptip: false });

        platformChartActionCreators.setType(this.props.name, chartType);

        if (this.state.pinned) {
            platformActionCreators.saveCharts();
        }
    },
    _onPinToggle: function _onPinToggle() {

        var pinned = !this.state.pinned;

        platformChartActionCreators.pinChart(this.props.name);

        platformActionCreators.saveCharts();
    },
    _onRefreshChange: function _onRefreshChange(e) {
        platformChartActionCreators.changeRefreshRate(e.target.value, this.props.name);

        if (this.state.pinned) {
            platformActionCreators.saveCharts();
        }
    },
    _onMinChange: function _onMinChange(e) {
        var min = e.target.value;
        var lineChart = this._drawLineChart(this.state.chartName, this.state.chartType, this._lineData(this._getNested(this.props.data)), min, this.state.max);

        this.setState({ lineChart: lineChart });

        platformChartActionCreators.setMin(min, this.props.name);

        if (this.state.pinned) {
            platformActionCreators.saveCharts();
        }
    },
    _onMaxChange: function _onMaxChange(e) {
        var max = e.target.value;
        var lineChart = this._drawLineChart(this.state.chartName, this.state.chartType, this._lineData(this._getNested(this.props.data)), this.state.min, max);

        this.setState({ lineChart: lineChart });

        platformChartActionCreators.setMax(max, this.props.name);

        if (this.state.pinned) {
            platformActionCreators.saveCharts();
        }
    },
    render: function render() {

        var chartStyle = {
            width: "90%"
        };

        var svgStyle = {
            padding: "0px 50px"
        };

        var controlStyle = {
            width: "100%",
            textAlign: "left"
        };

        var pinClasses = ["chart-pin inlineBlock"];
        pinClasses.push(this.state.pinned ? "pinned-chart" : "unpinned-chart");

        var controlButtons;

        if (!this.props.hideControls) {
            var taptipX = 0;
            var taptipY = 40;

            var tooltipX = 0;
            var tooltipY = 80;

            var chartTypeSelect = React.createElement(
                'select',
                {
                    onChange: this._onChartChange,
                    value: this.state.chartType,
                    autoFocus: true,
                    required: true
                },
                React.createElement(
                    'option',
                    { value: 'line' },
                    'Line'
                ),
                React.createElement(
                    'option',
                    { value: 'lineWithFocus' },
                    'Line with View Finder'
                ),
                React.createElement(
                    'option',
                    { value: 'stackedArea' },
                    'Stacked Area'
                ),
                React.createElement(
                    'option',
                    { value: 'cumulativeLine' },
                    'Cumulative Line'
                )
            );

            var chartTypeTaptip = {
                "title": "Chart Type",
                "content": chartTypeSelect,
                "x": taptipX,
                "y": taptipY
            };
            var chartTypeIcon = React.createElement('i', { className: 'fa fa-line-chart' });
            var chartTypeTooltip = {
                "content": "Chart Type",
                "x": tooltipX,
                "y": tooltipY
            };

            var chartTypeControlButton = React.createElement(ControlButton, {
                name: this.state.chartName + "_chartTypeControlButton",
                taptip: chartTypeTaptip,
                tooltip: chartTypeTooltip,
                icon: chartTypeIcon });

            var pinChartIcon = React.createElement(
                'div',
                { className: pinClasses.join(' ') },
                React.createElement('i', { className: 'fa fa-thumb-tack' })
            );
            var pinChartTooltip = {
                "content": "Pin to Dashboard",
                "x": tooltipX,
                "y": tooltipY
            };

            var pinChartControlButton = React.createElement(ControlButton, {
                name: this.state.chartName + "_pinChartControlButton",
                icon: pinChartIcon,
                tooltip: pinChartTooltip,
                clickAction: this._onPinToggle });

            var refreshChart = React.createElement(
                'div',
                null,
                React.createElement('input', {
                    type: 'number',
                    onChange: this._onRefreshChange,
                    value: this.props.refreshInterval,
                    min: '15000',
                    step: '1000',
                    placeholder: 'disabled'
                }),
                ' (ms)',
                React.createElement('br', null),
                React.createElement(
                    'span',
                    null,
                    'Omit to disable'
                )
            );

            var refreshChartTaptip = {
                "title": "Refresh Rate",
                "content": refreshChart,
                "x": taptipX,
                "y": taptipY
            };
            var refreshChartIcon = React.createElement('i', { className: 'fa fa-hourglass' });
            var refreshChartTooltip = {
                "content": "Refresh Rate",
                "x": tooltipX,
                "y": tooltipY
            };

            var refreshChartControlButton = React.createElement(ControlButton, {
                name: this.state.chartName + "_refreshChartControlButton",
                taptip: refreshChartTaptip,
                tooltip: refreshChartTooltip,
                icon: refreshChartIcon });

            var chartMin = React.createElement(
                'div',
                null,
                React.createElement('input', {
                    type: 'number',
                    onChange: this._onMinChange,
                    value: this.state.min,
                    step: '1'
                })
            );

            var chartMinTaptip = {
                "title": "Y Axis Min",
                "content": chartMin,
                "x": taptipX,
                "y": taptipY
            };
            var chartMinIcon = React.createElement(
                'div',
                { className: 'moveMin' },
                React.createElement(
                    'span',
                    null,
                    '▬'
                )
            );

            tooltipX = tooltipX + 20;

            var chartMinTooltip = {
                "content": "Y Axis Min",
                "x": tooltipX,
                "y": tooltipY
            };

            var chartMinControlButton = React.createElement(ControlButton, {
                name: this.state.chartName + "_chartMinControlButton",
                taptip: chartMinTaptip,
                tooltip: chartMinTooltip,
                icon: chartMinIcon });

            var chartMax = React.createElement(
                'div',
                null,
                React.createElement('input', {
                    type: 'number',
                    onChange: this._onMaxChange,
                    value: this.state.max,
                    step: '1'
                })
            );

            var chartMaxTaptip = {
                "title": "Y Axis Max",
                "content": chartMax,
                "x": taptipX,
                "y": taptipY
            };
            var chartMaxIcon = React.createElement(
                'div',
                { className: 'moveMax' },
                React.createElement(
                    'span',
                    null,
                    '▬'
                )
            );

            tooltipX = tooltipX + 20;

            var chartMaxTooltip = {
                "content": "Y Axis Max",
                "x": tooltipX,
                "y": tooltipY
            };

            var chartMaxControlButton = React.createElement(ControlButton, {
                name: this.state.chartName + "_chartMaxControlButton",
                taptip: chartMaxTaptip,
                tooltip: chartMaxTooltip,
                icon: chartMaxIcon });

            var spaceStyle = {
                width: "20px",
                height: "2px"
            };

            controlButtons = React.createElement(
                'div',
                { className: 'displayBlock',
                    style: controlStyle },
                pinChartControlButton,
                chartTypeControlButton,
                refreshChartControlButton,
                chartMinControlButton,
                chartMaxControlButton,
                React.createElement('div', { className: 'inlineBlock',
                    style: spaceStyle })
            );
        }

        return React.createElement(
            'div',
            { className: 'platform-line-chart',
                style: chartStyle,
                ref: this.state.chartName },
            React.createElement('svg', { id: this.state.chartName, style: svgStyle }),
            controlButtons
        );
    },
    _drawLineChart: function _drawLineChart(elementParent, chartType, data, yMin, yMax) {

        var tickCount = 0;
        // var lineChart;

        switch (chartType) {
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

        this.lineChart.margin({ left: 25, right: 25 }).x(function (d) {
            return d.x;
        }).y(function (d) {
            return d.y;
        }).useInteractiveGuideline(true).showYAxis(true).showXAxis(true);
        this.lineChart.xAxis.tickFormat(function (d, i) {

            var tickValue;

            if (typeof i === "undefined") {
                if (tickCount === 0) {
                    tickValue = moment(d).fromNow();
                    tickCount++;
                } else if (tickCount === 1) {
                    tickValue = moment(d).fromNow();
                    tickCount = 0;
                }
            } else {
                tickValue = "";
            }

            return tickValue;
        }).staggerLabels(false);
        this.lineChart.yAxis.tickFormat(d3.format('.1f'));
        this.lineChart.forceY([yMin, yMax]);

        switch (chartType) {
            case "lineWithFocus":
                this.lineChart.x2Axis.tickFormat(function (d) {
                    return d3.time.format('%X')(new Date(d));
                });
                break;
        }

        d3.selectAll('#' + elementParent + ' > *').remove();
        d3.select('#' + elementParent).datum(data).call(this.lineChart);
        nv.utils.windowResize(function () {
            if (this.lineChart) {
                this.lineChart.update();
            }
        });

        nv.addGraph(function () {
            return this.lineChart;
        });

        return this.lineChart;
    },
    _updateLineChart: function _updateLineChart(lineChart, elementParent, data) {
        d3.select('#' + elementParent).datum(data).call(lineChart);
    },
    _getNested: function _getNested(data) {
        var keyYearMonth = d3.nest().key(function (d) {
            return d.parent;
        }).key(function (d) {
            return d["0"];
        });
        var keyedData = keyYearMonth.entries(data.map(function (d) {
            return d;
        }));
        return keyedData;
    },
    _lineData: function _lineData(data) {
        var colors = ['DarkOrange', 'ForestGreen', 'DeepPink', 'DarkViolet', 'Teal', 'Maroon', 'RoyalBlue', 'Silver', 'MediumPurple', 'Red', 'Lime', 'Tan', 'LightGoldenrodYellow', 'Turquoise', 'Pink', 'DeepSkyBlue', 'OrangeRed', 'LightGrey', 'Olive'];
        data = data.sort(function (a, b) {
            return a.key > b.key;
        });
        var lineDataArr = [];
        for (var i = 0; i <= data.length - 1; i++) {
            var lineDataElement = [];
            var currentValues = data[i].values.sort(function (a, b) {
                return +a.key - +b.key;
            });
            for (var j = 0; j <= currentValues.length - 1; j++) {
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

}));

module.exports = PlatformChart;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-action-creators":6,"../action-creators/platform-chart-action-creators":7,"../action-creators/platforms-panel-action-creators":9,"../stores/platform-chart-store":62,"./confirm-form":18,"./control-button":20,"d3":undefined,"moment":undefined,"nvd3":undefined,"react":undefined,"react-click-outside":undefined,"react-dom":undefined,"react-router":undefined}],37:[function(require,module,exports){
'use strict';

var React = require('react');
var PlatformChart = require('./platform-chart');
var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var NewChartForm = require('./new-chart-form');
var chartStore = require('../stores/platform-chart-store');

var PlatformCharts = React.createClass({
    displayName: 'PlatformCharts',

    getInitialState: function getInitialState() {

        var state = {
            chartData: chartStore.getData()
        };

        return state;
    },
    componentDidMount: function componentDidMount() {
        chartStore.addChangeListener(this._onChartStoreChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        chartStore.removeChangeListener(this._onChartStoreChange);
    },
    _onChartStoreChange: function _onChartStoreChange() {
        this.setState({ chartData: chartStore.getData() });
    },
    _onAddChartClick: function _onAddChartClick() {

        platformActionCreators.loadChartTopics();
        modalActionCreators.openModal(React.createElement(NewChartForm, null));
    },
    render: function render() {

        var chartData = this.state.chartData;

        var platformCharts = [];

        for (var key in chartData) {
            if (chartData[key].data.length > 0) {
                var platformChart = React.createElement(PlatformChart, { key: key,
                    chart: chartData[key],
                    chartKey: key,
                    hideControls: false });
                platformCharts.push(platformChart);
            }
        }

        if (platformCharts.length === 0) {
            var noCharts = React.createElement(
                'p',
                { className: 'empty-help' },
                'No charts have been loaded.'
            );
            platformCharts.push(noCharts);
        }

        return React.createElement(
            'div',
            { className: 'view' },
            React.createElement(
                'div',
                { className: 'absolute_anchor' },
                React.createElement(
                    'div',
                    { className: 'view__actions' },
                    React.createElement(
                        'button',
                        {
                            className: 'button',
                            onClick: this._onAddChartClick
                        },
                        'Add Chart'
                    )
                ),
                React.createElement(
                    'h2',
                    null,
                    'Charts'
                ),
                platformCharts
            )
        );
    }
});

module.exports = PlatformCharts;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-action-creators":6,"../stores/platform-chart-store":62,"./new-chart-form":33,"./platform-chart":36,"react":undefined}],38:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var $ = require('jquery');

var ReactDOM = require('react-dom');
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
var platformsStore = require('../stores/platforms-store');

var PlatformManager = function (_React$Component) {
    _inherits(PlatformManager, _React$Component);

    function PlatformManager(props) {
        _classCallCheck(this, PlatformManager);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(PlatformManager).call(this, props));

        _this._doModalBindings = _this._doModalBindings.bind(_this);
        _this._onStoreChange = _this._onStoreChange.bind(_this);

        _this.state = getStateFromStores();
        return _this;
    }

    _createClass(PlatformManager, [{
        key: 'componentWillMount',
        value: function componentWillMount() {
            if (!this.state.initialized) {
                platformManagerActionCreators.initialize();
            }
        }
    }, {
        key: 'componentDidMount',
        value: function componentDidMount() {
            authorizationStore.addChangeListener(this._onStoreChange);
            consoleStore.addChangeListener(this._onStoreChange);
            modalStore.addChangeListener(this._onStoreChange);
            platformsPanelStore.addChangeListener(this._onStoreChange);
            platformsStore.addChangeListener(this._onStoreChange);
            statusIndicatorStore.addChangeListener(this._onStoreChange);
            this._doModalBindings();
        }
    }, {
        key: 'componentDidUpdate',
        value: function componentDidUpdate() {
            this._doModalBindings();

            if (this.state.expanded) {
                var handle = document.querySelector(".resize-handle");

                var onMouseDown = function onMouseDown(evt) {
                    var exteriorPanel = this.parentNode;
                    var children = exteriorPanel.parentNode.childNodes;
                    var platformsPanel;

                    for (var i = 0; i < children.length; i++) {
                        if (children[i].classList.contains("platform-statuses")) {
                            platformsPanel = children[i];
                            break;
                        }
                    }

                    var target = evt.target.setCapture ? evt.target : document;

                    if (target.setCapture) {
                        target.setCapture();
                    }

                    var onMouseMove = function onMouseMove(evt) {
                        var newWidth = Math.min(window.innerWidth, evt.clientX);

                        platformsPanel.style.width = newWidth + "px";
                        exteriorPanel.style.width = window.innerWidth - newWidth - 100 + "px";
                    };

                    var onMouseUp = function onMouseUp(evt) {
                        target.removeEventListener("mousemove", onMouseMove);
                        target.removeEventListener("mouseup", onMouseUp);
                    };

                    target.addEventListener("mousemove", onMouseMove);
                    target.addEventListener("mouseup", onMouseUp);

                    evt.preventDefault();
                };

                handle.addEventListener("mousedown", onMouseDown);
            }
        }
    }, {
        key: '_doModalBindings',
        value: function _doModalBindings() {
            if (this.state.modalContent) {
                window.addEventListener('keydown', this._closeModal);
                this._focusDisabled = $('input,select,textarea,button,a', ReactDOM.findDOMNode(this.refs.main)).attr('tabIndex', -1);
            } else {
                window.removeEventListener('keydown', this._closeModal);
                if (this._focusDisabled) {
                    this._focusDisabled.removeAttr('tabIndex');
                    delete this._focusDisabled;
                }
            }
        }
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {
            authorizationStore.removeChangeListener(this._onStoreChange);
            consoleStore.removeChangeListener(this._onStoreChange);
            modalStore.removeChangeListener(this._onStoreChange);
            platformsPanelStore.removeChangeListener(this._onStoreChange);
            platformsStore.removeChangeListener(this._onStoreChange);
            statusIndicatorStore.removeChangeListener(this._onStoreChange);
        }
    }, {
        key: '_onStoreChange',
        value: function _onStoreChange() {
            this.setState(getStateFromStores());
        }
    }, {
        key: '_onToggleClick',
        value: function _onToggleClick() {
            consoleActionCreators.toggleConsole();
        }
    }, {
        key: '_closeModal',
        value: function _closeModal(e) {
            if (e.keyCode === 27) {
                modalActionCreators.closeModal();
            }
        }
    }, {
        key: 'render',
        value: function render() {
            var classes = ['platform-manager'];
            var modal;
            var exteriorClasses = ["panel-exterior"];

            if (this.state.expanded === true) {
                exteriorClasses.push("narrow-exterior");
                exteriorClasses.push("slow-narrow");
            } else if (this.state.expanded === false) {
                exteriorClasses.push("wide-exterior");
                exteriorClasses.push("slow-wide");
            } else if (this.state.expanded === null) {
                exteriorClasses.push("wide-exterior");
            }

            var statusIndicator;

            if (this.state.consoleShown) {
                classes.push('console-open');
            }

            classes.push(this.state.loggedIn ? 'logged-in' : 'not-logged-in');

            if (this.state.modalContent) {
                classes.push('modal-open');
                modal = _react2.default.createElement(
                    Modal,
                    null,
                    this.state.modalContent
                );
            }

            if (this.state.status) {
                statusIndicator = _react2.default.createElement(StatusIndicator, null);
            }

            var resizeHandle;

            if (this.state.expanded === true) {
                resizeHandle = _react2.default.createElement('div', { className: 'resize-handle' });

                exteriorClasses.push("absolute_anchor");
            }

            return _react2.default.createElement(
                'div',
                { className: classes.join(' ') },
                statusIndicator,
                modal,
                _react2.default.createElement(
                    'div',
                    { ref: 'main', className: 'main' },
                    _react2.default.createElement(Navigation, null),
                    _react2.default.createElement(PlatformsPanel, null),
                    _react2.default.createElement(
                        'div',
                        { className: exteriorClasses.join(' ') },
                        resizeHandle,
                        this.props.children
                    )
                ),
                _react2.default.createElement('input', {
                    className: 'toggle',
                    type: 'button',
                    value: 'Console ' + (this.state.consoleShown ? '▼' : '▲'),
                    onClick: this._onToggleClick
                }),
                this.state.consoleShown && _react2.default.createElement(Console, { className: 'console' })
            );
        }
    }]);

    return PlatformManager;
}(_react2.default.Component);

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!authorizationStore.getAuthorization(),
        modalContent: modalStore.getModalContent(),
        expanded: platformsPanelStore.getExpanded(),
        status: statusIndicatorStore.getStatus(),
        initialized: platformsStore.getInitialized()
    };
}

exports.default = PlatformManager;

},{"../action-creators/console-action-creators":2,"../action-creators/modal-action-creators":5,"../action-creators/platform-manager-action-creators":8,"../stores/authorization-store":57,"../stores/console-store":58,"../stores/modal-store":61,"../stores/platforms-panel-store":64,"../stores/platforms-store":65,"../stores/status-indicator-store":66,"./console":19,"./modal":31,"./navigation":32,"./platforms-panel":41,"./status-indicator":47,"jquery":undefined,"react":undefined,"react-dom":undefined,"react-router":undefined}],39:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformActionCreators = require('../action-creators/platform-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platform = React.createClass({
    displayName: 'Platform',

    getInitialState: function getInitialState() {
        return getStateFromStores(this);
    },
    componentDidMount: function componentDidMount() {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function _onStoresChange() {
        this.setState(getStateFromStores(this));
    },
    _onFileChange: function _onFileChange(e) {
        if (!e.target.files.length) {
            return;
        }

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
                    file: reader.result
                });
                doFile(index + 1);
            };

            reader.readAsDataURL(files[index]);
        }

        doFile(0);
    },
    render: function render() {
        var platform = this.state.platform;

        if (!platform) {
            return React.createElement(
                'div',
                { className: 'view' },
                React.createElement(
                    'h2',
                    null,
                    React.createElement(
                        Router.Link,
                        { to: 'platforms' },
                        'Platforms'
                    ),
                    ' / ',
                    this.props.params.uuid
                ),
                React.createElement(
                    'p',
                    null,
                    'Platform not found.'
                )
            );
        }

        var agents;

        if (!platform.agents) {
            agents = React.createElement(
                'p',
                null,
                'Loading agents...'
            );
        } else if (!platform.agents.length) {
            agents = React.createElement(
                'p',
                null,
                'No agents installed.'
            );
        } else {
            agents = React.createElement(
                'table',
                null,
                React.createElement(
                    'thead',
                    null,
                    React.createElement(
                        'tr',
                        null,
                        React.createElement(
                            'th',
                            null,
                            'Name'
                        ),
                        React.createElement(
                            'th',
                            null,
                            'Identity'
                        ),
                        React.createElement(
                            'th',
                            null,
                            'UUID'
                        ),
                        React.createElement(
                            'th',
                            null,
                            'Status'
                        ),
                        React.createElement(
                            'th',
                            null,
                            'Action'
                        )
                    )
                ),
                React.createElement(
                    'tbody',
                    null,
                    platform.agents.sort(function (a, b) {
                        if (a.name.toLowerCase() > b.name.toLowerCase()) {
                            return 1;
                        }
                        if (a.name.toLowerCase() < b.name.toLowerCase()) {
                            return -1;
                        }
                        return 0;
                    }).map(function (agent) {
                        return React.createElement(AgentRow, {
                            key: agent.uuid,
                            platform: platform,
                            agent: agent });
                    })
                )
            );
        }

        return React.createElement(
            'div',
            { className: 'platform-view' },
            React.createElement(
                'h2',
                null,
                React.createElement(
                    Router.Link,
                    { to: 'platforms' },
                    'Platforms'
                ),
                ' / ',
                platform.name,
                ' (',
                platform.uuid,
                ')'
            ),
            React.createElement('br', null),
            React.createElement('br', null),
            React.createElement(
                'h3',
                null,
                'Agents'
            ),
            React.createElement(
                'div',
                { className: 'agents-container' },
                agents
            ),
            React.createElement(
                'h3',
                null,
                'Install agents'
            ),
            React.createElement('input', { type: 'file', multiple: true, onChange: this._onFileChange })
        );
    }
});

function getStateFromStores(component) {

    return {
        platform: platformsStore.getPlatform(component.props.params.uuid)
    };
}

module.exports = Platform;

},{"../action-creators/platform-action-creators":6,"../action-creators/status-indicator-action-creators":10,"../stores/platforms-store":65,"./agent-row":11,"react":undefined,"react-router":undefined}],40:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

var _immutable = require('immutable');

var _immutable2 = _interopRequireDefault(_immutable);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var React = require('react');
var Router = require('react-router');


var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var ControlButton = require('./control-button');

var PlatformsPanelItem = function (_BaseComponent) {
    _inherits(PlatformsPanelItem, _BaseComponent);

    function PlatformsPanelItem(props) {
        _classCallCheck(this, PlatformsPanelItem);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(PlatformsPanelItem).call(this, props));

        _this._bind('_onStoresChange', '_expandAll', '_handleArrowClick', '_showCancel', '_resumeLoad', '_checkItem', '_showTooltip', '_hideTooltip', '_moveTooltip', '_onAddDevices', '_onDeviceMethodChange');

        _this.state = {};

        _this.state.showTooltip = false;
        _this.state.tooltipX = null;
        _this.state.tooltipY = null;
        _this.state.checked = _this.props.panelItem.hasOwnProperty("checked") ? _this.props.panelItem.get("checked") : false;
        _this.state.panelItem = _this.props.panelItem;
        _this.state.children = _immutable2.default.fromJS(_this.props.panelChildren);

        if (_this.props.panelItem.get("type") === "platform") {
            _this.state.notInitialized = true;
            _this.state.loading = false;
            _this.state.cancelButton = false;
        }
        return _this;
    }

    _createClass(PlatformsPanelItem, [{
        key: 'componentDidMount',
        value: function componentDidMount() {
            platformsPanelItemsStore.addChangeListener(this._onStoresChange);
        }
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {
            platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
        }
    }, {
        key: 'shouldComponentUpdate',
        value: function shouldComponentUpdate(nextProps, nextState) {

            var doUpdate = false;

            if (this.state.showTooltip !== nextState.showTooltip || this.state.tooltipX !== nextState.tooltipX || this.state.tooltipY !== nextState.tooltipY || this.state.checked !== nextState.checked || this.state.notInitialized !== nextState.notInitialized || this.state.loading !== nextState.loading || this.state.cancelButton !== nextState.cancelButton || !this.state.panelItem.equals(nextState.panelItem)) {
                doUpdate = true;
            } else {
                if (typeof this.state.children === "undefined") {
                    if (typeof nextState.children !== "undefined") {
                        doUpdate = true;
                    }
                } else {
                    if (!this.state.children.equals(nextState.children)) {
                        doUpdate = true;
                    }
                }
            }

            return doUpdate;
        }
    }, {
        key: '_onStoresChange',
        value: function _onStoresChange() {

            var panelItem = _immutable2.default.fromJS(platformsPanelItemsStore.getItem(this.props.itemPath));
            var panelChildren = _immutable2.default.fromJS(platformsPanelItemsStore.getChildren(this.props.panelItem.toJS(), this.props.itemPath));

            var loadingComplete = platformsPanelItemsStore.getLoadingComplete(this.props.panelItem.toJS());

            if (loadingComplete === true || loadingComplete === null) {
                this.setState({ panelItem: panelItem });
                this.setState({ children: panelChildren });
                this.setState({ checked: panelItem.get("checked") });

                if (this.props.panelItem.get("type") === "platform") {
                    if (loadingComplete === true) {
                        this.setState({ loading: false });
                        this.setState({ notInitialized: false });
                    } else if (loadingComplete === null) {
                        this.setState({ loading: false });
                        this.setState({ notInitialized: true });
                    }
                }
            }
        }
    }, {
        key: '_expandAll',
        value: function _expandAll() {

            platformsPanelActionCreators.expandAll(this.props.itemPath);
        }
    }, {
        key: '_handleArrowClick',
        value: function _handleArrowClick() {

            if (!this.state.loading) // If not loading, treat it as just a regular toggle button
                {
                    if (this.state.panelItem.get("expanded") === null && this.state.panelItem.get("type") === "platform") {
                        this.setState({ loading: true });
                        platformsPanelActionCreators.loadChildren(this.props.panelItem.get("type"), this.props.panelItem.toJS());
                    } else {
                        if (this.state.panelItem.get("expanded")) {
                            platformsPanelActionCreators.expandAll(this.props.itemPath);
                        } else {
                            platformsPanelActionCreators.toggleItem(this.props.itemPath);
                        }
                    }
                } else if (this.state.hasOwnProperty("loading")) // it's a platform and it's loading
                {
                    if (this.state.loading || this.state.cancelButton) // if either loading or cancelButton is still
                        {
                            // true, either way, the user wants to 
                            this.setState({ loading: false }); // get out of the loading state, so turn
                            this.setState({ cancelButton: false }); // the toggle button back to an arrow icon
                        }
                }
        }
    }, {
        key: '_showCancel',
        value: function _showCancel() {

            if (this.state.hasOwnProperty("loading") && this.state.loading === true) {
                this.setState({ cancelButton: true });
            }
        }
    }, {
        key: '_resumeLoad',
        value: function _resumeLoad() {

            if (this.state.hasOwnProperty("loading")) {
                this.setState({ cancelButton: false });
            }
        }
    }, {
        key: '_checkItem',
        value: function _checkItem(e) {

            var checked = e.target.checked;

            if (checked) {
                this.setState({ checked: null });
                platformChartActionCreators.addToChart(this.props.panelItem.toJS());
            } else {
                this.setState({ checked: null });
                platformChartActionCreators.removeFromChart(this.props.panelItem.toJS());
            }
        }
    }, {
        key: '_showTooltip',
        value: function _showTooltip(evt) {
            this.setState({ showTooltip: true });
            this.setState({ tooltipX: evt.clientX - 60 });
            this.setState({ tooltipY: evt.clientY - 70 });
        }
    }, {
        key: '_hideTooltip',
        value: function _hideTooltip() {
            this.setState({ showTooltip: false });
        }
    }, {
        key: '_moveTooltip',
        value: function _moveTooltip(evt) {
            this.setState({ tooltipX: evt.clientX - 60 });
            this.setState({ tooltipY: evt.clientY - 70 });
        }
    }, {
        key: '_onAddDevices',
        value: function _onAddDevices(evt) {
            devicesActionCreators.configureDevices(this.state.panelItem.toJS());
        }
    }, {
        key: '_onDeviceMethodChange',
        value: function _onDeviceMethodChange(evt) {

            var deviceMethod = evt.target.value;

            this.setState({ deviceMethod: deviceMethod });

            if (deviceMethod) {
                devicesActionCreators.addDevices(this.state.panelItem.toJS(), deviceMethod);
                controlButtonActionCreators.hideTaptip("addDevicesButton");
            }
        }
    }, {
        key: 'render',
        value: function render() {

            console.log("rendering " + this.state.panelItem.get("name"));
            var panelItem = this.state.panelItem;
            var itemPath = this.props.itemPath;
            var propChildren = this.state.children;
            var children;

            var visibleStyle = {};

            if (panelItem.get("visible") !== true) {
                visibleStyle = {
                    display: "none"
                };
            }

            var childClass;
            var arrowClasses = ["arrowButton", "noRotate"];
            var arrowContent;
            var arrowContentStyle = {
                width: "14px"
            };

            if (this.state.hasOwnProperty("loading")) {
                if (this.state.cancelButton) {
                    arrowClasses.push("cancelLoading");
                } else if (this.state.loading) {
                    arrowClasses.push("loadingSpinner");
                }
            }

            var DevicesButton;

            if (["platform"].indexOf(panelItem.get("type")) > -1) {
                var taptipX = 20;
                var taptipY = 100;

                var tooltipX = 20;
                var tooltipY = 70;

                var devicesSelect = React.createElement(
                    'select',
                    {
                        onChange: this._onDeviceMethodChange,
                        value: this.state.deviceMethod,
                        autoFocus: true,
                        required: true
                    },
                    React.createElement(
                        'option',
                        { value: '' },
                        '-- Select method --'
                    ),
                    React.createElement(
                        'option',
                        { value: 'scanForDevices' },
                        'Scan for Devices'
                    ),
                    React.createElement(
                        'option',
                        { value: 'addDevicesManually' },
                        'Add Manually'
                    )
                );

                var devicesTaptip = {
                    "title": "Add Devices",
                    "content": devicesSelect,
                    "xOffset": taptipX,
                    "yOffset": taptipY
                };

                var devicesTooltip = {
                    "content": "Add Devices",
                    "xOffset": tooltipX,
                    "yOffset": tooltipY
                };

                DevicesButton = React.createElement(ControlButton, {
                    name: 'addDevicesButton',
                    tooltip: devicesTooltip,
                    controlclass: 'panelItemButton',
                    nocentering: true,
                    floatleft: true,
                    fontAwesomeIcon: 'cogs',
                    clickAction: this._onAddDevices });
            }

            var ChartCheckbox;

            if (["point"].indexOf(panelItem.get("type")) > -1) {
                if (this.state.checked !== null) {
                    ChartCheckbox = React.createElement('input', { className: 'panelItemCheckbox',
                        type: 'checkbox',
                        onChange: this._checkItem,
                        checked: this.state.checked });
                } else {
                    ChartCheckbox = React.createElement(
                        'div',
                        { className: 'checkboxSpinner arrowButton' },
                        React.createElement(
                            'span',
                            { style: arrowContentStyle },
                            React.createElement('i', { className: 'fa fa-circle-o-notch fa-spin fa-fw' })
                        )
                    );
                }
            }

            var tooltipStyle = {
                display: panelItem.get("type") !== "type" ? this.state.showTooltip ? "block" : "none" : "none",
                position: "absolute",
                top: this.state.tooltipY + "px",
                left: this.state.tooltipX + "px"
            };

            var toolTipClasses = this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer";

            if (!this.state.loading) {
                arrowClasses.push(panelItem.get("status") === "GOOD" ? "status-good" : panelItem.get("status") === "BAD" ? "status-bad" : "status-unknown");
            }

            var agentInfo;

            if (panelItem.get("type") === "agent") {
                agentInfo = React.createElement(
                    'div',
                    null,
                    'Identity: ',
                    panelItem.get("identity")
                );
            }

            if (this.state.cancelButton) {
                arrowContent = React.createElement(
                    'span',
                    { style: arrowContentStyle },
                    React.createElement('i', { className: 'fa fa-remove' })
                );
            } else if (this.state.loading) {
                arrowContent = React.createElement(
                    'span',
                    { style: arrowContentStyle },
                    React.createElement('i', { className: 'fa fa-circle-o-notch fa-spin fa-fw' })
                );
            } else if (panelItem.get("status") === "GOOD") {
                arrowContent = React.createElement(
                    'span',
                    { style: arrowContentStyle },
                    '▶'
                );
            } else if (panelItem.get("status") === "BAD") {
                arrowContent = React.createElement(
                    'span',
                    { style: arrowContentStyle },
                    React.createElement('i', { className: 'fa fa-minus-circle' })
                );
            } else {
                arrowContent = React.createElement(
                    'span',
                    { style: arrowContentStyle },
                    '▬'
                );
            }

            if (this.state.panelItem.get("expanded") === true && propChildren) {
                children = propChildren.sort(function (a, b) {
                    if (a.get("name").toUpperCase() > b.get("name").toUpperCase()) {
                        return 1;
                    }
                    if (a.get("name").toUpperCase() < b.get("name").toUpperCase()) {
                        return -1;
                    }
                    return 0;
                }).sort(function (a, b) {
                    if (a.get("sortOrder") > b.get("sortOrder")) {
                        return 1;
                    }
                    if (a.get("sortOrder") < b.get("sortOrder")) {
                        return -1;
                    }
                    return 0;
                }).map(function (propChild) {

                    var grandchildren = [];
                    propChild.get("children").forEach(function (childString) {
                        grandchildren.push(propChild.get(childString));
                    });

                    var itemKey = propChild.hasOwnProperty("uuid") ? propChild.get("uuid") : propChild.get("name") + this.get("uuid");

                    return React.createElement(PlatformsPanelItem, { key: itemKey,
                        panelItem: propChild,
                        itemPath: propChild.get("path").toJS(),
                        panelChildren: grandchildren });
                }, this.state.panelItem);

                if (children.length > 0) {
                    var classIndex = arrowClasses.indexOf("noRotate");

                    if (classIndex > -1) {
                        arrowClasses.splice(classIndex, 1);
                    }

                    arrowClasses.push("rotateDown");
                    childClass = "showItems";
                }
            }

            var itemClasses = [];

            if (!panelItem.hasOwnProperty("uuid")) {
                itemClasses.push("item_type");
            } else {
                itemClasses.push("item_label");
            }

            if (panelItem.get("type") === "platform" && this.state.notInitialized) {
                itemClasses.push("not_initialized");
            }

            var listItem = React.createElement(
                'div',
                { className: itemClasses.join(' ') },
                panelItem.get("name")
            );

            return React.createElement(
                'li',
                {
                    key: panelItem.get("uuid"),
                    className: 'panel-item',
                    style: visibleStyle
                },
                React.createElement(
                    'div',
                    { className: 'platform-info' },
                    React.createElement(
                        'div',
                        { className: arrowClasses.join(' '),
                            onDoubleClick: this._expandAll,
                            onClick: this._handleArrowClick,
                            onMouseEnter: this._showCancel,
                            onMouseLeave: this._resumeLoad },
                        arrowContent
                    ),
                    DevicesButton,
                    ChartCheckbox,
                    React.createElement(
                        'div',
                        { className: toolTipClasses,
                            style: tooltipStyle },
                        React.createElement(
                            'div',
                            { className: 'tooltip_inner' },
                            React.createElement(
                                'div',
                                { className: 'opaque_inner' },
                                agentInfo,
                                'Status: ',
                                panelItem.get("context") ? panelItem.get("context") : panelItem.get("statusLabel")
                            )
                        )
                    ),
                    React.createElement(
                        'div',
                        { className: 'tooltip_target',
                            onMouseEnter: this._showTooltip,
                            onMouseLeave: this._hideTooltip,
                            onMouseMove: this._moveTooltip },
                        listItem
                    )
                ),
                React.createElement(
                    'div',
                    { className: childClass },
                    React.createElement(
                        'ul',
                        { className: 'platform-panel-list' },
                        children
                    )
                )
            );
        }
    }]);

    return PlatformsPanelItem;
}(_baseComponent2.default);

;

exports.default = PlatformsPanelItem;

},{"../action-creators/control-button-action-creators":3,"../action-creators/devices-action-creators":4,"../action-creators/platform-chart-action-creators":7,"../action-creators/platforms-panel-action-creators":9,"../stores/platforms-panel-items-store":63,"./base-component":12,"./control-button":20,"immutable":undefined,"react":undefined,"react-router":undefined}],41:[function(require,module,exports){
'use strict';

var _platformsPanelItem = require('./platforms-panel-item');

var _platformsPanelItem2 = _interopRequireDefault(_platformsPanelItem);

var _immutable = require('immutable');

var _immutable2 = _interopRequireDefault(_immutable);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var React = require('react');
var Router = require('react-router');


var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var ControlButton = require('./control-button');

var PlatformsPanel = React.createClass({
    displayName: 'PlatformsPanel',

    getInitialState: function getInitialState() {
        var state = {};
        state.platforms = [];
        state.expanded = platformsPanelStore.getExpanded();
        state.filterValue = "";
        state.filterStatus = "";

        return state;
    },
    componentDidMount: function componentDidMount() {
        platformsPanelStore.addChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.addChangeListener(this._onPanelItemsStoreChange);

        this.exteriorPanel = document.querySelector(".panel-exterior");
        var children = this.exteriorPanel.parentNode.childNodes;

        for (var i = 0; i < children.length; i++) {
            if (children[i].classList.contains("platform-statuses")) {
                this.platformsPanel = children[i];
                break;
            }
        }
    },
    componentWillUnmount: function componentWillUnmount() {
        platformsPanelStore.removeChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.removeChangeListener(this._onPanelItemsStoreChange);
    },
    _onPanelStoreChange: function _onPanelStoreChange() {
        var expanded = platformsPanelStore.getExpanded();

        if (expanded !== this.state.expanded) {
            this.setState({ expanded: expanded });
        }

        if (expanded !== null) {
            if (expanded === false) {
                this.platformsPanel.style.width = "";
                this.exteriorPanel.style.width = "";
            }

            var platformsList = platformsPanelItemsStore.getChildren("platforms", null);
            this.setState({ platforms: platformsList });
        } else {
            this.setState({ filterValue: "" });
            this.setState({ filterStatus: "" });
            this.platformsPanel.style.width = "";
            this.exteriorPanel.style.width = "";
        }
    },
    _onPanelItemsStoreChange: function _onPanelItemsStoreChange() {
        if (this.state.expanded !== null) {
            this.setState({ platforms: platformsPanelItemsStore.getChildren("platforms", null) });
        }
    },
    _onFilterBoxChange: function _onFilterBoxChange(e) {
        this.setState({ filterValue: e.target.value });
        platformsPanelActionCreators.loadFilteredItems(e.target.value, "");
        this.setState({ filterStatus: "" });
    },
    _onFilterGood: function _onFilterGood(e) {
        platformsPanelActionCreators.loadFilteredItems("", "GOOD");
        this.setState({ filterStatus: "GOOD" });
        this.setState({ filterValue: "" });
    },
    _onFilterBad: function _onFilterBad(e) {
        platformsPanelActionCreators.loadFilteredItems("", "BAD");
        this.setState({ filterStatus: "BAD" });
        this.setState({ filterValue: "" });
    },
    _onFilterUnknown: function _onFilterUnknown(e) {
        platformsPanelActionCreators.loadFilteredItems("", "UNKNOWN");
        this.setState({ filterStatus: "UNKNOWN" });
        this.setState({ filterValue: "" });
    },
    _onFilterOff: function _onFilterOff(e) {
        platformsPanelActionCreators.loadFilteredItems("", "");
        this.setState({ filterValue: "" });
        this.setState({ filterStatus: "" });
    },
    _togglePanel: function _togglePanel() {
        platformsPanelActionCreators.togglePanel();
    },
    render: function render() {
        var platforms;

        var classes = this.state.expanded === null ? ["platform-statuses", "platform-collapsed"] : this.state.expanded ? ["platform-statuses", "slow-open", "platform-expanded"] : ["platform-statuses", "slow-shut", "platform-collapsed"];

        var contentsStyle = {
            display: this.state.expanded ? "block" : "none",
            padding: "0px 0px 20px 10px",
            clear: "right",
            width: "100%"
        };

        var filterBoxContainer = {
            textAlign: "left"
        };

        var filterGood, filterBad, filterUnknown;
        filterGood = filterBad = filterUnknown = false;

        switch (this.state.filterStatus) {
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

        var tooltipX = 80;
        var tooltipY = 220;

        var filterGoodIcon = React.createElement(
            'div',
            { className: 'status-good' },
            React.createElement(
                'span',
                null,
                '▶'
            )
        );
        var filterGoodTooltip = {
            "content": "Healthy",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterGoodControlButton = React.createElement(ControlButton, {
            name: 'filterGoodControlButton',
            icon: filterGoodIcon,
            selected: filterGood,
            tooltip: filterGoodTooltip,
            clickAction: this._onFilterGood });

        var filterBadIcon = React.createElement(
            'div',
            { className: 'status-bad' },
            React.createElement('i', { className: 'fa fa-minus-circle' })
        );
        var filterBadTooltip = {
            "content": "Unhealthy",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterBadControlButton = React.createElement(ControlButton, {
            name: 'filterBadControlButton',
            icon: filterBadIcon,
            selected: filterBad,
            tooltip: filterBadTooltip,
            clickAction: this._onFilterBad });

        var filterUnknownIcon = React.createElement(
            'div',
            { className: 'status-unknown moveDown' },
            React.createElement(
                'span',
                null,
                '▬'
            )
        );
        var filterUnknownTooltip = {
            "content": "Unknown Status",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterUnknownControlButton = React.createElement(ControlButton, {
            name: 'filterUnknownControlButton',
            icon: filterUnknownIcon,
            selected: filterUnknown,
            tooltip: filterUnknownTooltip,
            clickAction: this._onFilterUnknown });

        var filterOffIcon = React.createElement('i', { className: 'fa fa-ban' });
        var filterOffTooltip = {
            "content": "Clear Filter",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterOffControlButton = React.createElement(ControlButton, {
            name: 'filterOffControlButton',
            icon: filterOffIcon,
            tooltip: filterOffTooltip,
            clickAction: this._onFilterOff });

        if (!this.state.platforms) {
            platforms = React.createElement(
                'p',
                null,
                'Loading platforms panel ...'
            );
        } else if (!this.state.platforms.length) {
            platforms = React.createElement(
                'p',
                null,
                'No platforms found.'
            );
        } else {
            platforms = this.state.platforms.sort(function (a, b) {
                if (a.name.toUpperCase() > b.name.toUpperCase()) {
                    return 1;
                }
                if (a.name.toUpperCase() < b.name.toUpperCase()) {
                    return -1;
                }
                return 0;
            }).map(function (platform) {
                return React.createElement(_platformsPanelItem2.default, {
                    key: platform.uuid,
                    panelItem: _immutable2.default.fromJS(platform),
                    itemPath: platform.path });
            });
        }

        return React.createElement(
            'div',
            { className: classes.join(" ") },
            React.createElement(
                'div',
                { className: 'extend-panel',
                    onClick: this._togglePanel },
                this.state.expanded ? '◀' : '▶'
            ),
            React.createElement(
                'div',
                { style: contentsStyle },
                React.createElement('br', null),
                React.createElement(
                    'div',
                    { className: 'filter_box', style: filterBoxContainer },
                    React.createElement('span', { className: 'fa fa-search' }),
                    React.createElement('input', {
                        type: 'search',
                        onChange: this._onFilterBoxChange,
                        value: this.state.filterValue
                    }),
                    React.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        filterGoodControlButton,
                        filterBadControlButton,
                        filterUnknownControlButton,
                        filterOffControlButton
                    )
                ),
                React.createElement(
                    'ul',
                    { className: 'platform-panel-list' },
                    platforms
                )
            )
        );
    }
});

module.exports = PlatformsPanel;

},{"../action-creators/platforms-panel-action-creators":9,"../stores/platforms-panel-items-store":63,"../stores/platforms-panel-store":64,"./control-button":20,"./platforms-panel-item":40,"immutable":undefined,"react":undefined,"react-router":undefined}],42:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformsStore = require('../stores/platforms-store');
var RegisterPlatformForm = require('../components/register-platform-form');
var DeregisterPlatformConfirmation = require('../components/deregister-platform-confirmation');

var Platforms = React.createClass({
    displayName: 'Platforms',

    getInitialState: function getInitialState() {
        return getStateFromStores();
    },
    componentDidMount: function componentDidMount() {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function componentWillUnmount() {
        platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function _onStoresChange() {
        this.setState(getStateFromStores());
    },
    _onRegisterClick: function _onRegisterClick() {
        modalActionCreators.openModal(React.createElement(RegisterPlatformForm, null));
    },
    _onDeregisterClick: function _onDeregisterClick(platform) {
        modalActionCreators.openModal(React.createElement(DeregisterPlatformConfirmation, { platform: platform }));
    },
    render: function render() {
        var platforms;

        if (!this.state.platforms) {
            platforms = React.createElement(
                'p',
                null,
                'Loading platforms...'
            );
        } else if (!this.state.platforms.length) {
            platforms = React.createElement(
                'p',
                null,
                'No platforms found.'
            );
        } else {
            platforms = this.state.platforms.sort(function (a, b) {
                if (a.name.toLowerCase() > b.name.toLowerCase()) {
                    return 1;
                }
                if (a.name.toLowerCase() < b.name.toLowerCase()) {
                    return -1;
                }
                return 0;
            }).map(function (platform) {
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

                return React.createElement(
                    'div',
                    {
                        key: platform.uuid,
                        className: 'view__item view__item--list'
                    },
                    React.createElement(
                        'h3',
                        null,
                        React.createElement(
                            Router.Link,
                            {
                                to: "platform/" + platform.uuid
                            },
                            platform.name
                        )
                    ),
                    React.createElement(
                        'button',
                        {
                            className: 'deregister-platform',
                            onClick: this._onDeregisterClick.bind(this, platform),
                            title: 'Deregister platform'
                        },
                        '×'
                    ),
                    React.createElement(
                        'code',
                        null,
                        status.join(' | ')
                    )
                );
            }, this);
        }

        return React.createElement(
            'div',
            { className: 'view' },
            React.createElement(
                'div',
                { className: 'absolute_anchor' },
                React.createElement(
                    'h2',
                    null,
                    'Platforms'
                ),
                React.createElement(
                    'div',
                    { className: 'view__actions' },
                    React.createElement(
                        'button',
                        { className: 'button', onClick: this._onRegisterClick },
                        'Register platform'
                    )
                ),
                platforms
            )
        );
    }
});

function getStateFromStores() {
    return {
        platforms: platformsStore.getPlatforms()
    };
}

module.exports = Platforms;

},{"../action-creators/modal-action-creators":5,"../components/deregister-platform-confirmation":26,"../components/register-platform-form":44,"../stores/platforms-store":65,"react":undefined,"react-router":undefined}],43:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

var PreviewRegistryForm = function (_BaseComponent) {
    _inherits(PreviewRegistryForm, _BaseComponent);

    function PreviewRegistryForm(props) {
        _classCallCheck(this, PreviewRegistryForm);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(PreviewRegistryForm).call(this, props));

        _this._bind("_toggleLayout", "_updateFileName", "_onSubmit");

        _this.state = {};
        _this.state.csvlayout = true;
        _this.state.fileName = "";
        return _this;
    }

    _createClass(PreviewRegistryForm, [{
        key: '_toggleLayout',
        value: function _toggleLayout(itemKey) {

            this.setState({ csvlayout: !this.state.csvlayout });
        }
    }, {
        key: '_updateFileName',
        value: function _updateFileName(e) {

            this.setState({ fileName: e.target.value });
        }
    }, {
        key: '_onCancelClick',
        value: function _onCancelClick(e) {
            modalActionCreators.closeModal();
        }
    }, {
        key: '_onSubmit',
        value: function _onSubmit(e) {
            e.preventDefault();
            modalActionCreators.closeModal();
            this.props.onsaveregistry();
        }
    }, {
        key: 'render',
        value: function render() {

            var content;

            var layoutToggle;

            if (this.state.csvlayout) {
                layoutToggle = _react2.default.createElement(
                    'div',
                    { className: 'displayBlock' },
                    _react2.default.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        'csv'
                    ),
                    ' / ',
                    _react2.default.createElement(
                        'div',
                        { className: 'form__link inlineBlock',
                            onClick: this._toggleLayout },
                        _react2.default.createElement(
                            'a',
                            null,
                            'table'
                        )
                    )
                );

                var attributes = [];

                var headerRow = [];

                this.props.attributes[0].forEach(function (item, index) {
                    headerRow.push(item.label);
                });

                attributes.push(_react2.default.createElement(
                    'span',
                    { key: "header-" + this.props.deviceId },
                    headerRow.join()
                ));
                attributes.push(_react2.default.createElement('br', { key: "br-header-" + this.props.deviceId }));

                this.props.attributes.forEach(function (attributeRow, rowIndex) {

                    var newRow = [];

                    attributeRow.forEach(function (columnCell, columnIndex) {
                        newRow.push(columnCell.value);
                    });

                    attributes.push(_react2.default.createElement(
                        'span',
                        { key: "row-" + rowIndex + "-" + this.props.deviceId },
                        newRow.join()
                    ));
                    attributes.push(_react2.default.createElement('br', { key: "br-" + rowIndex + "-" + this.props.deviceId }));
                }, this);

                content = _react2.default.createElement(
                    'div',
                    null,
                    attributes
                );
            } else {
                layoutToggle = _react2.default.createElement(
                    'div',
                    { className: 'displayBlock' },
                    _react2.default.createElement(
                        'div',
                        { className: 'form__link inlineBlock',
                            onClick: this._toggleLayout },
                        _react2.default.createElement(
                            'a',
                            null,
                            'csv'
                        )
                    ),
                    ' / ',
                    _react2.default.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        'table'
                    )
                );

                var headerRow = this.props.attributes[0].map(function (item, index) {

                    return _react2.default.createElement(
                        'th',
                        { key: item.key + "-header-" + index },
                        item.label
                    );
                });

                var attributes = this.props.attributes.map(function (attributeRow, rowIndex) {

                    var attributeCells = attributeRow.map(function (columnCell, columnIndex) {

                        return _react2.default.createElement(
                            'td',
                            { key: columnCell.key + "-cell-" + rowIndex + "-" + columnIndex },
                            columnCell.value
                        );
                    });

                    var registryRow = _react2.default.createElement(
                        'tr',
                        { key: this.props.deviceId + "-row-" + rowIndex },
                        attributeCells
                    );

                    return registryRow;
                }, this);

                content = _react2.default.createElement(
                    'table',
                    null,
                    _react2.default.createElement(
                        'thead',
                        null,
                        _react2.default.createElement(
                            'tr',
                            null,
                            headerRow
                        )
                    ),
                    _react2.default.createElement(
                        'tbody',
                        null,
                        attributes
                    )
                );
            }

            return _react2.default.createElement(
                'form',
                { className: 'preview-registry-form', onSubmit: this._onSubmit },
                _react2.default.createElement(
                    'h1',
                    null,
                    'Save this registry configuration?'
                ),
                _react2.default.createElement(
                    'h4',
                    null,
                    this.props.deviceAddress,
                    ' / ',
                    this.props.deviceName,
                    ' / ',
                    this.props.deviceId
                ),
                layoutToggle,
                content,
                _react2.default.createElement('br', null),
                _react2.default.createElement(
                    'div',
                    { className: 'displayBlock' },
                    _react2.default.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        'CSV File Name: '
                    ),
                    ' ',
                    _react2.default.createElement(
                        'div',
                        { className: 'inlineBlock' },
                        _react2.default.createElement('input', {
                            onChange: this._updateFileName,
                            value: this.state.fileName,
                            type: 'text' })
                    )
                ),
                _react2.default.createElement(
                    'div',
                    { className: 'form__actions' },
                    _react2.default.createElement(
                        'button',
                        {
                            className: 'button button--secondary',
                            type: 'button',
                            onClick: this._onCancelClick
                        },
                        'Cancel'
                    ),
                    _react2.default.createElement(
                        'button',
                        {
                            className: 'button',
                            disabled: this.state.fileName === "" },
                        'Save'
                    )
                )
            );
        }
    }]);

    return PreviewRegistryForm;
}(_baseComponent2.default);

;

exports.default = PreviewRegistryForm;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"./base-component":12,"react":undefined}],44:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var RegisterPlatformForm = React.createClass({
    displayName: 'RegisterPlatformForm',

    getInitialState: function getInitialState() {
        var state = {};

        state.method = 'discovery';
        state.registering = false;

        state.name = state.discovery_address = state.ipaddress = state.serverKey = state.publicKey = state.secretKey = '';
        state.protocol = 'tcp';

        return state;
    },
    _onNameChange: function _onNameChange(e) {
        this.setState({ name: e.target.value });
    },
    _onAddressChange: function _onAddressChange(e) {
        this.setState({ ipaddress: e.target.value });
        this.setState({ discovery_address: e.target.value });
    },
    _onProtocolChange: function _onProtocolChange(e) {
        this.setState({ protocol: e.target.value });
    },
    _onServerKeyChange: function _onServerKeyChange(e) {
        this.setState({ serverKey: e.target.value });
    },
    _onPublicKeyChange: function _onPublicKeyChange(e) {
        this.setState({ publicKey: e.target.value });
    },
    _onSecretKeyChange: function _onSecretKeyChange(e) {
        this.setState({ secretKey: e.target.value });
    },
    _toggleMethod: function _toggleMethod(e) {
        this.setState({ method: this.state.method === "discovery" ? "advanced" : "discovery" });
    },
    _onCancelClick: function _onCancelClick(e) {
        this.setState({ registering: false });
        modalActionCreators.closeModal();
    },
    _onSubmit: function _onSubmit(e) {
        e.preventDefault();
        var address = this.state.method === "discovery" ? this.state.discovery_address : this._formatAddress();

        this.setState({ registering: true });
        platformManagerActionCreators.registerPlatform(this.state.name, address, this.state.method);
    },
    _formatAddress: function _formatAddress() {

        var fullAddress = this.state.protocol + "://" + this.state.ipaddress;

        if (this.state.serverKey) {
            fullAddress = fullAddress + "?serverkey=" + this.state.serverKey;
        }

        if (this.state.publicKey) {
            fullAddress = fullAddress + "&publickey=" + this.state.publicKey;
        }

        if (this.state.secretKey) {
            fullAddress = fullAddress + "&secretkey=" + this.state.secretKey;
        }

        return fullAddress;
    },
    render: function render() {

        var fullAddress = this._formatAddress();

        var registerForm;

        var submitMethod;

        var progress;

        if (this.state.registering) {
            var progressStyle = {
                textAlign: "center",
                width: "100%"
            };
            progress = React.createElement(
                'div',
                { style: progressStyle },
                React.createElement('progress', null)
            );
        }

        switch (this.state.method) {
            case "discovery":
                registerForm = React.createElement(
                    'div',
                    null,
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv firstCell' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Name'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block inputField',
                                    type: 'text',
                                    onChange: this._onNameChange,
                                    value: this.state.name,
                                    autoFocus: true,
                                    required: true
                                })
                            ),
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '70%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Address'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block inputField',
                                    type: 'text',
                                    onChange: this._onAddressChange,
                                    value: this.state.discovery_address,
                                    required: true
                                })
                            )
                        )
                    ),
                    progress,
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv firstCell' },
                                React.createElement(
                                    'div',
                                    { className: 'form__link',
                                        onClick: this._toggleMethod },
                                    React.createElement(
                                        'a',
                                        null,
                                        'Advanced'
                                    )
                                )
                            ),
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '70%' },
                                React.createElement(
                                    'div',
                                    { className: 'form__actions' },
                                    React.createElement(
                                        'button',
                                        {
                                            className: 'button button--secondary',
                                            type: 'button',
                                            onClick: this._onCancelClick
                                        },
                                        'Cancel'
                                    ),
                                    React.createElement(
                                        'button',
                                        {
                                            className: 'button',
                                            disabled: !this.state.name || !this.state.discovery_address
                                        },
                                        'Register'
                                    )
                                )
                            )
                        )
                    )
                );
                break;
            case "advanced":

                registerForm = React.createElement(
                    'div',
                    null,
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv firstCell' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Name'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block',
                                    type: 'text',
                                    onChange: this._onNameChange,
                                    value: this.state.name,
                                    autoFocus: true,
                                    required: true
                                })
                            ),
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '10%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Protocol'
                                ),
                                React.createElement('br', null),
                                React.createElement(
                                    'select',
                                    {
                                        className: 'form__control',
                                        onChange: this._onProtocolChange,
                                        value: this.state.protocol,
                                        required: true
                                    },
                                    React.createElement(
                                        'option',
                                        { value: 'tcp' },
                                        'TCP'
                                    ),
                                    React.createElement(
                                        'option',
                                        { value: 'ipc' },
                                        'IPC'
                                    )
                                )
                            ),
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '56%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'VIP address'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block',
                                    type: 'text',
                                    onChange: this._onAddressChange,
                                    value: this.state.ipaddress,
                                    required: true
                                })
                            )
                        )
                    ),
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '80%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Server Key'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block',
                                    type: 'text',
                                    onChange: this._onServerKeyChange,
                                    value: this.state.serverKey
                                })
                            )
                        )
                    ),
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '80%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Public Key'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block',
                                    type: 'text',
                                    onChange: this._onPublicKeyChange,
                                    value: this.state.publicKey
                                })
                            )
                        )
                    ),
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '80%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Secret Key'
                                ),
                                React.createElement('input', {
                                    className: 'form__control form__control--block',
                                    type: 'text',
                                    onChange: this._onSecretKeyChange,
                                    value: this.state.secretKey
                                })
                            )
                        )
                    ),
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '100%' },
                                React.createElement(
                                    'label',
                                    { className: 'formLabel' },
                                    'Preview'
                                ),
                                React.createElement(
                                    'div',
                                    {
                                        className: 'preview' },
                                    fullAddress
                                )
                            )
                        )
                    ),
                    progress,
                    React.createElement(
                        'div',
                        { className: 'tableDiv' },
                        React.createElement(
                            'div',
                            { className: 'rowDiv' },
                            React.createElement(
                                'div',
                                { className: 'cellDiv firstCell' },
                                React.createElement(
                                    'div',
                                    { className: 'form__link',
                                        onClick: this._toggleMethod },
                                    React.createElement(
                                        'a',
                                        null,
                                        'Discover'
                                    )
                                )
                            ),
                            React.createElement(
                                'div',
                                { className: 'cellDiv',
                                    width: '70%' },
                                React.createElement(
                                    'div',
                                    { className: 'form__actions' },
                                    React.createElement(
                                        'button',
                                        {
                                            className: 'button button--secondary',
                                            type: 'button',
                                            onClick: this._onCancelClick
                                        },
                                        'Cancel'
                                    ),
                                    React.createElement(
                                        'button',
                                        {
                                            className: 'button',
                                            disabled: !this.state.name || !this.state.protocol || !this.state.ipaddress || !(this.state.serverKey && this.state.publicKey && this.state.secretKey || !this.state.publicKey && !this.state.secretKey)
                                        },
                                        'Register'
                                    )
                                )
                            )
                        )
                    )
                );
                break;
        }

        return React.createElement(
            'form',
            { className: 'register-platform-form', onSubmit: this._onSubmit },
            React.createElement(
                'h1',
                null,
                'Register platform'
            ),
            registerForm
        );
    }
});

module.exports = RegisterPlatformForm;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-manager-action-creators":8,"react":undefined}],45:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _baseComponent = require('./base-component');

var _baseComponent2 = _interopRequireDefault(_baseComponent);

var _editPointForm = require('./edit-point-form');

var _editPointForm2 = _interopRequireDefault(_editPointForm);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }
// import PureRenderMixin from 'react-addons-pure-render-mixin';


var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');

var registryWs, registryWebsocket;

var RegistryRow = function (_BaseComponent) {
    _inherits(RegistryRow, _BaseComponent);

    function RegistryRow(props) {
        _classCallCheck(this, RegistryRow);

        var _this = _possibleConstructorReturn(this, Object.getPrototypeOf(RegistryRow).call(this, props));

        _this._bind('_updateCell', '_showProps', '_handleRowClick', '_selectForDelete', '_grabResizeHandle');

        _this.state = _this._resetState(_this.props);

        // this.shouldComponentUpdate = PureRenderMixin.shouldComponentUpdate.bind(this);
        return _this;
    }

    _createClass(RegistryRow, [{
        key: 'componentDidMount',
        value: function componentDidMount() {}
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {}
    }, {
        key: 'componentWillReceiveProps',
        value: function componentWillReceiveProps(nextProps) {
            if (!this.props.attributesList.equals(nextProps.attributesList) || this.props.allSelected !== nextProps.allSelected) {
                var newState = this._resetState(nextProps, this.props.allSelected !== nextProps.allSelected);
                this.setState(newState);
            }
        }
    }, {
        key: 'shouldComponentUpdate',
        value: function shouldComponentUpdate(nextProps, nextState) {
            var doUpdate = false;

            if (!this.state.attributesList.equals(nextState.attributesList) || this.state.selectedForDelete !== nextState.selectedForDelete) {
                doUpdate = true;
                console.log("state's not equal");
            } else {
                doUpdate = !this.props.immutableProps.equals(nextProps.immutableProps);

                if (doUpdate) {
                    console.log("immutable props not equal");
                }
            }

            return doUpdate;
        }
    }, {
        key: '_resetState',
        value: function _resetState(props, updateAllSelected) {
            var state = {};

            state.attributesList = props.attributesList;

            state.deviceId = this.props.immutableProps.get("deviceId");
            state.deviceAddress = this.props.immutableProps.get("deviceAddress");
            state.rowIndex = this.props.immutableProps.get("rowIndex");

            state.devicePrefix = "dvc" + state.deviceId + "-" + state.deviceAddress + "-" + state.rowIndex + "-";

            if (updateAllSelected) {
                state.selectedForDelete = props.allSelected;
            } else {
                state.selectedForDelete = false;
            }

            return state;
        }
    }, {
        key: '_updateCell',
        value: function _updateCell(column, e) {

            var currentTarget = e.currentTarget;

            var newValues = this.state.attributesList.updateIn(["attributes", column, "value"], function (item) {

                return currentTarget.value;
            });

            this.setState({ attributesList: newValues });
        }
    }, {
        key: '_showProps',
        value: function _showProps(attributesList) {

            devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));

            modalActionCreators.openModal(_react2.default.createElement(_editPointForm2.default, {
                deviceId: this.props.immutableProps.get("deviceId"),
                deviceAddress: this.props.immutableProps.get("deviceAddress"),
                attributes: this.state.attributesList.get("attributes") }));
        }
    }, {
        key: '_selectForDelete',
        value: function _selectForDelete() {
            devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));
            this.setState({ selectedForDelete: !this.state.selectedForDelete });

            this.props.oncheckselect(this.state.attributesList.getIn(["attributes", 0]).value);
        }
    }, {
        key: '_handleRowClick',
        value: function _handleRowClick(evt) {

            if (evt.target.nodeName !== "INPUT" && evt.target.nodeName !== "I" && evt.target.nodeName !== "DIV") {
                devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));

                if (!this.state.attributesList.get("selected")) {
                    var attributesList = this.state.attributesList.set("selected", true);
                    this.setState({ attributesList: attributesList });
                }
            }
        }
    }, {
        key: '_grabResizeHandle',
        value: function _grabResizeHandle(columnIndex, evt) {
            var target = evt.target;

            var targetColumn = this.refs[this.state.devicePrefix + columnIndex];

            var onMouseMove = function onMouseMove(evt) {
                // console.log(evt.clientX);
            };

            var onMouseUp = function (evt) {
                var clientRect = targetColumn.getClientRects();

                var targetWidth = evt.clientX - clientRect[0].left;

                this.props.onresizecolumn(columnIndex, targetWidth + "px");

                document.removeEventListener("mousemove", onMouseMove);
                document.removeEventListener("mouseup", onMouseUp);
            }.bind(this);

            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);

            evt.preventDefault();
        }
    }, {
        key: 'render',
        value: function render() {

            var registryCells = [];
            var rowIndex = this.props.immutableProps.get("rowIndex");

            this.state.attributesList.get("attributes").forEach(function (item, columnIndex) {

                if (item.keyProp) {
                    var selectedCellStyle = item.selected ? { backgroundColor: "#F5B49D", width: "100%" } : { width: "100%" };
                    var focusedCell = this.props.immutableProps.get("selectedCellColumn") === columnIndex && this.props.immutableProps.get("selectedCell") ? "focusedCell" : "";

                    var itemCell = !item.editable ? _react2.default.createElement(
                        'td',
                        { key: item.key + "-" + rowIndex + "-" + columnIndex,
                            ref: this.state.devicePrefix + columnIndex },
                        _react2.default.createElement(
                            'label',
                            null,
                            item.value
                        )
                    ) : _react2.default.createElement(
                        'td',
                        { key: item.key + "-" + rowIndex + "-" + columnIndex,
                            ref: this.state.devicePrefix + columnIndex },
                        _react2.default.createElement('input', {
                            id: this.state.attributesList.get("attributes").get(columnIndex).key + "-" + columnIndex + "-" + rowIndex,
                            type: 'text',
                            className: focusedCell,
                            style: selectedCellStyle,
                            onChange: this._updateCell.bind(this, columnIndex),
                            value: this.state.attributesList.get("attributes").get(columnIndex).value })
                    );

                    registryCells.push(itemCell);

                    if (columnIndex + 1 < this.state.attributesList.get("attributes").size) {
                        var resizeHandle = _react2.default.createElement('td', {
                            className: 'resize-handle-td',
                            onMouseDown: this._grabResizeHandle.bind(this, columnIndex) });
                        registryCells.push(resizeHandle);
                    }
                }
            }, this);

            registryCells.push(_react2.default.createElement(
                'td',
                { key: "propsButton-" + rowIndex },
                _react2.default.createElement(
                    'div',
                    { className: 'propsButton',
                        onClick: this._showProps.bind(this, this.state.attributesList.get("attributes")) },
                    _react2.default.createElement('i', { className: 'fa fa-ellipsis-h' })
                )
            ));

            var selectedRowClasses = [];

            if (this.state.attributesList.get("selected")) {
                selectedRowClasses.push("selectedRegistryPoint");
            }

            if (this.props.immutableProps.get("keyboardSelected")) {
                selectedRowClasses.push("keyboard-selected");
            }

            console.log("row " + rowIndex + " visible is " + this.state.attributesList.get("visible"));

            var visibleStyle = !this.props.immutableProps.get("filterOn") || this.state.attributesList.get("visible") ? {} : { display: "none" };

            return _react2.default.createElement(
                'tr',
                { key: "registry-row-" + rowIndex,
                    'data-row': rowIndex,
                    onClick: this._handleRowClick,
                    className: selectedRowClasses.join(" "),
                    style: visibleStyle },
                _react2.default.createElement(
                    'td',
                    { key: "checkbox-" + rowIndex },
                    _react2.default.createElement('input', { type: 'checkbox',
                        onChange: this._selectForDelete,
                        checked: this.state.selectedForDelete })
                ),
                registryCells
            );
        }
    }]);

    return RegistryRow;
}(_baseComponent2.default);

;

function objectIsEmpty(obj) {
    return Object.keys(obj).length === 0;
}

exports.default = RegistryRow;

},{"../action-creators/devices-action-creators":4,"../action-creators/modal-action-creators":5,"../action-creators/status-indicator-action-creators":10,"../stores/devices-store":60,"./base-component":12,"./edit-point-form":28,"react":undefined}],46:[function(require,module,exports){
'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');

var RemoveAgentForm = React.createClass({
    displayName: 'RemoveAgentForm',

    getInitialState: function getInitialState() {
        var state = {};

        for (var prop in this.props.agent) {
            state[prop] = this.props.agent[prop];
        }

        return state;
    },
    _onPropChange: function _onPropChange(e) {
        var state = {};

        this.setState(state);
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function _onSubmit(e) {
        e.preventDefault();
        platformActionCreators.removeAgent(this.props.platform, this.props.agent);
    },
    render: function render() {

        var removeMsg = 'Remove agent ' + this.props.agent.uuid + ' (' + this.props.agent.name + ', ' + this.props.agent.tag + ')?';

        return React.createElement(
            'form',
            { className: 'remove-agent-form', onSubmit: this._onSubmit },
            React.createElement(
                'div',
                null,
                removeMsg
            ),
            React.createElement(
                'div',
                { className: 'form__actions' },
                React.createElement(
                    'button',
                    {
                        className: 'button button--secondary',
                        type: 'button',
                        onClick: this._onCancelClick
                    },
                    'Cancel'
                ),
                React.createElement(
                    'button',
                    {
                        className: 'button',
                        type: 'submit',
                        disabled: !this.props.agent.uuid
                    },
                    'Remove'
                )
            )
        );
    }
});

module.exports = RemoveAgentForm;

},{"../action-creators/modal-action-creators":5,"../action-creators/platform-action-creators":6,"react":undefined}],47:[function(require,module,exports){
'use strict';

var React = require('react');

var statusIndicatorCreators = require('../action-creators/status-indicator-action-creators');
var statusIndicatorStore = require('../stores/status-indicator-store');

var StatusIndicator = React.createClass({
    displayName: 'StatusIndicator',


    getInitialState: function getInitialState() {
        var state = statusIndicatorStore.getStatusMessage();

        state.errors = state.status === "error";
        state.fadeOut = false;

        return state;
    },
    componentDidMount: function componentDidMount() {
        if (!this.state.errors) {
            this.fadeTimer = setTimeout(this._fadeForClose, 4000);
            this.closeTimer = setTimeout(this._autoCloseOnSuccess, 5000);
        }
    },
    _fadeForClose: function _fadeForClose() {
        this.setState({ fadeOut: true });
    },
    _keepVisible: function _keepVisible(evt) {
        if (this.fadeTimer) {
            this.setState({ fadeOut: false });

            clearTimeout(this.fadeTimer);
            clearTimeout(this.closeTimer);

            evt.currentTarget.addEventListener("mouseleave", this._closeOnMouseOut);
        }
    },
    _closeOnMouseOut: function _closeOnMouseOut() {
        if (!this.state.errors) {
            this.fadeTimer = setTimeout(this._fadeForClose, 0);
            this.closeTimer = setTimeout(this._autoCloseOnSuccess, 1000);
        }
    },
    _autoCloseOnSuccess: function _autoCloseOnSuccess() {
        statusIndicatorCreators.closeStatusIndicator();
    },
    _onCloseClick: function _onCloseClick() {
        statusIndicatorCreators.closeStatusIndicator();
    },

    render: function render() {
        var classes = ["status-indicator"];

        var green = "#35B809";
        var red = "#FC0516";

        var displayButton = "none";
        var color = green;

        if (this.state.errors) {
            displayButton = "block";
            color = red;
        } else if (this.state.fadeOut) {
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
        };

        var buttonDivStyle = {
            width: "100%",
            height: "3rem",
            display: displayButton
        };

        var spacerStyle = {
            width: "100%",
            height: "2rem"
        };

        var messageStyle = {
            padding: "0px 20px"
        };

        var statusMessage = React.createElement(
            'b',
            null,
            this.state.statusMessage
        );

        if (this.state.hasOwnProperty("highlight")) {
            var highlight = this.state.highlight;
            var wholeMessage = this.state.statusMessage;

            var startIndex = wholeMessage.indexOf(highlight);

            if (startIndex > -1) {
                var newMessage = [];

                if (startIndex === 0) {
                    newMessage.push(React.createElement(
                        'b',
                        { key: 'b1' },
                        wholeMessage.substring(0, highlight.length)
                    ));
                    newMessage.push(React.createElement(
                        'span',
                        { key: 'span1' },
                        wholeMessage.substring(highlight.length)
                    ));
                } else {
                    newMessage.push(React.createElement(
                        'span',
                        { key: 'span1' },
                        wholeMessage.substring(0, startIndex)
                    ));
                    newMessage.push(React.createElement(
                        'b',
                        { key: 'b1' },
                        wholeMessage.substring(startIndex, startIndex + highlight.length)
                    ));
                    newMessage.push(React.createElement(
                        'span',
                        { key: 'span2' },
                        wholeMessage.substring(startIndex + highlight.length)
                    ));
                }

                statusMessage = newMessage;
            }
        }

        messageStyle.textAlign = this.state.hasOwnProperty("align") ? this.state.align : "left";

        return React.createElement(
            'div',
            {
                className: classes.join(' '),
                onMouseEnter: this._keepVisible
            },
            React.createElement('div', { style: colorStyle }),
            React.createElement('br', null),
            React.createElement(
                'div',
                { style: messageStyle },
                statusMessage
            ),
            React.createElement('div', { style: spacerStyle }),
            React.createElement(
                'div',
                { style: buttonDivStyle },
                React.createElement(
                    'button',
                    {
                        className: 'button',
                        style: buttonStyle,
                        onClick: this._onCloseClick
                    },
                    'Close'
                )
            )
        );
    }
});

module.exports = StatusIndicator;

},{"../action-creators/status-indicator-action-creators":10,"../stores/status-indicator-store":66,"react":undefined}],48:[function(require,module,exports){
'use strict';

var keyMirror = require('keymirror');

module.exports = keyMirror({
    HANDLE_KEY_DOWN: null,
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

    WILL_INITIALIZE_PLATFORMS: null,
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
    CHANGE_CHART_MIN: null,
    CHANGE_CHART_MAX: null,
    CHANGE_CHART_REFRESH: null,
    REFRESH_CHART: null,
    REMOVE_CHART: null,
    LOAD_CHARTS: null,
    REMOVE_PLATFORM_CHARTS: null,

    EXPAND_ALL: null,
    TOGGLE_ITEM: null,
    CHECK_ITEM: null,
    FILTER_ITEMS: null,

    CONFIGURE_DEVICES: null,
    FOCUS_ON_DEVICE: null,
    ADD_DEVICES: null,
    // SCAN_FOR_DEVICES: null,
    LISTEN_FOR_IAMS: null,
    DEVICE_DETECTED: null,
    POINT_RECEIVED: null,
    CANCEL_SCANNING: null,
    // LIST_DETECTED_DEVICES: null,
    CONFIGURE_DEVICE: null,
    TOGGLE_SHOW_POINTS: null,
    EDIT_REGISTRY: null,
    UPDATE_REGISTRY: null,
    LOAD_REGISTRY: null,
    // GENERATE_REGISTRY: null,
    CANCEL_REGISTRY: null,
    SAVE_REGISTRY: null,
    SAVE_CONFIG: null,

    // ADD_CONTROL_BUTTON: null,
    // REMOVE_CONTROL_BUTTON: null,
    TOGGLE_TAPTIP: null,
    HIDE_TAPTIP: null,
    SHOW_TAPTIP: null,
    CLEAR_BUTTON: null,

    RECEIVE_CHART_TOPICS: null
});

},{"keymirror":undefined}],49:[function(require,module,exports){
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

},{"../constants/action-types":48,"flux":undefined}],50:[function(require,module,exports){
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

},{}],51:[function(require,module,exports){
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
        request: exchange.request
    });

    exchange.promise = new xhr.Request({
        method: 'POST',
        url: '/jsonrpc',
        contentType: 'application/json',
        data: data,
        timeout: 60000
    }).finally(function () {
        exchange.completed = Date.now();
    }).then(function (response) {
        exchange.response = response;

        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_RESPONSE,
            exchange: exchange,
            response: response
        });

        if (response.error) {
            throw new RpcError(response.error);
        }

        return JSON.parse(JSON.stringify(response.result));
    }).catch(xhr.Error, function (error) {
        exchange.error = error;

        dispatcher.dispatch({
            type: ACTION_TYPES.FAIL_REQUEST,
            exchange: exchange,
            error: error
        });

        throw new RpcError(error);
    });
}

module.exports = RpcExchange;

},{"../../constants/action-types":48,"../../dispatcher":49,"../xhr":55,"./error":50,"node-uuid":undefined}],52:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange')
};

},{"./error":50,"./exchange":51}],53:[function(require,module,exports){
'use strict';

var EventEmitter = require('events').EventEmitter;

var CHANGE_EVENT = 'change';

function Store() {
    EventEmitter.call(this);
    this.setMaxListeners(0);
}
Store.prototype = EventEmitter.prototype;

Store.prototype.emitChange = function () {
    this.emit(CHANGE_EVENT);
};

Store.prototype.addChangeListener = function (callback) {
    this.on(CHANGE_EVENT, callback);
};

Store.prototype.removeChangeListener = function (callback) {
    this.removeListener(CHANGE_EVENT, callback);
};

module.exports = Store;

},{"events":undefined}],54:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;

},{}],55:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error')
};

},{"./error":54,"./request":56}],56:[function(require,module,exports){
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

},{"./error":54,"bluebird":undefined,"jquery":undefined}],57:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _authorization = sessionStorage.getItem('authorization');
var _username = sessionStorage.getItem('username');

var authorizationStore = new Store();

authorizationStore.getAuthorization = function () {
    return _authorization;
};

authorizationStore.getUsername = function () {
    return _username;
};

authorizationStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _authorization = action.authorization;
            _username = action.name;
            sessionStorage.setItem('authorization', _authorization);
            sessionStorage.setItem('username', _username);
            authorizationStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            authorizationStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _authorization = null;
            _username = null;
            sessionStorage.removeItem('authorization');
            sessionStorage.removeItem('username');
            authorizationStore.emitChange();
            break;
    }
});

module.exports = authorizationStore;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53}],58:[function(require,module,exports){
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

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53,"../stores/authorization-store":57}],59:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _controlButtons = {};

var controlButtonStore = new Store();

controlButtonStore.getTaptip = function (name) {

    var showTaptip = null;

    if (_controlButtons.hasOwnProperty([name])) {
        if (_controlButtons[name].hasOwnProperty("showTaptip")) {
            showTaptip = _controlButtons[name].showTaptip;
        }
    }

    return showTaptip;
};

controlButtonStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.TOGGLE_TAPTIP:

            var showTaptip;

            if (_controlButtons.hasOwnProperty(action.name)) {
                _controlButtons[action.name].showTaptip = showTaptip = !_controlButtons[action.name].showTaptip;
            } else {
                _controlButtons[action.name] = { "showTaptip": true };
                showTaptip = true;
            }

            if (showTaptip === true) {
                //close other taptips    
                for (var key in _controlButtons) {
                    if (key !== action.name) {
                        _controlButtons[key].showTaptip = false;
                    }
                }
            }

            controlButtonStore.emitChange();

            break;

        case ACTION_TYPES.HIDE_TAPTIP:

            if (_controlButtons.hasOwnProperty(action.name)) {
                if (_controlButtons[action.name].hasOwnProperty("showTaptip")) {
                    _controlButtons[action.name].showTaptip = false;
                }
            }

            controlButtonStore.emitChange();

            break;
    }
});

module.exports = controlButtonStore;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53,"../stores/authorization-store":57}],60:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');
var Immutable = require("immutable");

var devicesStore = new Store();

var _action = "get_scan_settings";
var _view = "Detect Devices";
var _device = null;
var _data = {};
var _backupData = {};
var _registryFiles = {};
var _backupFileName = {};
var _platform;
var _devices = [];
// var Device = Immutable.Record({
//     id: undefined,
//     name: undefined,
//     vendor_id: undefined,
//     address: undefined,
//     max_apdu_length: undefined,
//     segmentation_supported: undefined,
//     showPoints: undefined,
//     configuring: undefined,
//     platformUuid: undefined,
//     bacnetProxyUuid: undefined,
//     registryConfig: [],
//     keyProps: ["volttron_point_name", "units", "writable"],
//     selectedPoints: [],
//     items: [ 
//         { key: "address", label: "Address", value: undefined },  
//         { key: "deviceName", label: "Name", value: undefined },  
//         { key: "deviceDescription", label: "Description", value: undefined }, 
//         { key: "deviceId", label: "Device ID", value: undefined }, 
//         { key: "vendorId", label: "Vendor ID", value: undefined }, 
//         { key: "vendor", label: "Vendor", value: undefined },
//         { key: "type", label: "Type", value: "BACnet" }
//     ]
// });


var _newScan = false;
var _warnings = {};
var _keyboard = {
    device: null,
    active: false,
    cmd: null,
    started: false
};
var _focusedDevice = null;

var _placeHolders = Immutable.List([[{ "key": "Point_Name", "value": "", "editable": true }, { "key": "Volttron_Point_Name", "value": "" }, { "key": "Units", "value": "" }, { "key": "Units_Details", "value": "" }, { "key": "Writable", "value": "" }, { "key": "Starting_Value", "value": "" }, { "key": "Type", "value": "" }, { "key": "Notes", "value": "" }]]);

var vendorTable = {
    "0": "ASHRAE",
    "1": "NIST",
    "2": "The Trane Company",
    "3": "McQuay International",
    "4": "PolarSoft",
    "5": "Johnson Controls, Inc.",
    "6": "American Auto-Matrix",
    "7": "Siemens Schweiz AG (Formerly: Landis & Staefa Division Europe)",
    "8": "Delta Controls",
    "9": "Siemens Schweiz AG",
    "10": "Schneider Electric",
    "11": "TAC",
    "12": "Orion Analysis Corporation",
    "13": "Teletrol Systems Inc.",
    "14": "Cimetrics Technology",
    "15": "Cornell University",
    "16": "United Technologies Carrier",
    "17": "Honeywell Inc.",
    "18": "Alerton / Honeywell",
    "19": "TAC AB",
    "20": "Hewlett-Packard Company",
    "21": "Dorsette’s Inc.",
    "22": "Siemens Schweiz AG (Formerly: Cerberus AG)",
    "23": "York Controls Group",
    "24": "Automated Logic Corporation",
    "25": "CSI Control Systems International",
    "26": "Phoenix Controls Corporation",
    "27": "Innovex Technologies, Inc.",
    "28": "KMC Controls, Inc.",
    "29": "Xn Technologies, Inc.",
    "30": "Hyundai Information Technology Co., Ltd.",
    "31": "Tokimec Inc.",
    "32": "Simplex",
    "33": "North Building Technologies Limited",
    "34": "Notifier",
    "35": "Reliable Controls Corporation",
    "36": "Tridium Inc.",
    "37": "Sierra Monitor Corporation/FieldServer Technologies",
    "38": "Silicon Energy",
    "39": "Kieback & Peter GmbH & Co KG",
    "40": "Anacon Systems, Inc.",
    "41": "Systems Controls & Instruments, LLC",
    "42": "Acuity Brands Lighting, Inc.",
    "43": "Micropower Manufacturing",
    "44": "Matrix Controls",
    "45": "METALAIRE",
    "46": "ESS Engineering",
    "47": "Sphere Systems Pty Ltd.",
    "48": "Walker Technologies Corporation",
    "49": "H I Solutions, Inc.",
    "50": "MBS GmbH",
    "51": "SAMSON AG",
    "52": "Badger Meter Inc.",
    "53": "DAIKIN Industries Ltd.",
    "54": "NARA Controls Inc.",
    "55": "Mammoth Inc.",
    "56": "Liebert Corporation",
    "57": "SEMCO Incorporated",
    "58": "Air Monitor Corporation",
    "59": "TRIATEK, LLC",
    "60": "NexLight",
    "61": "Multistack",
    "62": "TSI Incorporated",
    "63": "Weather-Rite, Inc.",
    "64": "Dunham-Bush",
    "65": "Reliance Electric",
    "66": "LCS Inc.",
    "67": "Regulator Australia PTY Ltd.",
    "68": "Touch-Plate Lighting Controls",
    "69": "Amann GmbH",
    "70": "RLE Technologies",
    "71": "Cardkey Systems",
    "72": "SECOM Co., Ltd.",
    "73": "ABB Gebäudetechnik AG Bereich NetServ",
    "74": "KNX Association cvba",
    "75": "Institute of Electrical Installation Engineers of Japan (IEIEJ)",
    "76": "Nohmi Bosai, Ltd.",
    "77": "Carel S.p.A.",
    "78": "UTC Fire & Security España, S.L.",
    "79": "Hochiki Corporation",
    "80": "Fr. Sauter AG",
    "81": "Matsushita Electric Works, Ltd.",
    "82": "Mitsubishi Electric Corporation, Inazawa Works",
    "83": "Mitsubishi Heavy Industries, Ltd.",
    "84": "Xylem, Inc.",
    "85": "Yamatake Building Systems Co., Ltd.",
    "86": "The Watt Stopper, Inc.",
    "87": "Aichi Tokei Denki Co., Ltd.",
    "88": "Activation Technologies, LLC",
    "89": "Saia-Burgess Controls, Ltd.",
    "90": "Hitachi, Ltd.",
    "91": "Novar Corp./Trend Control Systems Ltd.",
    "92": "Mitsubishi Electric Lighting Corporation",
    "93": "Argus Control Systems, Ltd.",
    "94": "Kyuki Corporation",
    "95": "Richards-Zeta Building Intelligence, Inc.",
    "96": "Scientech R&D, Inc.",
    "97": "VCI Controls, Inc.",
    "98": "Toshiba Corporation",
    "99": "Mitsubishi Electric Corporation Air Conditioning & Refrigeration Systems Works",
    "100": "Custom Mechanical Equipment, LLC",
    "101": "ClimateMaster",
    "102": "ICP Panel-Tec, Inc.",
    "103": "D-Tek Controls",
    "104": "NEC Engineering, Ltd.",
    "105": "PRIVA BV",
    "106": "Meidensha Corporation",
    "107": "JCI Systems Integration Services",
    "108": "Freedom Corporation",
    "109": "Neuberger Gebäudeautomation GmbH",
    "110": "eZi Controls",
    "111": "Leviton Manufacturing",
    "112": "Fujitsu Limited",
    "113": "Emerson Network Power",
    "114": "S. A. Armstrong, Ltd.",
    "115": "Visonet AG",
    "116": "M&M Systems, Inc.",
    "117": "Custom Software Engineering",
    "118": "Nittan Company, Limited",
    "119": "Elutions Inc. (Wizcon Systems SAS)",
    "120": "Pacom Systems Pty., Ltd.",
    "121": "Unico, Inc.",
    "122": "Ebtron, Inc.",
    "123": "Scada Engine",
    "124": "AC Technology Corporation",
    "125": "Eagle Technology",
    "126": "Data Aire, Inc.",
    "127": "ABB, Inc.",
    "128": "Transbit Sp. z o. o.",
    "129": "Toshiba Carrier Corporation",
    "130": "Shenzhen Junzhi Hi-Tech Co., Ltd.",
    "131": "Tokai Soft",
    "132": "Blue Ridge Technologies",
    "133": "Veris Industries",
    "134": "Centaurus Prime",
    "135": "Sand Network Systems",
    "136": "Regulvar, Inc.",
    "137": "AFDtek Division of Fastek International Inc.",
    "138": "PowerCold Comfort Air Solutions, Inc.",
    "139": "I Controls",
    "140": "Viconics Electronics, Inc.",
    "141": "Yaskawa America, Inc.",
    "142": "DEOS control systems GmbH",
    "143": "Digitale Mess- und Steuersysteme AG",
    "144": "Fujitsu General Limited",
    "145": "Project Engineering S.r.l.",
    "146": "Sanyo Electric Co., Ltd.",
    "147": "Integrated Information Systems, Inc.",
    "148": "Temco Controls, Ltd.",
    "149": "Airtek International Inc.",
    "150": "Advantech Corporation",
    "151": "Titan Products, Ltd.",
    "152": "Regel Partners",
    "153": "National Environmental Product",
    "154": "Unitec Corporation",
    "155": "Kanden Engineering Company",
    "156": "Messner Gebäudetechnik GmbH",
    "157": "Integrated.CH",
    "158": "Price Industries",
    "159": "SE-Elektronic GmbH",
    "160": "Rockwell Automation",
    "161": "Enflex Corp.",
    "162": "ASI Controls",
    "163": "SysMik GmbH Dresden",
    "164": "HSC Regelungstechnik GmbH",
    "165": "Smart Temp Australia Pty. Ltd.",
    "166": "Cooper Controls",
    "167": "Duksan Mecasys Co., Ltd.",
    "168": "Fuji IT Co., Ltd.",
    "169": "Vacon Plc",
    "170": "Leader Controls",
    "171": "Cylon Controls, Ltd.",
    "172": "Compas",
    "173": "Mitsubishi Electric Building Techno-Service Co., Ltd.",
    "174": "Building Control Integrators",
    "175": "ITG Worldwide (M) Sdn Bhd",
    "176": "Lutron Electronics Co., Inc.",
    "177": "Cooper-Atkins Corporation",
    "178": "LOYTEC Electronics GmbH",
    "179": "ProLon",
    "180": "Mega Controls Limited",
    "181": "Micro Control Systems, Inc.",
    "182": "Kiyon, Inc.",
    "183": "Dust Networks",
    "184": "Advanced Building Automation Systems",
    "185": "Hermos AG",
    "186": "CEZIM",
    "187": "Softing",
    "188": "Lynxspring, Inc.",
    "189": "Schneider Toshiba Inverter Europe",
    "190": "Danfoss Drives A/S",
    "191": "Eaton Corporation",
    "192": "Matyca S.A.",
    "193": "Botech AB",
    "194": "Noveo, Inc.",
    "195": "AMEV",
    "196": "Yokogawa Electric Corporation",
    "197": "GFR Gesellschaft für Regelungstechnik",
    "198": "Exact Logic",
    "199": "Mass Electronics Pty Ltd dba Innotech Control Systems Australia",
    "200": "Kandenko Co., Ltd.",
    "201": "DTF, Daten-Technik Fries",
    "202": "Klimasoft, Ltd.",
    "203": "Toshiba Schneider Inverter Corporation",
    "204": "Control Applications, Ltd.",
    "205": "KDT Systems Co., Ltd.",
    "206": "Onicon Incorporated",
    "207": "Automation Displays, Inc.",
    "208": "Control Solutions, Inc.",
    "209": "Remsdaq Limited",
    "210": "NTT Facilities, Inc.",
    "211": "VIPA GmbH",
    "212": "TSC21 Association of Japan",
    "213": "Strato Automation",
    "214": "HRW Limited",
    "215": "Lighting Control & Design, Inc.",
    "216": "Mercy Electronic and Electrical Industries",
    "217": "Samsung SDS Co., Ltd",
    "218": "Impact Facility Solutions, Inc.",
    "219": "Aircuity",
    "220": "Control Techniques, Ltd.",
    "221": "OpenGeneral Pty., Ltd.",
    "222": "WAGO Kontakttechnik GmbH & Co. KG",
    "223": "Cerus Industrial",
    "224": "Chloride Power Protection Company",
    "225": "Computrols, Inc.",
    "226": "Phoenix Contact GmbH & Co. KG",
    "227": "Grundfos Management A/S",
    "228": "Ridder Drive Systems",
    "229": "Soft Device SDN BHD",
    "230": "Integrated Control Technology Limited",
    "231": "AIRxpert Systems, Inc.",
    "232": "Microtrol Limited",
    "233": "Red Lion Controls",
    "234": "Digital Electronics Corporation",
    "235": "Ennovatis GmbH",
    "236": "Serotonin Software Technologies, Inc.",
    "237": "LS Industrial Systems Co., Ltd.",
    "238": "Square D Company",
    "239": "S Squared Innovations, Inc.",
    "240": "Aricent Ltd.",
    "241": "EtherMetrics, LLC",
    "242": "Industrial Control Communications, Inc.",
    "243": "Paragon Controls, Inc.",
    "244": "A. O. Smith Corporation",
    "245": "Contemporary Control Systems, Inc.",
    "246": "Intesis Software SL",
    "247": "Ingenieurgesellschaft N. Hartleb mbH",
    "248": "Heat-Timer Corporation",
    "249": "Ingrasys Technology, Inc.",
    "250": "Costerm Building Automation",
    "251": "WILO SE",
    "252": "Embedia Technologies Corp.",
    "253": "Technilog",
    "254": "HR Controls Ltd. & Co. KG",
    "255": "Lennox International, Inc.",
    "256": "RK-Tec Rauchklappen-Steuerungssysteme GmbH & Co. KG",
    "257": "Thermomax, Ltd.",
    "258": "ELCON Electronic Control, Ltd.",
    "259": "Larmia Control AB",
    "260": "BACnet Stack at SourceForge",
    "261": "G4S Security Services A/S",
    "262": "Exor International S.p.A.",
    "263": "Cristal Controles",
    "264": "Regin AB",
    "265": "Dimension Software, Inc.",
    "266": "SynapSense Corporation",
    "267": "Beijing Nantree Electronic Co., Ltd.",
    "268": "Camus Hydronics Ltd.",
    "269": "Kawasaki Heavy Industries, Ltd.",
    "270": "Critical Environment Technologies",
    "271": "ILSHIN IBS Co., Ltd.",
    "272": "ELESTA Energy Control AG",
    "273": "KROPMAN Installatietechniek",
    "274": "Baldor Electric Company",
    "275": "INGA mbH",
    "276": "GE Consumer & Industrial",
    "277": "Functional Devices, Inc.",
    "278": "ESAC",
    "279": "M-System Co., Ltd.",
    "280": "Yokota Co., Ltd.",
    "281": "Hitranse Technology Co., LTD",
    "282": "Vigilent Corporation",
    "283": "Kele, Inc.",
    "284": "Opera Electronics, Inc.",
    "285": "Gentec",
    "286": "Embedded Science Labs, LLC",
    "287": "Parker Hannifin Corporation",
    "288": "MaCaPS International Limited",
    "289": "Link4 Corporation",
    "290": "Romutec Steuer-u. Regelsysteme GmbH",
    "291": "Pribusin, Inc.",
    "292": "Advantage Controls",
    "293": "Critical Room Control",
    "294": "LEGRAND",
    "295": "Tongdy Control Technology Co., Ltd.",
    "296": "ISSARO Integrierte Systemtechnik",
    "297": "Pro-Dev Industries",
    "298": "DRI-STEEM",
    "299": "Creative Electronic GmbH",
    "300": "Swegon AB",
    "301": "Jan Brachacek",
    "302": "Hitachi Appliances, Inc.",
    "303": "Real Time Automation, Inc.",
    "304": "ITEC Hankyu-Hanshin Co.",
    "305": "Cyrus E&M Engineering Co., Ltd.",
    "306": "Badger Meter",
    "307": "Cirrascale Corporation",
    "308": "Elesta GmbH Building Automation",
    "309": "Securiton",
    "310": "OSlsoft, Inc.",
    "311": "Hanazeder Electronic GmbH",
    "312": "Honeywell Security Deutschland, Novar GmbH",
    "313": "Siemens Industry, Inc.",
    "314": "ETM Professional Control GmbH",
    "315": "Meitav-tec, Ltd.",
    "316": "Janitza Electronics GmbH",
    "317": "MKS Nordhausen",
    "318": "De Gier Drive Systems B.V.",
    "319": "Cypress Envirosystems",
    "320": "SMARTron s.r.o.",
    "321": "Verari Systems, Inc.",
    "322": "K-W Electronic Service, Inc.",
    "323": "ALFA-SMART Energy Management",
    "324": "Telkonet, Inc.",
    "325": "Securiton GmbH",
    "326": "Cemtrex, Inc.",
    "327": "Performance Technologies, Inc.",
    "328": "Xtralis (Aust) Pty Ltd",
    "329": "TROX GmbH",
    "330": "Beijing Hysine Technology Co., Ltd",
    "331": "RCK Controls, Inc.",
    "332": "Distech Controls SAS",
    "333": "Novar/Honeywell",
    "334": "The S4 Group, Inc.",
    "335": "Schneider Electric",
    "336": "LHA Systems",
    "337": "GHM engineering Group, Inc.",
    "338": "Cllimalux S.A.",
    "339": "VAISALA Oyj",
    "340": "COMPLEX (Beijing) Technology, Co., LTD.",
    "341": "SCADAmetrics",
    "342": "POWERPEG NSI Limited",
    "343": "BACnet Interoperability Testing Services, Inc.",
    "344": "Teco a.s.",
    "345": "Plexus Technology, Inc.",
    "346": "Energy Focus, Inc.",
    "347": "Powersmiths International Corp.",
    "348": "Nichibei Co., Ltd.",
    "349": "HKC Technology Ltd.",
    "350": "Ovation Networks, Inc.",
    "351": "Setra Systems",
    "352": "AVG Automation",
    "353": "ZXC Ltd.",
    "354": "Byte Sphere",
    "355": "Generiton Co., Ltd.",
    "356": "Holter Regelarmaturen GmbH & Co. KG",
    "357": "Bedford Instruments, LLC",
    "358": "Standair Inc.",
    "359": "WEG Automation - R&D",
    "360": "Prolon Control Systems ApS",
    "361": "Inneasoft",
    "362": "ConneXSoft GmbH",
    "363": "CEAG Notlichtsysteme GmbH",
    "364": "Distech Controls Inc.",
    "365": "Industrial Technology Research Institute",
    "366": "ICONICS, Inc.",
    "367": "IQ Controls s.c.",
    "368": "OJ Electronics A/S",
    "369": "Rolbit Ltd.",
    "370": "Synapsys Solutions Ltd.",
    "371": "ACME Engineering Prod. Ltd.",
    "372": "Zener Electric Pty, Ltd.",
    "373": "Selectronix, Inc.",
    "374": "Gorbet & Banerjee, LLC.",
    "375": "IME",
    "376": "Stephen H. Dawson Computer Service",
    "377": "Accutrol, LLC",
    "378": "Schneider Elektronik GmbH",
    "379": "Alpha-Inno Tec GmbH",
    "380": "ADMMicro, Inc.",
    "381": "Greystone Energy Systems, Inc.",
    "382": "CAP Technologie",
    "383": "KeRo Systems",
    "384": "Domat Control System s.r.o.",
    "385": "Efektronics Pty. Ltd.",
    "386": "Hekatron Vertriebs GmbH",
    "387": "Securiton AG",
    "388": "Carlo Gavazzi Controls SpA",
    "389": "Chipkin Automation Systems",
    "390": "Savant Systems, LLC",
    "391": "Simmtronic Lighting Controls",
    "392": "Abelko Innovation AB",
    "393": "Seresco Technologies Inc.",
    "394": "IT Watchdogs",
    "395": "Automation Assist Japan Corp.",
    "396": "Thermokon Sensortechnik GmbH",
    "397": "EGauge Systems, LLC",
    "398": "Quantum Automation (ASIA) PTE, Ltd.",
    "399": "Toshiba Lighting & Technology Corp.",
    "400": "SPIN Engenharia de Automação Ltda.",
    "401": "Logistics Systems & Software Services India PVT. Ltd.",
    "402": "Delta Controls Integration Products",
    "403": "Focus Media",
    "404": "LUMEnergi Inc.",
    "405": "Kara Systems",
    "406": "RF Code, Inc.",
    "407": "Fatek Automation Corp.",
    "408": "JANDA Software Company, LLC",
    "409": "Open System Solutions Limited",
    "410": "Intelec Systems PTY Ltd.",
    "411": "Ecolodgix, LLC",
    "412": "Douglas Lighting Controls",
    "413": "iSAtech GmbH",
    "414": "AREAL",
    "415": "Beckhoff Automation GmbH",
    "416": "IPAS GmbH",
    "417": "KE2 Therm Solutions",
    "418": "Base2Products",
    "419": "DTL Controls, LLC",
    "420": "INNCOM International, Inc.",
    "421": "BTR Netcom GmbH",
    "422": "Greentrol Automation, Inc",
    "423": "BELIMO Automation AG",
    "424": "Samsung Heavy Industries Co, Ltd",
    "425": "Triacta Power Technologies, Inc.",
    "426": "Globestar Systems",
    "427": "MLB Advanced Media, LP",
    "428": "SWG Stuckmann Wirtschaftliche Gebäudesysteme GmbH",
    "429": "SensorSwitch",
    "430": "Multitek Power Limited",
    "431": "Aquametro AG",
    "432": "LG Electronics Inc.",
    "433": "Electronic Theatre Controls, Inc.",
    "434": "Mitsubishi Electric Corporation Nagoya Works",
    "435": "Delta Electronics, Inc.",
    "436": "Elma Kurtalj, Ltd.",
    "437": "ADT Fire and Security Sp. A.o.o.",
    "438": "Nedap Security Management",
    "439": "ESC Automation Inc.",
    "440": "DSP4YOU Ltd.",
    "441": "GE Sensing and Inspection Technologies",
    "442": "Embedded Systems SIA",
    "443": "BEFEGA GmbH",
    "444": "Baseline Inc.",
    "445": "M2M Systems Integrators",
    "446": "OEMCtrl",
    "447": "Clarkson Controls Limited",
    "448": "Rogerwell Control System Limited",
    "449": "SCL Elements",
    "450": "Hitachi Ltd.",
    "451": "Newron System SA",
    "452": "BEVECO Gebouwautomatisering BV",
    "453": "Streamside Solutions",
    "454": "Yellowstone Soft",
    "455": "Oztech Intelligent Systems Pty Ltd.",
    "456": "Novelan GmbH",
    "457": "Flexim Americas Corporation",
    "458": "ICP DAS Co., Ltd.",
    "459": "CARMA Industries Inc.",
    "460": "Log-One Ltd.",
    "461": "TECO Electric & Machinery Co., Ltd.",
    "462": "ConnectEx, Inc.",
    "463": "Turbo DDC Südwest",
    "464": "Quatrosense Environmental Ltd.",
    "465": "Fifth Light Technology Ltd.",
    "466": "Scientific Solutions, Ltd.",
    "467": "Controller Area Network Solutions (M) Sdn Bhd",
    "468": "RESOL - Elektronische Regelungen GmbH",
    "469": "RPBUS LLC",
    "470": "BRS Sistemas Eletronicos",
    "471": "WindowMaster A/S",
    "472": "Sunlux Technologies Ltd.",
    "473": "Measurlogic",
    "474": "Frimat GmbH",
    "475": "Spirax Sarco",
    "476": "Luxtron",
    "477": "Raypak Inc",
    "478": "Air Monitor Corporation",
    "479": "Regler Och Webbteknik Sverige (ROWS)",
    "480": "Intelligent Lighting Controls Inc.",
    "481": "Sanyo Electric Industry Co., Ltd",
    "482": "E-Mon Energy Monitoring Products",
    "483": "Digital Control Systems",
    "484": "ATI Airtest Technologies, Inc.",
    "485": "SCS SA",
    "486": "HMS Industrial Networks AB",
    "487": "Shenzhen Universal Intellisys Co Ltd",
    "488": "EK Intellisys Sdn Bhd",
    "489": "SysCom",
    "490": "Firecom, Inc.",
    "491": "ESA Elektroschaltanlagen Grimma GmbH",
    "492": "Kumahira Co Ltd",
    "493": "Hotraco",
    "494": "SABO Elektronik GmbH",
    "495": "Equip'Trans",
    "496": "TCS Basys Controls",
    "497": "FlowCon International A/S",
    "498": "ThyssenKrupp Elevator Americas",
    "499": "Abatement Technologies",
    "500": "Continental Control Systems, LLC",
    "501": "WISAG Automatisierungstechnik GmbH & Co KG",
    "502": "EasyIO",
    "503": "EAP-Electric GmbH",
    "504": "Hardmeier",
    "505": "Mircom Group of Companies",
    "506": "Quest Controls",
    "507": "Mestek, Inc",
    "508": "Pulse Energy",
    "509": "Tachikawa Corporation",
    "510": "University of Nebraska-Lincoln",
    "511": "Redwood Systems",
    "512": "PASStec Industrie-Elektronik GmbH",
    "513": "NgEK, Inc.",
    "514": "t-mac Technologies",
    "515": "Jireh Energy Tech Co., Ltd.",
    "516": "Enlighted Inc.",
    "517": "El-Piast Sp. Z o.o",
    "518": "NetxAutomation Software GmbH",
    "519": "Invertek Drives",
    "520": "Deutschmann Automation GmbH & Co. KG",
    "521": "EMU Electronic AG",
    "522": "Phaedrus Limited",
    "523": "Sigmatek GmbH & Co KG",
    "524": "Marlin Controls",
    "525": "Circutor, SA",
    "526": "UTC Fire & Security",
    "527": "DENT Instruments, Inc.",
    "528": "FHP Manufacturing Company - Bosch Group",
    "529": "GE Intelligent Platforms",
    "530": "Inner Range Pty Ltd",
    "531": "GLAS Energy Technology",
    "532": "MSR-Electronic-GmbH",
    "533": "Energy Control Systems, Inc.",
    "534": "EMT Controls",
    "535": "Daintree Networks Inc.",
    "536": "EURO ICC d.o.o",
    "537": "TE Connectivity Energy",
    "538": "GEZE GmbH",
    "539": "NEC Corporation",
    "540": "Ho Cheung International Company Limited",
    "541": "Sharp Manufacturing Systems Corporation",
    "542": "DOT CONTROLS a.s.",
    "543": "BeaconMedæs",
    "544": "Midea Commercial Aircon",
    "545": "WattMaster Controls",
    "546": "Kamstrup A/S",
    "547": "CA Computer Automation GmbH",
    "548": "Laars Heating Systems Company",
    "549": "Hitachi Systems, Ltd.",
    "550": "Fushan AKE Electronic Engineering Co., Ltd.",
    "551": "Toshiba International Corporation",
    "552": "Starman Systems, LLC",
    "553": "Samsung Techwin Co., Ltd.",
    "554": "ISAS-Integrated Switchgear and Systems P/L",
    "555": "Reserved for ASHRAE",
    "556": "Obvius",
    "557": "Marek Guzik",
    "558": "Vortek Instruments, LLC",
    "559": "Universal Lighting Technologies",
    "560": "Myers Power Products, Inc.",
    "561": "Vector Controls GmbH",
    "562": "Crestron Electronics, Inc.",
    "563": "A&E Controls Limited",
    "564": "Projektomontaza A.D.",
    "565": "Freeaire Refrigeration",
    "566": "Aqua Cooler Pty Limited",
    "567": "Basic Controls",
    "568": "GE Measurement and Control Solutions Advanced Sensors",
    "569": "EQUAL Networks",
    "570": "Millennial Net",
    "571": "APLI Ltd",
    "572": "Electro Industries/GaugeTech",
    "573": "SangMyung University",
    "574": "Coppertree Analytics, Inc.",
    "575": "CoreNetiX GmbH",
    "576": "Acutherm",
    "577": "Dr. Riedel Automatisierungstechnik GmbH",
    "578": "Shina System Co., Ltd",
    "579": "Iqapertus",
    "580": "PSE Technology",
    "581": "BA Systems",
    "582": "BTICINO",
    "583": "Monico, Inc.",
    "584": "iCue",
    "585": "tekmar Control Systems Ltd.",
    "586": "Control Technology Corporation",
    "587": "GFAE GmbH",
    "588": "BeKa Software GmbH",
    "589": "Isoil Industria SpA",
    "590": "Home Systems Consulting SpA",
    "591": "Socomec",
    "592": "Everex Communications, Inc.",
    "593": "Ceiec Electric Technology",
    "594": "Atrila GmbH",
    "595": "WingTechs",
    "596": "Shenzhen Mek Intellisys Pte Ltd.",
    "597": "Nestfield Co., Ltd.",
    "598": "Swissphone Telecom AG",
    "599": "PNTECH JSC",
    "600": "Horner APG, LLC",
    "601": "PVI Industries, LLC",
    "602": "Ela-compil",
    "603": "Pegasus Automation International LLC",
    "604": "Wight Electronic Services Ltd.",
    "605": "Marcom",
    "606": "Exhausto A/S",
    "607": "Dwyer Instruments, Inc.",
    "608": "Link GmbH",
    "609": "Oppermann Regelgerate GmbH",
    "610": "NuAire, Inc.",
    "611": "Nortec Humidity, Inc.",
    "612": "Bigwood Systems, Inc.",
    "613": "Enbala Power Networks",
    "614": "Inter Energy Co., Ltd.",
    "615": "ETC",
    "616": "COMELEC S.A.R.L",
    "617": "Pythia Technologies",
    "618": "TrendPoint Systems, Inc.",
    "619": "AWEX",
    "620": "Eurevia",
    "621": "Kongsberg E-lon AS",
    "622": "FlaktWoods",
    "623": "E + E Elektronik GES M.B.H.",
    "624": "ARC Informatique",
    "625": "SKIDATA AG",
    "626": "WSW Solutions",
    "627": "Trefon Electronic GmbH",
    "628": "Dongseo System",
    "629": "Kanontec Intelligence Technology Co., Ltd.",
    "630": "EVCO S.p.A.",
    "631": "Accuenergy (CANADA) Inc.",
    "632": "SoftDEL",
    "633": "Orion Energy Systems, Inc.",
    "634": "Roboticsware",
    "635": "DOMIQ Sp. z o.o.",
    "636": "Solidyne",
    "637": "Elecsys Corporation",
    "638": "Conditionaire International Pty. Limited",
    "639": "Quebec, Inc.",
    "640": "Homerun Holdings",
    "641": "Murata Americas",
    "642": "Comptek",
    "643": "Westco Systems, Inc.",
    "644": "Advancis Software & Services GmbH",
    "645": "Intergrid, LLC",
    "646": "Markerr Controls, Inc.",
    "647": "Toshiba Elevator and Building Systems Corporation",
    "648": "Spectrum Controls, Inc.",
    "649": "Mkservice",
    "650": "Fox Thermal Instruments",
    "651": "SyxthSense Ltd",
    "652": "DUHA System S R.O.",
    "653": "NIBE",
    "654": "Melink Corporation",
    "655": "Fritz-Haber-Institut",
    "656": "MTU Onsite Energy GmbH, Gas Power Systems",
    "657": "Omega Engineering, Inc.",
    "658": "Avelon",
    "659": "Ywire Technologies, Inc.",
    "660": "M.R. Engineering Co., Ltd.",
    "661": "Lochinvar, LLC",
    "662": "Sontay Limited",
    "663": "GRUPA Slawomir Chelminski",
    "664": "Arch Meter Corporation",
    "665": "Senva, Inc.",
    "666": "Reserved for ASHRAE",
    "667": "FM-Tec",
    "668": "Systems Specialists, Inc.",
    "669": "SenseAir",
    "670": "AB IndustrieTechnik Srl",
    "671": "Cortland Research, LLC",
    "672": "MediaView",
    "673": "VDA Elettronica",
    "674": "CSS, Inc.",
    "675": "Tek-Air Systems, Inc.",
    "676": "ICDT",
    "677": "The Armstrong Monitoring Corporation",
    "678": "DIXELL S.r.l",
    "679": "Lead System, Inc.",
    "680": "ISM EuroCenter S.A.",
    "681": "TDIS",
    "682": "Trade FIDES",
    "683": "Knürr GmbH (Emerson Network Power)",
    "684": "Resource Data Management",
    "685": "Abies Technology, Inc.",
    "686": "Amalva",
    "687": "MIRAE Electrical Mfg. Co., Ltd.",
    "688": "HunterDouglas Architectural Projects Scandinavia ApS",
    "689": "RUNPAQ Group Co., Ltd",
    "690": "Unicard SA",
    "691": "IE Technologies",
    "692": "Ruskin Manufacturing",
    "693": "Calon Associates Limited",
    "694": "Contec Co., Ltd.",
    "695": "iT GmbH",
    "696": "Autani Corporation",
    "697": "Christian Fortin",
    "698": "HDL",
    "699": "IPID Sp. Z.O.O Limited",
    "700": "Fuji Electric Co., Ltd",
    "701": "View, Inc.",
    "702": "Samsung S1 Corporation",
    "703": "New Lift",
    "704": "VRT Systems",
    "705": "Motion Control Engineering, Inc.",
    "706": "Weiss Klimatechnik GmbH",
    "707": "Elkon",
    "708": "Eliwell Controls S.r.l.",
    "709": "Japan Computer Technos Corp",
    "710": "Rational Network ehf",
    "711": "Magnum Energy Solutions, LLC",
    "712": "MelRok",
    "713": "VAE Group",
    "714": "LGCNS",
    "715": "Berghof Automationstechnik GmbH",
    "716": "Quark Communications, Inc.",
    "717": "Sontex",
    "718": "mivune AG",
    "719": "Panduit",
    "720": "Smart Controls, LLC",
    "721": "Compu-Aire, Inc.",
    "722": "Sierra",
    "723": "ProtoSense Technologies",
    "724": "Eltrac Technologies Pvt Ltd",
    "725": "Bektas Invisible Controls GmbH",
    "726": "Entelec",
    "727": "INNEXIV",
    "728": "Covenant",
    "729": "Davitor AB",
    "730": "TongFang Technovator",
    "731": "Building Robotics, Inc.",
    "732": "HSS-MSR UG",
    "733": "FramTack LLC",
    "734": "B. L. Acoustics, Ltd.",
    "735": "Traxxon Rock Drills, Ltd",
    "736": "Franke",
    "737": "Wurm GmbH & Co",
    "738": "AddENERGIE",
    "739": "Mirle Automation Corporation",
    "740": "Ibis Networks",
    "741": "ID-KARTA s.r.o.",
    "742": "Anaren, Inc.",
    "743": "Span, Incorporated",
    "744": "Bosch Thermotechnology Corp",
    "745": "DRC Technology S.A.",
    "746": "Shanghai Energy Building Technology Co, Ltd",
    "747": "Fraport AG",
    "748": "Flowgroup",
    "749": "Skytron Energy, GmbH",
    "750": "ALTEL Wicha, Golda Sp. J.",
    "751": "Drupal",
    "752": "Axiomatic Technology, Ltd",
    "753": "Bohnke + Partner",
    "754": "Function 1",
    "755": "Optergy Pty, Ltd",
    "756": "LSI Virticus",
    "757": "Konzeptpark GmbH",
    "758": "Hubbell Building Automation, Inc.",
    "759": "eCurv, Inc.",
    "760": "Agnosys GmbH",
    "761": "Shanghai Sunfull Automation Co., LTD",
    "762": "Kurz Instruments, Inc.",
    "763": "Cias Elettronica S.r.l.",
    "764": "Multiaqua, Inc.",
    "765": "BlueBox",
    "766": "Sensidyne",
    "767": "Viessmann Elektronik GmbH",
    "768": "ADFweb.com srl",
    "769": "Gaylord Industries",
    "770": "Majur Ltd.",
    "771": "Shanghai Huilin Technology Co., Ltd.",
    "772": "Exotronic",
    "773": "Safecontrol spol s.r.o.",
    "774": "Amatis",
    "775": "Universal Electric Corporation",
    "776": "iBACnet",
    "777": "Reserved for ASHRAE",
    "778": "Smartrise Engineering, Inc.",
    "779": "Miratron, Inc.",
    "780": "SmartEdge",
    "781": "Mitsubishi Electric Australia Pty Ltd",
    "782": "Triangle Research International Ptd Ltd",
    "783": "Produal Oy",
    "784": "Milestone Systems A/S",
    "785": "Trustbridge",
    "786": "Feedback Solutions",
    "787": "IES",
    "788": "GE Critical Power",
    "789": "Riptide IO",
    "790": "Messerschmitt Systems AG",
    "791": "Dezem Energy Controlling",
    "792": "MechoSystems",
    "793": "evon GmbH",
    "794": "CS Lab GmbH",
    "795": "8760 Enterprises, Inc.",
    "796": "Touche Controls",
    "797": "Ontrol Teknik Malzeme San. ve Tic. A.S.",
    "798": "Uni Control System Sp. Z o.o.",
    "799": "Weihai Ploumeter Co., Ltd",
    "800": "Elcom International Pvt. Ltd",
    "801": "Philips Lighting",
    "802": "AutomationDirect",
    "803": "Paragon Robotics",
    "804": "SMT System & Modules Technology AG",
    "805": "OS Technology Service and Trading Co., LTD",
    "806": "CMR Controls Ltd",
    "807": "Innovari, Inc.",
    "808": "ABB Control Products",
    "809": "Gesellschaft fur Gebäudeautomation mbH",
    "810": "RODI Systems Corp.",
    "811": "Nextek Power Systems",
    "812": "Creative Lighting",
    "813": "WaterFurnace International",
    "814": "Mercury Security",
    "815": "Hisense (Shandong) Air-Conditioning Co., Ltd.",
    "816": "Layered Solutions, Inc.",
    "817": "Leegood Automatic System, Inc.",
    "818": "Shanghai Restar Technology Co., Ltd.",
    "819": "Reimann Ingenieurbüro",
    "820": "LynTec",
    "821": "HTP",
    "822": "Elkor Technologies, Inc.",
    "823": "Bentrol Pty Ltd",
    "824": "Team-Control Oy",
    "825": "NextDevice, LLC",
    "826": "GLOBAL CONTROL 5 Sp. z o.o.",
    "827": "King I Electronics Co., Ltd",
    "828": "SAMDAV",
    "829": "Next Gen Industries Pvt. Ltd.",
    "830": "Entic LLC",
    "831": "ETAP",
    "832": "Moralle Electronics Limited",
    "833": "Leicom AG",
    "834": "Watts Regulator Company",
    "835": "S.C. Orbtronics S.R.L.",
    "836": "Gaussan Technologies",
    "837": "WEBfactory GmbH",
    "838": "Ocean Controls",
    "839": "Messana Air-Ray Conditioning s.r.l.",
    "840": "Hangzhou BATOWN Technology Co. Ltd.",
    "841": "Reasonable Controls",
    "842": "Servisys, Inc.",
    "843": "halstrup-walcher GmbH",
    "844": "SWG Automation Fuzhou Limited",
    "845": "KSB Aktiengesellschaft",
    "846": "Hybryd Sp. z o.o.",
    "847": "Helvatron AG",
    "848": "Oderon Sp. Z.O.O.",
    "849": "miko",
    "850": "Exodraft",
    "851": "Hochhuth GmbH",
    "852": "Integrated System Technologies Ltd.",
    "853": "Shanghai Cellcons Controls Co., Ltd",
    "854": "Emme Controls, LLC",
    "855": "Field Diagnostic Services, Inc.",
    "856": "Ges Teknik A.S.",
    "857": "Global Power Products, Inc.",
    "858": "Option NV",
    "859": "BV-Control AG",
    "860": "Sigren Engineering AG",
    "861": "Shanghai Jaltone Technology Co., Ltd.",
    "862": "MaxLine Solutions Ltd",
    "863": "Kron Instrumentos Elétricos Ltda",
    "864": "Thermo Matrix",
    "865": "Infinite Automation Systems, Inc.",
    "866": "Vantage",
    "867": "Elecon Measurements Pvt Ltd",
    "868": "TBA",
    "869": "Carnes Company",
    "870": "Harman Professional",
    "871": "Nenutec Asia Pacific Pte Ltd",
    "872": "Gia NV",
    "873": "Kepware Tehnologies",
    "874": "Temperature Electronics Ltd",
    "875": "Packet Power",
    "876": "Project Haystack Corporation",
    "877": "DEOS Controls Americas Inc.",
    "878": "Senseware Inc",
    "879": "MST Systemtechnik AG",
    "880": "Lonix Ltd",
    "881": "GMC-I Messtechnik GmbH",
    "882": "Aviosys International Inc.",
    "883": "Efficient Building Automation Corp.",
    "884": "Accutron Instruments Inc.",
    "885": "Vermont Energy Control Systems LLC",
    "886": "DCC Dynamics",
    "887": "Brück Electronic GmbH",
    "888": "Reserved for ASHRAE",
    "889": "NGBS Hungary Ltd.",
    "890": "ILLUM Technology, LLC",
    "891": "Delta Controls Germany Limited",
    "892": "S+T Service & Technique S.A.",
    "893": "SimpleSoft",
    "894": "Candi Controls, Inc.",
    "895": "EZEN Solution Inc.",
    "896": "Fujitec Co. Ltd.",
    "897": "Terralux",
    "898": "Annicom",
    "899": "Bihl+Wiedemann GmbH",
    "900": "Daper, Inc.",
    "901": "Schüco International KG",
    "902": "Otis Elevator Company",
    "903": "Fidelix Oy",
    "904": "RAM GmbH Mess- und Regeltechnik",
    "905": "WEMS",
    "906": "Ravel Electronics Pvt Ltd",
    "907": "OmniMagni",
    "908": "Echelon",
    "909": "Intellimeter Canada, Inc.",
    "910": "Bithouse Oy",
    "911": "Reserved for ASHRAE",
    "912": "BuildPulse",
    "913": "Shenzhen 1000 Building Automation Co. Ltd",
    "914": "AED Engineering GmbH",
    "915": "Güntner GmbH & Co. KG",
    "916": "KNXlogic",
    "917": "CIM Environmental Group",
    "918": "Flow Control",
    "919": "Lumen Cache, Inc.",
    "920": "Ecosystem",
    "921": "Potter Electric Signal Company, LLC",
    "922": "Tyco Fire & Security S.p.A.",
    "923": "Watanabe Electric Industry Co., Ltd.",
    "924": "Causam Energy",
    "925": "W-tec AG",
    "926": "IMI Hydronic Engineering International SA",
    "927": "ARIGO Software",
    "928": "MSA Safety",
    "929": "Smart Solucoes Ltda - MERCATO",
    "930": "PIATRA Engineering",
    "931": "ODIN Automation Systems, LLC",
    "932": "Belparts NV",
    "999": "Reserved for ASHRAE"
};

devicesStore.getState = function () {
    return { action: _action, view: _view, device: _device, platform: _platform };
};

devicesStore.getRegistryValues = function (device) {

    var device = devicesStore.getDeviceRef(device.id, device.address);
    var config = [];

    if (device) {
        if (device.registryConfig.length) {
            config = device.registryConfig;
        }
    } else {
        config = _placeHolders;
    }

    return config;
};

devicesStore.getDataLoaded = function (device) {
    return _data.hasOwnProperty(device.deviceId) && _data.hasOwnProperty(device.deviceId) ? _data[device.deviceId].length : false;
};

devicesStore.getRegistryFile = function (device) {

    return _registryFiles.hasOwnProperty(device.deviceId) && _data.hasOwnProperty(device.deviceId) && _data[device.deviceId].length ? _registryFiles[device.deviceId] : "";
};

devicesStore.getWarnings = function () {
    return _warnings;
};

devicesStore.getDevices = function (platform, bacnetUuid) {

    var devices = _devices.filter(function (device) {
        return device.platformUuid === platform.uuid && device.bacnetProxyUuid === bacnetUuid;
    });

    return JSON.parse(JSON.stringify(devices));
};

devicesStore.getDeviceByID = function (deviceId) {

    var device = _devices.find(function (dvc) {
        return dvc.id === deviceId;
    });

    return device;
};

devicesStore.getDeviceRef = function (deviceId, deviceAddress) {

    var device = _devices.find(function (dvc) {
        return dvc.id === deviceId && dvc.address === deviceAddress;
    });

    return device;
};

devicesStore.getDevice = function (deviceId, deviceAddress) {

    return JSON.parse(JSON.stringify(devicesStore.getDeviceRef(deviceId, deviceAddress)));
};

devicesStore.getNewScan = function () {

    return _newScan;
};

devicesStore.getSelectedPoints = function (device) {

    var device = devicesStore.getDeviceRef(device.id, device.address);
    var selectedPoints = [];

    if (device) {
        selectedPoints = device.selectedPoints;
    }

    return selectedPoints;
};

devicesStore.getKeyboard = function (deviceId) {

    var keyboard = deviceId === _keyboard.device ? JSON.parse(JSON.stringify(_keyboard)) : null;

    return keyboard;
};

devicesStore.deviceHasFocus = function (deviceId) {
    return _focusedDevice === deviceId;
};

devicesStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        // case ACTION_TYPES.HANDLE_KEY_DOWN:

        //     if (_devices.length)
        //     {
        //         var keydown = action.keydown;

        //         var emitKeyboard = function (keyboard)
        //         {
        //             devicesStore.emitChange();
        //         }

        //         switch (keydown.which)
        //         {
        //             case 17: // control

        //                 if (!_keyboard.started)
        //                 {
        //                     if (_keyboard.device === null)
        //                     {
        //                         var focusedDevice = _devices.find(function (device) {
        //                             return (device.registryConfig.length > 0);
        //                         });

        //                         _keyboard.device = focusedDevice.id;
        //                     }

        //                     if (_keyboard.device !== null)
        //                     {
        //                         _keyboard.active = true;
        //                         _keyboard.cmd = "start";
        //                         _keyboard.started = true;

        //                         emitKeyboard(_keyboard);
        //                     }
        //                 }
        //                 else
        //                 {
        //                     _keyboard.cmd = "resume";
        //                     emitKeyboard(_keyboard);
        //                 }
        //                 break;
        //             case 27: // ESC
        //                 _keyboard.active = false;
        //                 _keyboard.cmd = null;
        //                 _keyboard.started = false;
        //                 emitKeyboard(_keyboard);
        //                 break;
        //             case 13: // Enter
        //                 _keyboard.cmd = "enter";
        //                 _keyboard.active = false;
        //                 emitKeyboard(_keyboard);
        //                 break;
        //             // case 9:    //Tab
        //             case 32:    //Space
        //             case 40:    //Down
        //                 _keyboard.cmd = (keydown.shiftKey ? "extend_down" : "down");
        //                 emitKeyboard(_keyboard);
        //                 break;
        //             case 38:    //Up
        //                 _keyboard.cmd = (keydown.shiftKey ? "extend_up" : "up");
        //                 emitKeyboard(_keyboard);
        //                 break;
        //             case 46:    //Delete
        //                 _keyboard.cmd = "delete";
        //                 emitKeyboard(_keyboard);
        //                 break;
        //         }
        //     }

        //     break;
        case ACTION_TYPES.CONFIGURE_DEVICES:
            _platform = action.platform;
            _devices = [];
            _newScan = true;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.ADD_DEVICES:
        case ACTION_TYPES.CANCEL_SCANNING:
            _action = "get_scan_settings";
            _view = "Detect Devices";
            _device = null;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.LISTEN_FOR_IAMS:
            _newScan = false;
            _warnings = {};
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.DEVICE_DETECTED:
            _action = "device_detected";
            _view = "Devices Found";
            var warning = loadDevice(action.device, action.platform, action.bacnet);

            if (!objectIsEmpty(warning)) {
                if (_warnings.hasOwnProperty(warning.key)) {
                    _warnings[warning.key].items.push(warning.value);
                } else {
                    _warnings[warning.key] = {
                        message: warning.message,
                        items: [warning.value]
                    };
                }
            }
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.POINT_RECEIVED:
            _action = "point_received";
            _view = "Devices Found";
            var warning = loadPoint(action.data, action.platform, action.bacnet);

            if (!objectIsEmpty(warning)) {
                if (_warnings.hasOwnProperty(warning.key)) {
                    _warnings[warning.key].items.push(warning.value);
                } else {
                    _warnings[warning.key] = {
                        message: warning.message,
                        items: [warning.value]
                    };
                }
            }
            devicesStore.emitChange();
            break;

        case ACTION_TYPES.FOCUS_ON_DEVICE:

            var focusedDevice = devicesStore.getDeviceRef(action.deviceId, action.address);

            if (focusedDevice) {
                if (_focusedDevice !== focusedDevice.id) {
                    _focusedDevice = focusedDevice.id;

                    devicesStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.CONFIGURE_DEVICE:
            _action = "configure_device";
            _view = "Configure Device";
            _device = action.device;

            var device = devicesStore.getDeviceRef(_device.id, _device.address);

            if (device) {
                device.showPoints = action.device.showPoints;
                device.configuring = action.device.configuring;

                if (device.configuring) {
                    device.registryConfig = [];
                }
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.TOGGLE_SHOW_POINTS:
            _action = "configure_device";
            _view = "Configure Device";
            _device = action.device;

            var device = devicesStore.getDeviceRef(_device.id, _device.address);

            if (device) {
                device.showPoints = action.device.showPoints;
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.CANCEL_REGISTRY:
            _action = "configure_device";
            _view = "Configure Device";
            _device = action.device;
            // _data[_device.deviceId] = (_backupData.hasOwnProperty(_device.deviceId) ? JSON.parse(JSON.stringify(_backupData[_device.deviceId])) : []);
            // _registryFiles[_device.deviceId] = (_backupFileName.hasOwnProperty(_device.deviceId) ? _backupFileName[_device.deviceId] : "");

            var device = devicesStore.getDeviceRef(_device.id, _device.address);

            if (device) {
                device.registryConfig = [];
                device.showPoints = false;
                device.configuring = false;
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.LOAD_REGISTRY:
            _action = "configure_registry";
            _view = "Registry Configuration";
            // _device = action.device;
            // _backupData[_device.id] = (_data.hasOwnProperty(_device.id) ? JSON.parse(JSON.stringify(_data[_device.id])) : []);
            // _backupFileName[_device.id] = (_registryFiles.hasOwnProperty(_device.id) ? _registryFiles[_device.id] : "");
            // _data[_device.id] = JSON.parse(JSON.stringify(action.data));

            var device = devicesStore.getDeviceRef(action.deviceId, action.deviceAddress);

            if (device) {
                device.registryConfig = getPreppedData(action.data);
                device.showPoints = true;
                device.selectedPoints = [];
            }

            _registryFiles[action.deviceId] = action.file;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.UPDATE_REGISTRY:
            _action = "update_registry";
            _view = "Registry Configuration";
            // _device = action.device;
            // _backupData[_device.id] = (_data.hasOwnProperty(_device.id) ? JSON.parse(JSON.stringify(_data[_device.id])) : []);
            // _backupFileName[_device.id] = (_registryFiles.hasOwnProperty(_device.id) ? _registryFiles[_device.id] : "");
            // _data[_device.id] = JSON.parse(JSON.stringify(action.data));

            var i = -1;
            var keyProps = [];

            var device = devicesStore.getDeviceRef(action.deviceId, action.deviceAddress);

            if (device) {
                var attributes = device.registryConfig.find(function (attributes, index) {
                    var match = attributes.get(0).value === action.attributes.get(0).value;

                    if (match) {
                        i = index;
                    }

                    return match;
                });

                action.attributes.forEach(function (item) {
                    if (item.keyProp) {
                        keyProps.push(item.key);
                    }
                });

                device.keyProps = keyProps;

                if (typeof attributes !== "undefined") {
                    device.registryConfig[i] = action.attributes;
                } else {
                    device.registryConfig.push(action.attributes);
                }

                device.selectedPoints = action.selectedPoints;
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.EDIT_REGISTRY:
            _action = "configure_registry";
            _view = "Registry Configuration";
            _device = action.device;
            _backupData[_device.deviceId] = _data.hasOwnProperty(_device.deviceId) ? JSON.parse(JSON.stringify(_data[_device.deviceId])) : [];
            _backupFileName[_device.deviceId] = _registryFiles.hasOwnProperty(_device.deviceId) ? _registryFiles[_device.deviceId] : "";
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.SAVE_REGISTRY:
            _action = "configure_device";
            _view = "Configure Device";
            // _device = action.device;

            var device = devicesStore.getDeviceRef(action.deviceId, action.deviceAddress);

            if (device) {
                device.registryConfig = action.data;
                device.showPoints = false;
            }

            devicesStore.emitChange();
            break;
    }

    function getPreppedData(data) {

        var preppedData = data.map(function (row) {
            var preppedRow = row.map(function (cell) {

                prepCell(cell);

                return cell;
            });

            return Immutable.List(preppedRow);
        });

        return preppedData;
    }

    function prepCell(cell) {

        cell.key = cell.key.toLowerCase();

        cell.editable = !(cell.key === "point_name" || cell.key === "reference_point_name" || cell.key === "object_type" || cell.key === "index");
    }

    function loadPoint(data, platform, bacnetUuid) {
        var warningMsg = {};

        if (data) {
            var point = JSON.parse(data);
            var deviceId = "59";
            // var deviceId = point.device_id;
            var deviceAddress = "10.0.2.6";
            var addPoint = true;

            var device = devicesStore.getDeviceRef(deviceId, deviceAddress);

            if (device) {
                var pointInList = device.registryConfig.find(function (point) {
                    var indexCell = point.find(function (cell) {
                        return cell.key === "index";
                    });

                    var match = false;

                    if (indexCell) {
                        match = indexCell.value === point.Index;
                    }

                    return match;
                });

                if (typeof pointInList === "undefined") {
                    var newPoint = [];

                    for (var key in point) {
                        var cell = {
                            key: key.toLowerCase().replace(/ /g, "_"),
                            label: key,
                            value: point[key] === null ? "" : point[key]
                        };

                        prepCell(cell);

                        newPoint.push(cell);
                    }

                    device.registryConfig.push(Immutable.List(newPoint));
                }
            }
        }

        return warningMsg;
    }

    function objectIsEmpty(obj) {
        return Object.keys(obj).length === 0;
    }

    function loadDevice(data, platform, bacnetUuid) {
        var warningMsg = {};

        if (data) {
            var device = JSON.parse(data);
            var deviceIdStr = device.device_id.toString();
            var addDevice = true;

            var alreadyInList = devicesStore.getDeviceByID(deviceIdStr);

            if (alreadyInList) {
                if (alreadyInList.address !== device.address) {
                    warningMsg = {
                        key: "duplicate_id",
                        message: "Duplicate device IDs found. What the heck? Your network may not be set up correctly. ",
                        value: deviceIdStr
                    };
                } else // If the IDs are the same and the addresses are the same, assume
                    {
                        // it's an IAM for a device we already know about

                        addDevice = false;
                    }
            }

            if (addDevice) {
                _devices.push({
                    id: deviceIdStr,
                    name: device.device_name,
                    vendor_id: device.vendor_id,
                    address: device.address,
                    max_apdu_length: device.max_apdu_length,
                    segmentation_supported: device.segmentation_supported,
                    showPoints: false,
                    configuring: false,
                    platformUuid: platform.uuid,
                    bacnetProxyUuid: bacnetUuid,
                    registryConfig: [],
                    keyProps: ["volttron_point_name", "units", "writable"],
                    selectedPoints: [],
                    items: [{ key: "address", label: "Address", value: device.address }, { key: "deviceName", label: "Name", value: device.device_name }, { key: "deviceDescription", label: "Description", value: device.device_description }, { key: "deviceId", label: "Device ID", value: deviceIdStr }, { key: "vendorId", label: "Vendor ID", value: device.vendor_id }, { key: "vendor", label: "Vendor", value: vendorTable[device.vendor_id] }, { key: "type", label: "Type", value: "BACnet" }]
                });
            }
        }

        return warningMsg;
    }
});

module.exports = devicesStore;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53,"../stores/authorization-store":57,"immutable":undefined}],61:[function(require,module,exports){
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

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53}],62:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');
var platformsStore = require('./platforms-store.js');

var _chartData = {};
var _showCharts = false;
var _chartTopics = {
    platforms: []
};

var chartStore = new Store();

chartStore.getPinnedCharts = function () {
    var pinnedCharts = [];

    var user = authorizationStore.getUsername();

    for (var key in _chartData) {
        if (_chartData[key].hasOwnProperty("pinned") && _chartData[key].pinned === true && _chartData[key].data.length > 0) {
            pinnedCharts.push(_chartData[key]);
        }
    }

    return JSON.parse(JSON.stringify(pinnedCharts));
};

chartStore.getData = function () {
    return JSON.parse(JSON.stringify(_chartData));
};

chartStore.getPinned = function (chartKey) {
    return _chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].pinned : null;
};

chartStore.getType = function (chartKey) {
    var type = "line";

    if (_chartData.hasOwnProperty(chartKey)) {
        if (_chartData[chartKey].hasOwnProperty("type")) {
            type = _chartData[chartKey].type;
        }
    }

    return type;
};

chartStore.getMin = function (chartKey) {
    var min;

    if (_chartData.hasOwnProperty(chartKey)) {
        if (_chartData[chartKey].hasOwnProperty("min")) {
            min = _chartData[chartKey].min;
        }
    }

    return min;
};

chartStore.getMax = function (chartKey) {
    var max;

    if (_chartData.hasOwnProperty(chartKey)) {
        if (_chartData[chartKey].hasOwnProperty("max")) {
            max = _chartData[chartKey].max;
        }
    }

    return max;
};

chartStore.getRefreshRate = function (chartKey) {
    return _chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].refreshInterval : null;
};

chartStore.showCharts = function () {

    var showCharts = _showCharts;

    _showCharts = false;

    return showCharts;
};

chartStore.getChartTopics = function () {

    var topics = [];

    if (_chartTopics.hasOwnProperty("platforms")) {
        topics = JSON.parse(JSON.stringify(_chartTopics.platforms));

        if (topics.length) {
            if (_chartData !== {}) {
                // Filter out any topics that are already in charts
                topics = topics.filter(function (topic) {

                    var topicInChart = false;

                    if (_chartData.hasOwnProperty(topic.name)) {
                        var path = _chartData[topic.name].series.find(function (item) {
                            return item.topic === topic.value;
                        });

                        topicInChart = path ? true : false;
                    }

                    return !topicInChart;
                });
            }

            // Filter out any orphan chart topics not associated with registered platforms
            var platformUuids = platformsStore.getPlatforms().map(function (platform) {
                return platform.uuid;
            });

            topics = topics.filter(function (topic) {

                // This filter will keep platform topics of known platforms and any topic that
                // looks like a device topic
                var platformTopic = platformUuids.filter(function (uuid) {
                    return topic.value.indexOf(uuid) > -1 || topic.value.indexOf("datalogger/platform") < 0;
                });

                return platformTopic.length ? true : false;
            });
        }
    }

    return topics;
};

chartStore.getTopicInCharts = function (topic, topicName) {
    var itemInChart;

    if (_chartData.hasOwnProperty(topicName)) {
        _chartData[topicName].series.find(function (series) {

            itemInChart = series.topic === topic;

            return itemInChart;
        });
    }

    return itemInChart;
};

chartStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.ADD_TO_CHART:

            if (_chartData.hasOwnProperty(action.panelItem.name)) {
                insertSeries(action.panelItem);
                chartStore.emitChange();
            } else {
                if (action.panelItem.hasOwnProperty("data")) {
                    var chartObj = {
                        refreshInterval: action.panelItem.hasOwnProperty("refreshInterval") ? action.panelItem.refreshInterval : 15000,
                        pinned: action.panelItem.hasOwnProperty("pinned") ? action.panelItem.pinned : false,
                        type: action.panelItem.hasOwnProperty("chartType") ? action.panelItem.chartType : "line",
                        data: convertTimeToSeconds(action.panelItem.data),
                        chartKey: action.panelItem.name,
                        min: action.panelItem.hasOwnProperty("min") ? action.panelItem.min : null,
                        max: action.panelItem.hasOwnProperty("max") ? action.panelItem.max : null,
                        series: [setChartItem(action.panelItem)]
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

            if (_chartData.hasOwnProperty(action.panelItem.name)) {
                removeSeries(action.panelItem.name, action.panelItem.uuid);

                if (_chartData.hasOwnProperty(action.panelItem.name)) {
                    if (_chartData[action.panelItem.name].length === 0) {
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

            if (_chartData[action.chartKey].hasOwnProperty("refreshInterval")) {
                _chartData[action.chartKey].refreshInterval = action.rate;
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_MIN:

            _chartData[action.chartKey].min = action.min;

            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_MAX:

            _chartData[action.chartKey].max = action.max;

            chartStore.emitChange();

            break;

        case ACTION_TYPES.PIN_CHART:

            if (_chartData[action.chartKey].hasOwnProperty("pinned")) {
                _chartData[action.chartKey].pinned = !_chartData[action.chartKey].pinned;
            } else {
                _chartData[action.chartKey].pinned = true;
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_TYPE:

            if (_chartData[action.chartKey].type !== action.chartType) {
                _chartData[action.chartKey].type = action.chartType;
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.SHOW_CHARTS:

            if (action.emitChange) {
                _showCharts = true;
                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.RECEIVE_CHART_TOPICS:
            _chartTopics = {};

            var chartTopics = JSON.parse(JSON.stringify(action.topics));

            _chartTopics.platforms = chartTopics;

            chartStore.emitChange();
            break;

        case ACTION_TYPES.REMOVE_CHART:

            var name = action.name;

            if (_chartData.hasOwnProperty(name)) {

                delete _chartData[name];

                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.REMOVE_PLATFORM_CHARTS:

            var seriesToCut = [];

            for (var name in _chartData) {
                _chartData[name].series.forEach(function (series) {

                    if (series.path.indexOf(this.uuid) > -1) {
                        seriesToCut.push({ name: series.name, uuid: series.uuid });
                    }
                }, action.platform);
            }

            seriesToCut.forEach(function (series) {
                removeSeries(series.name, series.uuid);

                if (_chartData[series.name].series.length === 0) {
                    delete _chartData[series.name];
                }
            }, action.platform);

            if (seriesToCut.length) {
                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:

            _chartData = {};

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
        };

        return chartItem;
    }

    function insertSeries(item) {

        var chartItems = _chartData[item.name].data.filter(function (datum) {
            return datum.uuid === item.uuid;
        });

        if (chartItems.length === 0) {
            if (item.hasOwnProperty("data")) {
                _chartData[item.name].data = _chartData[item.name].data.concat(convertTimeToSeconds(item.data));
                _chartData[item.name].series.push(setChartItem(item));
            }
        }
    }

    function removeSeries(name, uuid) {

        if (_chartData[name].data.length > 0) {
            for (var i = _chartData[name].data.length - 1; i >= 0; i--) {
                if (_chartData[name].data[i].uuid === uuid) {
                    _chartData[name].data.splice(i, 1);
                }
            }

            for (var i = 0; i < _chartData[name].series.length; i++) {
                if (_chartData[name].series[i].uuid === uuid) {
                    _chartData[name].series.splice(i, 1);

                    break;
                }
            }
        }
    }

    function convertTimeToSeconds(data) {
        var dataList = [];

        for (var key in data) {
            var newItem = {};

            for (var skey in data[key]) {
                var value = data[key][skey];

                if (typeof value === 'string') {
                    value = value.replace('+00:00', '');
                }

                if (skey === "0" && typeof value === 'string' && Date.parse(value + 'Z')) {
                    value = Date.parse(value + 'Z');
                }

                newItem[skey] = value;
            }

            dataList.push(newItem);
        }

        return dataList;
    }
});

module.exports = chartStore;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53,"../stores/authorization-store":57,"./platforms-store.js":65}],63:[function(require,module,exports){
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

platformsPanelItemsStore.getLastCheck = function (topic) {
    return _lastCheck;
};

platformsPanelItemsStore.findTopicInTree = function (topic) {
    var path = [];

    var topicParts = topic.split("/");

    if (topic.indexOf("datalogger/platforms") > -1) // if a platform instance
        {
            for (var key in _items.platforms) {
                if (key === topicParts[2]) {
                    if (_items.platforms[key].hasOwnProperty("points")) {
                        _items.platforms[key].points.children.find(function (point) {

                            var found = point === topic;

                            if (found) {
                                path = _items.platforms[key].points[point].path;
                            }

                            return found;
                        });
                    }

                    break;
                }
            }
        } else // else a device point
        {
            var buildingName = topicParts[1];

            for (var key in _items.platforms) {
                var platform = _items.platforms[key];
                var foundPlatform = false;

                if (platform.hasOwnProperty("buildings")) {
                    platform.buildings.children.find(function (buildingUuid) {

                        var foundBuilding = platform.buildings[buildingUuid].name === buildingName;

                        if (foundBuilding) {
                            var parent = platform.buildings[buildingUuid];

                            for (var i = 2; i <= topicParts.length - 2; i++) {
                                var deviceName = topicParts[i];

                                if (parent.hasOwnProperty("devices")) {
                                    parent.devices.children.find(function (deviceUuid) {

                                        var foundDevice = parent.devices[deviceUuid].name === deviceName;

                                        if (foundDevice) {
                                            parent = parent.devices[deviceUuid];
                                        }

                                        return foundDevice;
                                    });
                                }
                            }

                            if (parent.hasOwnProperty("points")) {
                                parent.points.children.find(function (point) {
                                    var foundPoint = parent.points[point].topic === topic;

                                    if (foundPoint) {
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

                if (foundPlatform) {
                    break;
                }
            }
        }

    return JSON.parse(JSON.stringify(path));
};

platformsPanelItemsStore.getItem = function (itemPath) {
    var itemsList = [];
    var item = _items;

    for (var i = 0; i < itemPath.length; i++) {
        if (item.hasOwnProperty(itemPath[i])) {
            item = item[itemPath[i]];
        }
    }

    return item;
};

platformsPanelItemsStore.getChildren = function (parent, parentPath) {

    var itemsList = [];
    var item = _items;

    if (parentPath !== null) // for everything but the top level, drill down to the parent
        {
            var validPath = true;

            for (var i = 0; i < parentPath.length; i++) {
                if (item.hasOwnProperty(parentPath[i])) {
                    item = item[parentPath[i]];
                } else {
                    validPath = false;
                }
            }

            if (validPath) {
                for (var i = 0; i < item.children.length; i++) {
                    itemsList.push(item[item.children[i]]);
                }
            }
        } else {
        for (var key in item[parent]) {
            itemsList.push(item[parent][key]);
        }
    }

    return itemsList;
};

platformsPanelItemsStore.loadFilteredItems = function (filterTerm, filterStatus) {

    var filterItems = function filterItems(parent, filterTerm, filterStatus) {

        var notAMatch;
        var compareTerm;

        if (filterTerm === "") {
            notAMatch = function notAMatch(parent, filterStatus) {
                if (parent.hasOwnProperty("status")) {
                    return parent.status !== filterStatus;
                } else {
                    return filterStatus !== "UNKNOWN";
                }
            };

            compareTerm = filterStatus;
        } else if (filterStatus === "") {
            notAMatch = function notAMatch(parent, filterTerm) {
                var upperParent = parent.name.toUpperCase();;
                var filterStr = filterTerm;

                var filterParts = filterTerm.split(" ");
                var foundColon = filterParts[0].indexOf(":") > -1;

                if (foundColon) {
                    var index = filterTerm.indexOf(":");
                    var filterKey = filterTerm.substring(0, index);
                    filterStr = filterTerm.substring(index + 1);

                    if (parent.hasOwnProperty(filterKey)) {
                        upperParent = parent[filterKey].toUpperCase();
                    } else {
                        return true;
                    }
                }

                return upperParent.trim().indexOf(filterStr.trim().toUpperCase()) < 0;
            };

            compareTerm = filterTerm;
        }

        if (parent.children.length === 0) {
            parent.visible = !notAMatch(parent, compareTerm);
            parent.expanded = null;

            return parent;
        } else {
            var childrenToHide = 0;

            for (var i = 0; i < parent.children.length; i++) {
                var childString = parent.children[i];
                var filteredChild = filterItems(parent[childString], filterTerm, filterStatus);

                if (!filteredChild.visible) {
                    ++childrenToHide;
                }
            }

            if (childrenToHide === parent.children.length) {
                parent.visible = !notAMatch(parent, compareTerm);
                parent.expanded = false;
            } else {
                parent.visible = true;
                parent.expanded = true;
            }

            return parent;
        }
    };

    for (var key in _items.platforms) {
        if (filterTerm !== "" || filterStatus !== "") {
            filterItems(_items.platforms[key], filterTerm, filterStatus);
        } else {
            expandAllChildren(_items.platforms[key], false);
            _items.platforms[key].visible = true;
        }
    }
};

var expandAllChildren = function expandAllChildren(parent, expanded) {

    for (var i = 0; i < parent.children.length; i++) {
        var childString = parent.children[i];
        expandAllChildren(parent[childString], expanded);
    }

    if (parent.children.length > 0) {
        parent.expanded = expanded;
    } else {
        parent.expanded = null;
    }

    parent.visible = true;
};

platformsPanelItemsStore.getExpanded = function () {
    return _expanded;
};

platformsPanelItemsStore.getLoadingComplete = function (panelItem) {

    var loadingComplete = null;

    if (_loadingDataComplete.hasOwnProperty(panelItem.uuid)) {
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

            var expanded = item.expanded !== null ? !item.expanded : true;

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

            platforms.forEach(function (platform) {
                if (!action.reload || !_items["platforms"].hasOwnProperty(platform.uuid)) {
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
                }
            });

            var platformsToRemove = [];

            for (var key in _items.platforms) {
                var match = platforms.find(function findPlatform(platform) {
                    return key === platform.uuid;
                });

                if (!match) {
                    platformsToRemove.push(key);
                }
            }

            platformsToRemove.forEach(function (uuid) {
                delete _items.platforms[uuid];
            });

            _lastCheck = false;

            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.agents.length > 0) {
                insertAgents(platform, action.agents);
            }

            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.devices.length > 0) {
                insertDevices(platform, action.devices);
            }

            break;
        case ACTION_TYPES.RECEIVE_PERFORMANCE_STATS:

            switch (action.parent.type) {
                case "platform":

                    var platform = _items["platforms"][action.parent.uuid];

                    if (action.points.length > 0) {
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

                        if (platform.children.indexOf("points") < 0) {
                            platform.children.push("points");
                        }

                        action.points.forEach(function (point) {
                            var pointProps = point;
                            pointProps.expanded = false;
                            pointProps.visible = true;
                            pointProps.path = platform.points.path.slice(0);

                            var uuid = point.hasOwnProperty("topic") ? point.topic : point.uuid;

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

    function insertAgents(platform, agents) {
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

        if (platform.children.indexOf("agents") < 0) {
            platform.children.push("agents");
        }

        var agentsHealth;

        agentsToInsert.forEach(function (agent) {
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

    function insertBuilding(platform, uuid, name) {
        if (platform.children.indexOf("buildings") < 0) {
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

        if (!platform.buildings.hasOwnProperty(uuid)) {
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

            platform.buildings.children.push(buildingProps.uuid);
            platform.buildings[buildingProps.uuid] = buildingProps;
        }

        return platform.buildings[uuid];
    }

    function insertDevices(platform, devices) {
        var devicesToInsert = JSON.parse(JSON.stringify(devices));

        var buildings = [];

        if (devicesToInsert.length > 0) {
            //Make a 2D array where each row is another level 
            // of devices and subdevices in the tree
            var nestedDevices = [];
            var level = 3;
            var deviceCount = 0;

            while (deviceCount < devicesToInsert.length) {
                var levelList = [];

                devicesToInsert.forEach(function (device) {

                    var deviceParts = device.path.split("/");

                    if (deviceParts.length === level) {
                        levelList.push(device);
                        ++deviceCount;
                    }
                });

                if (levelList.length > 0) {
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

    function insertDevice(device, building, legendInfo, row) {
        switch (row) {
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
                if (subDeviceLevel !== row + 2) {
                    console.log("wrong level number");
                } else {
                    //Now find the subdevice's parent device by using the parts of its path
                    // to walk the tree
                    var parentPath = JSON.parse(JSON.stringify(building.path));
                    var parentDevice = building; // start at the building
                    var currentLevel = 2; // the level of the top-level devices

                    while (currentLevel < subDeviceLevel) {
                        var parentDeviceUuid = deviceParts[0];

                        for (var i = 1; i <= currentLevel; i++) {
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
                    if (parentDevice.children.indexOf("devices") < 0) {
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

                    if (parentDevice.devices.children.length > 1) {
                        updateDeviceGroupStatus(parentDevice);
                    }
                }

                break;
        }
    }

    function checkForPoints(item, data) {
        if (data.hasOwnProperty("points")) {
            if (item.children.indexOf("points") < 0) {
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

                var pattern = /[!@#$%^&*()+\-=\[\]{};':"\\|, .<>\/?]/g;

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

    function getParentPath(parent) {
        var path = parent.path;

        var pathParts = [];

        var item = _items;

        path.forEach(function (part) {
            item = item[part];
            if (_itemTypes.indexOf(part) < 0) {
                pathParts.push(item.name);
            }
        });

        var pathStr = pathParts.join(" > ");

        return pathStr;
    }

    function updatePlatformStatus(uuid) {
        if (_items.platforms.hasOwnProperty(uuid)) {
            var platform = JSON.parse(JSON.stringify(_items.platforms[uuid]));

            if (_items.platforms[uuid].hasOwnProperty("agents")) {
                var agentsHealth = _items.platforms[uuid].agents.status;
                platform.status = checkStatuses(agentsHealth, platform);
            }

            if (platform.status === "GOOD" || platform.status === "UNKNOWN") {
                if (_items.platforms[uuid].hasOwnProperty("buildings")) {
                    var buildingsHealth = _items.platforms[uuid].buildings.status;
                    platform.status = checkStatuses(buildingsHealth, platform);
                }
            }

            if (platform.status === "GOOD" || platform.status === "UNKNOWN") {
                if (_items.platforms[uuid].hasOwnProperty("points")) {
                    var pointsHealth = _items.platforms[uuid].points.status;
                    platform.status = checkStatuses(pointsHealth, platform);
                }
            }

            if (platform.status !== _items.platforms[uuid].status) {
                _items.platforms[uuid].status = platform.status;
                _items.platforms[uuid].statusLabel = getStatusLabel(platform.status);
                _items.platforms[uuid].context = "Status problems found.";
            }
        }
    }

    function updateDeviceGroupStatus(parent) {
        var parentDevice = JSON.parse(JSON.stringify(parent));

        if (parentDevice.hasOwnProperty("devices")) {
            parentDevice.devices.children.forEach(function (uuid) {
                var subDeviceHealth = checkStatuses(parentDevice.devices[uuid].status, parentDevice.devices);

                if (subDeviceHealth !== parent.devices.status) {
                    parent.devices.status = subDeviceHealth;
                    parent.devices.statusLabel = getStatusLabel(subDeviceHealth);
                }
            });
        }

        var deviceGroupHealth = checkStatuses(parent.devices.status, parentDevice);
        if (deviceGroupHealth !== parent.status) {
            parent.status = deviceGroupHealth;
            parent.statusLabel = getStatusLabel(deviceGroupHealth);
            parent.context = "Status problems found.";
        }
    }

    function checkStatuses(health, item) {
        if (typeof health === "undefined") {
            health = item.status;
        } else {
            switch (health) {
                case "UNKNOWN":

                    switch (item.status) {
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

    function getStatusLabel(status) {
        var statusLabel;

        switch (status) {
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

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53,"../stores/platform-chart-store":62}],64:[function(require,module,exports){
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
            _expanded === null ? _expanded = true : _expanded = !_expanded;
            platformsPanelStore.emitChange();
            break;
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _expanded = null;
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53}],65:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _platforms = null;
var _initialized = false;

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

platformsStore.getVcInstance = function () {
    var vc;

    if (_platforms) {
        if (_platforms.length) {
            vc = _platforms.find(function (platform) {

                var hasVcAgent = false;

                if (platform.agents) {
                    if (platform.agents.length) {
                        var vcAgent = platform.agents.find(function (agent) {
                            return agent.name.toLowerCase().indexOf("volttroncentral") > -1;
                        });

                        if (vcAgent) {
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

platformsStore.getAgentRunning = function (platform, agentType) {

    var agentRunning = false;

    if (platform) {
        if (platform.hasOwnProperty("agents")) {
            var agentToFind = platform.agents.find(function (agent) {
                return agent.name.toLowerCase().indexOf(agentType) > -1;
            });

            if (agentToFind) {
                agentRunning = agentToFind.process_id !== null && agentToFind.return_code === null;
            }
        }
    }

    return agentRunning;
};

platformsStore.getVcHistorianRunning = function () {

    var platform = platformsStore.getVcInstance();
    var historianRunning = platformsStore.getAgentRunning(platform, "historian");

    return historianRunning;
};

platformsStore.getRunningBacnetProxies = function (uuid) {
    var bacnetProxies = [];

    if (_platforms) {
        if (_platforms.length) {
            var foundPlatform = _platforms.find(function (platform) {
                return platform.uuid === uuid;
            });

            if (foundPlatform) {
                if (foundPlatform.hasOwnProperty("agents")) {
                    bacnetProxies = foundPlatform.agents.filter(function (agent) {

                        var runningProxy = agent.name.toLowerCase().indexOf("bacnet_proxy") > -1 && agent.actionPending === false && agent.process_id !== null && agent.return_code === null;

                        return runningProxy;
                    });
                }
            }
        }
    }

    return bacnetProxies;
};

platformsStore.getForwarderRunning = function (platformUuid) {

    var platform = platformsStore.getPlatform(platformUuid);
    var forwarderRunning = platformsStore.getAgentRunning(platform, "forwarderagent");

    return forwarderRunning;
};

platformsStore.getInitialized = function () {
    return _initialized;
};

platformsStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _platforms = null;
            break;

        case ACTION_TYPES.WILL_INITIALIZE_PLATFORMS:
            _initialized = true;
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

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53,"./authorization-store":57}],66:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _statusMessage = null;
var _status = null;
var _highlight = null;
var _align = null;

var statusIndicatorStore = new Store();

statusIndicatorStore.getStatusMessage = function () {

    var status = {
        statusMessage: _statusMessage,
        status: _status
    };

    if (_highlight) {
        status.highlight = _highlight;
    }

    if (_align) {
        status.align = _align;
    }

    return status;
};

statusIndicatorStore.getStatus = function () {
    return _status;
};

statusIndicatorStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.OPEN_STATUS:
            _statusMessage = action.message;
            _status = action.status;
            _highlight = action.highlight;
            _align = action.align;

            statusIndicatorStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_STATUS:
            _statusMessage = {};
            _status = null;
            statusIndicatorStore.emitChange();
            break;
    }
});

module.exports = statusIndicatorStore;

},{"../constants/action-types":48,"../dispatcher":49,"../lib/store":53}]},{},[1]);
