(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var authorizationStore = require('./stores/authorization-store');
var LoginForm = require('./components/login-form');
var PageNotFound = require('./components/page-not-found');
var Platform = require('./components/platform');
var PlatformManager = require('./components/platform-manager');
var Platforms = require('./components/platforms');

var _afterLoginPath = '/platforms';

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
        React.createElement(Router.Route, {name: "platforms", path: "platforms", handler: checkAuth(Platforms)}), 
        React.createElement(Router.Route, {name: "platform", path: "platforms/:uuid", handler: checkAuth(Platform)}), 
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
});

authorizationStore.addChangeListener(function () {
    if (authorizationStore.getAuthorization() && router.isActive('/login')) {
        router.replaceWith(_afterLoginPath);
    } else if (!authorizationStore.getAuthorization() && !router.isActive('/login')) {
        router.replaceWith('/login');
    }
});


},{"./components/login-form":9,"./components/page-not-found":11,"./components/platform":13,"./components/platform-manager":12,"./components/platforms":14,"./stores/authorization-store":24,"react":undefined,"react-router":undefined}],2:[function(require,module,exports){
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


},{"../constants/action-types":15,"../dispatcher":16,"../lib/rpc/exchange":18}],3:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var platformsStore = require('../stores/platforms-store');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    initialize: function () {
        if (authorizationStore.getAuthorization() && !platformsStore.getPlatforms()) {
            platformManagerActionCreators.loadPlatforms();
        }
    },
    requestAuthorization: function (username, password) {
        new rpc.Exchange({
            method: 'get_authorization',
            params: {
                username: username,
                password: password,
            },
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AUTHORIZATION,
                    authorization: result,
                });

                platformManagerActionCreators.loadPlatforms();
            })
            .catch(handleRpcError);
    },
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    },
    loadPlatforms: function () {
        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'list_platforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: platforms,
                });

                platforms.forEach(function (platform) {
                    platformManagerActionCreators.loadPlatform(platform);
                });
            })
            .catch(handleRpcError);
    },
    loadPlatform: function (platform) {
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
            .catch(handleRpcError);
    },
    clearPlatformError: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_PLATFORM_ERROR,
            platform: platform,
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
                agent.actionPending = false;
                agent.process_id = status.process_id;
                agent.return_code = status.return_code;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            })
            .catch(handleRpcError);
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
                agent.actionPending = false;
                agent.process_id = status.process_id;
                agent.return_code = status.return_code;

                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORM,
                    platform: platform,
                });
            })
            .catch(handleRpcError);
    },
    installAgents: function (platform, files) {
        platformManagerActionCreators.clearPlatformError(platform);

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
                    platformManagerActionCreators.loadPlatform(platform);
                }
            });
    },
};

function handleRpcError(error) {
    if (error.code && error.code === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformManagerActionCreators.clearAuthorization();
    } else {
        throw error;
    }
}

module.exports = platformManagerActionCreators;


},{"../constants/action-types":15,"../dispatcher":16,"../lib/rpc":19,"../stores/authorization-store":24,"../stores/platforms-store":27}],4:[function(require,module,exports){
'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var AgentRow = React.createClass({displayName: "AgentRow",
    _onStop: function () {
        platformManagerActionCreators.stopAgent(this.props.platform, this.props.agent);
    },
    _onStart: function () {
        platformManagerActionCreators.startAgent(this.props.platform, this.props.agent);
    },
    render: function () {
        var agent = this.props.agent, status, action;

        if (agent.actionPending === undefined) {
            status = 'Retrieving status...';
        } else if (agent.actionPending) {
            if (agent.process_id === null || agent.return_code !== null) {
                status = 'Starting...';
                action = (
                    React.createElement("input", {className: "button", type: "button", value: "Start", disabled: true})
                );
            } else {
                status = 'Stopping...';
                action = (
                    React.createElement("input", {className: "button", type: "button", value: "Stop", disabled: true})
                );
            }
        } else {
            if (agent.process_id === null) {
                status = 'Never started';
                action = (
                    React.createElement("input", {className: "button", type: "button", value: "Start", onClick: this._onStart})
                );
            } else if (agent.return_code === null) {
                status = 'Running (PID ' + agent.process_id + ')';
                action = (
                    React.createElement("input", {className: "button", type: "button", value: "Stop", onClick: this._onStop})
                );
            } else {
                status = 'Stopped (returned ' + agent.return_code + ')';
                action = (
                    React.createElement("input", {className: "button", type: "button", value: "Start", onClick: this._onStart})
                );
            }
        }

        return (
            React.createElement("tr", null, 
                React.createElement("td", null, agent.name), 
                React.createElement("td", null, agent.uuid), 
                React.createElement("td", null, status), 
                React.createElement("td", null, action)
            )
        );
    },
});

module.exports = AgentRow;


},{"../action-creators/platform-manager-action-creators":3,"react":undefined}],5:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../stores/console-store":25,"react":undefined}],6:[function(require,module,exports){
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


},{"./composer":5,"./conversation":7,"react":undefined}],7:[function(require,module,exports){
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


},{"../stores/console-store":25,"./exchange":8,"jquery":undefined,"react":undefined}],8:[function(require,module,exports){
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


},{"react":undefined}],9:[function(require,module,exports){
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
    _onInputChange: function () {
        this.setState({
            username: this.refs.username.getDOMNode().value,
            password: this.refs.password.getDOMNode().value,
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
                    ref: "username", 
                    type: "text", 
                    placeholder: "Username", 
                    autoFocus: true, 
                    onChange: this._onInputChange}
                ), 
                React.createElement("input", {
                    className: "login-form__field", 
                    ref: "password", 
                    type: "password", 
                    placeholder: "Password", 
                    onChange: this._onInputChange}
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/login-form-store":26,"react":undefined,"react-router":undefined}],10:[function(require,module,exports){
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
            navItems = ['Platforms'].map(function (navItem) {
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
                React.createElement("a", {key: "logout", className: "navigation__item", onClick: this._onLogOutClick}, 
                    "Log out"
                )
            );
        }

        return (
            React.createElement("nav", {className: "navigation"}, 
                React.createElement("h1", {className: "logo"}, 
                    React.createElement("span", {className: "logo__name"}, "VOLTTRON"), 
                    React.createElement("span", {className: "logo__tm"}, "™")
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/authorization-store":24,"react":undefined,"react-router":undefined}],11:[function(require,module,exports){
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


},{"react":undefined}],12:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var authorizationStore = require('../stores/authorization-store');
var Console = require('./console');
var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');
var Navigation = require('./navigation');

var PlatformManager = React.createClass({displayName: "PlatformManager",
    mixins: [Router.Navigation, Router.State],
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        authorizationStore.addChangeListener(this._onStoreChange);
        consoleStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        authorizationStore.removeChangeListener(this._onStoreChange);
        consoleStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onButtonClick: function () {
        consoleActionCreators.toggleConsole();
    },
    render: function () {
        var classes = ['platform-manager'];

        if (this.state.consoleShown) {
            classes.push('platform-manager--console-open');
        }

        if (this.state.loggedIn) {
            classes.push('platform-manager--logged-in');
        } else {
            classes.push('platform-manager--not-logged-in');
        }

        return (
            React.createElement("div", {className: classes.join(' ')}, 
                React.createElement("div", {className: "main"}, 
                    React.createElement(Navigation, null), 
                    React.createElement(Router.RouteHandler, null)
                ), 
                React.createElement("input", {
                    className: "toggle", 
                    type: "button", 
                    value: 'Console ' + (this.state.consoleShown ? '\u25bc' : '\u25b2'), 
                    onClick: this._onButtonClick}
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
    };
}

module.exports = PlatformManager;


},{"../action-creators/console-action-creators":2,"../stores/authorization-store":24,"../stores/console-store":25,"./console":6,"./navigation":10,"react":undefined,"react-router":undefined}],13:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platform = React.createClass({displayName: "Platform",
    mixins: [Router.State],
    getInitialState: function () {
        return getStateFromStores(this);
    },
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
        platformManagerActionCreators.clearPlatformError(this.state.platform);
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
                platformManagerActionCreators.installAgents(platform, parsedFiles);
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
        if (!this.state.platform) {
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

        var platform = this.state.platform;
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
            React.createElement("div", {className: "view"}, 
                this.state.error && (
                    React.createElement("div", {className: "view__error error"}, this.state.error)
                ), 
                React.createElement("h2", null, 
                    React.createElement(Router.Link, {to: "platforms"}, "Platforms"), 
                    " / ", 
                    platform.name, " (", platform.uuid, ")"
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/platforms-store":27,"./agent-row":4,"react":undefined,"react-router":undefined}],14:[function(require,module,exports){
'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platforms = React.createClass({displayName: "Platforms",
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
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
                        React.createElement(Router.Link, {
                            key: platform.uuid, 
                            to: "platform", 
                            params: {uuid: platform.uuid}, 
                            className: "view__item"
                        }, 
                            React.createElement("h3", null, platform.name), 
                            React.createElement("code", null, status.join(' | '))
                        )
                    );
                });
        }

        return (
            React.createElement("div", {className: "view view--list"}, 
                React.createElement("h2", null, "Platforms"), 
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/platforms-store":27,"react":undefined,"react-router":undefined}],15:[function(require,module,exports){
'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
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
    RECEIVE_PLATFORM_ERROR: null,
    CLEAR_PLATFORM_ERROR: null,
});


},{"react/lib/keyMirror":undefined}],16:[function(require,module,exports){
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


},{"../constants/action-types":15,"flux":undefined}],17:[function(require,module,exports){
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


},{}],18:[function(require,module,exports){
'use strict';

var uuid = require('node-uuid');

var ACTION_TYPES = require('../../constants/action-types');
var dispatcher = require('../../dispatcher');
var RpcError = require('./error');
var xhr = require('../xhr');

function RpcExchange(opts) {
    if (!(this instanceof RpcExchange)) {
        return new RpcExchange(opts);
    }

    var exchange = this;

    // TODO: validate opts
    opts.jsonrpc = '2.0';
    opts.id = uuid.v1();

    exchange.initiated = Date.now();
    exchange.request = opts;

    dispatcher.dispatch({
        type: ACTION_TYPES.MAKE_REQUEST,
        exchange: exchange,
        request: exchange.request,
    });

    exchange.promise = new xhr.Request({
        method: 'POST',
        url: '/jsonrpc',
        contentType: 'application/json',
        data: JSON.stringify(exchange.request),
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

            return response.result;
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


},{"../../constants/action-types":15,"../../dispatcher":16,"../xhr":22,"./error":17,"node-uuid":undefined}],19:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange'),
};


},{"./error":17,"./exchange":18}],20:[function(require,module,exports){
'use strict';

var EventEmitter = require('events').EventEmitter;

var CHANGE_EVENT = 'change';

function Store() {
    EventEmitter.call(this);
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


},{"events":undefined}],21:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;


},{}],22:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":21,"./request":23}],23:[function(require,module,exports){
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


},{"./error":21,"bluebird":undefined,"jquery":undefined}],24:[function(require,module,exports){
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


},{"../constants/action-types":15,"../dispatcher":16,"../lib/store":20}],25:[function(require,module,exports){
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
            _exchanges.push(action.exchange);
            consoleStore.emitChange();
            break;

        case ACTION_TYPES.FAIL_REQUEST:
        case ACTION_TYPES.RECEIVE_RESPONSE:
            consoleStore.emitChange();
            break;
    }
});

module.exports = consoleStore;


},{"../constants/action-types":15,"../dispatcher":16,"../lib/store":20,"../stores/authorization-store":24}],26:[function(require,module,exports){
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


},{"../constants/action-types":15,"../dispatcher":16,"../lib/store":20,"./authorization-store":24}],27:[function(require,module,exports){
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


},{"../constants/action-types":15,"../dispatcher":16,"../lib/store":20,"../stores/authorization-store":24}]},{},[1]);
