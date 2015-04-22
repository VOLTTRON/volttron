(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');

var PlatformManager = require('./components/platform-manager');

React.render(
    React.createElement(PlatformManager, null),
    document.getElementById('app')
);


},{"./components/platform-manager":13,"react":undefined}],2:[function(require,module,exports){
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


},{"../constants/action-types":14,"../dispatcher":15,"../lib/rpc/exchange":17}],3:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
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
            })
            .catch(rpc.Error, function (error) {
                if (error.code && error.code === 401) {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
                        error: error,
                    });
                } else {
                    throw error;
                }
            });
    },
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    },
    goToPage: function (page) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_PAGE,
            page: page,
        });
    },
    loadPlatforms: function () {
        var authorization = platformManagerStore.getAuthorization();

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
                        });
                });
            })
            .catch(function (error) {
                if (error.code && error.code === 401) {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
                        error: error,
                    });
                } else {
                    throw error;
                }
            });
    },
    startAgent: function (platform, agent) {
        var authorization = platformManagerStore.getAuthorization();

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
            });
    },
    stopAgent: function (platform, agent) {
        var authorization = platformManagerStore.getAuthorization();

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
            });
    },
};

window.onhashchange = function () {
    platformManagerActionCreators.goToPage(location.hash.substr(1));
};

module.exports = platformManagerActionCreators;


},{"../constants/action-types":14,"../dispatcher":15,"../lib/rpc":18,"../stores/platform-manager-store":25}],4:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../stores/console-store":23,"react":undefined}],6:[function(require,module,exports){
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


},{"../stores/console-store":23,"./exchange":8,"jquery":undefined,"react":undefined}],8:[function(require,module,exports){
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

var AgentRow = require('./agent-row');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Home = React.createClass({displayName: "Home",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
        setTimeout(platformManagerActionCreators.loadPlatforms);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
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
            platforms = this.state.platforms.map(function (platform) {
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
                                platform.agents.map(function (agent) {
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
                    React.createElement("div", {className: "platform", key: platform.uuid}, 
                        React.createElement("h2", null, platform.name, " (", platform.uuid, ")"), 
                        agents
                    )
                );
            });
        }

        return (
            React.createElement("div", {className: "home"}, 
                platforms
            )
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformManagerStore.getPlatforms(),
    };
}

module.exports = Home;


},{"../action-creators/platform-manager-action-creators":3,"../stores/platform-manager-store":25,"./agent-row":4,"react":undefined}],10:[function(require,module,exports){
'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LogOutButton = React.createClass({displayName: "LogOutButton",
    _onClick: function () {
        platformManagerActionCreators.clearAuthorization();
    },
    render: function () {
        return (
            React.createElement("button", {className: "button", onClick: this._onClick}, "Log out")
        );
    }
});

module.exports = LogOutButton;


},{"../action-creators/platform-manager-action-creators":3,"react":undefined}],11:[function(require,module,exports){
'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var loginFormStore = require('../stores/login-form-store');

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
                React.createElement("h1", null, "VOLTTRON(TM) Platform Manager"), 
                React.createElement("input", {
                    ref: "username", 
                    type: "text", 
                    placeholder: "Username", 
                    onChange: this._onInputChange}
                ), 
                React.createElement("input", {
                    ref: "password", 
                    type: "password", 
                    placeholder: "Password", 
                    onChange: this._onInputChange}
                ), 
                React.createElement("input", {
                    className: "button", 
                    type: "submit", 
                    value: "Log in", 
                    disabled: !this.state.username || !this.state.password}
                ), 
                this.state.error ? (
                    React.createElement("div", {className: "error"}, 
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/login-form-store":24,"react":undefined}],12:[function(require,module,exports){
'use strict';

var React = require('react');

var LogOutButton = require('./log-out-button');

var Navigation = React.createClass({displayName: "Navigation",
    render: function () {
        return (
            React.createElement("div", {className: "navigation"}, 
                React.createElement("h1", null, React.createElement("a", {href: "#home"}, "VOLTTRON(TM) Platform Manager")), 
                React.createElement(LogOutButton, null)
            )
        );
    }
});

module.exports = Navigation;


},{"./log-out-button":10,"react":undefined}],13:[function(require,module,exports){
'use strict';

var React = require('react');

var Console = require('./console');
var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');
var Home = require('./home');
var LoginForm = require('./login-form');
var Navigation = require('./navigation');
var platformManagerStore = require('../stores/platform-manager-store');

var PlatformManager = React.createClass({displayName: "PlatformManager",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
        consoleStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onChange);
        consoleStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    _onButtonClick: function () {
        consoleActionCreators.toggleConsole();
    },
    render: function () {
        var classes = ['platform-manager'];

        if (!this.state.consoleShown) {
            classes.push('platform-manager--console-hidden');
        }

        return (
            React.createElement("div", {className: classes.join(' ')}, 
                React.createElement("div", {className: "main"}, 
                    !this.state.loggedIn && React.createElement(LoginForm, null), 
                    this.state.loggedIn && React.createElement(Navigation, null), 
                    this.state.loggedIn && React.createElement(Home, null)
                ), 
                React.createElement("input", {
                    className: "toggle button", 
                    type: "button", 
                    value: 'Console ' + (this.state.consoleShown ? '\u25bc' : '\u25b2'), 
                    onClick: this._onButtonClick}
                ), 
                this.state.consoleShown && React.createElement(Console, {className: "console"})
            )
        );
    }
});

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!platformManagerStore.getAuthorization(),
    };
}

module.exports = PlatformManager;


},{"../action-creators/console-action-creators":2,"../stores/console-store":23,"../stores/platform-manager-store":25,"./console":6,"./home":9,"./login-form":11,"./navigation":12,"react":undefined}],14:[function(require,module,exports){
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

    CHANGE_PAGE: null,

    RECEIVE_PLATFORMS: null,
    RECEIVE_PLATFORM: null,
});


},{"react/lib/keyMirror":undefined}],15:[function(require,module,exports){
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


},{"../constants/action-types":14,"flux":undefined}],16:[function(require,module,exports){
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


},{}],17:[function(require,module,exports){
'use strict';

var uuid = require('node-uuid');

var ACTION_TYPES = require('../../constants/action-types');
var dispatcher = require('../../dispatcher');
var RpcError = require('./error');
var xhr = require('../xhr');

function RpcExchange(opts) {
    if (!this instanceof RpcExchange) {
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


},{"../../constants/action-types":14,"../../dispatcher":15,"../xhr":21,"./error":16,"node-uuid":undefined}],18:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange'),
};


},{"./error":16,"./exchange":17}],19:[function(require,module,exports){
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


},{"events":undefined}],20:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;


},{}],21:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":20,"./request":22}],22:[function(require,module,exports){
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


},{"./error":20,"bluebird":undefined,"jquery":undefined}],23:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');
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

function _resetComposerValue(updateMethod) {
    var authorization = platformManagerStore.getAuthorization();
    var parsed;

    try {
        parsed = JSON.parse(_composerValue);

        if (updateMethod) {
            parsed.method = platformManagerStore.getPage();
        }
    } catch (e) {
        parsed = { method: platformManagerStore.getPage() };
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
    dispatcher.waitFor([platformManagerStore.dispatchToken]);

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

        case ACTION_TYPES.CHANGE_PAGE:
            _composerId = Date.now();
            _resetComposerValue(true);
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


},{"../constants/action-types":14,"../dispatcher":15,"../lib/store":19,"./platform-manager-store":25}],24:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');
var Store = require('../lib/store');

var _lastError = null;

var loginFormStore = new Store();

loginFormStore.getLastError = function () {
    return _lastError;
};

loginFormStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([platformManagerStore.dispatchToken]);

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


},{"../constants/action-types":14,"../dispatcher":15,"../lib/store":19,"./platform-manager-store":25}],25:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _authorization = sessionStorage.getItem('authorization');
var _page = location.hash.substr(1);
var _platforms = null;

var platformManagerStore = new Store();

platformManagerStore.getAuthorization = function () {
    return _authorization;
};

platformManagerStore.getPage = function () {
    return _page;
};

platformManagerStore.getPlatforms = function () {
    return _platforms;
};

platformManagerStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _authorization = action.authorization;
            sessionStorage.setItem('authorization', _authorization);
            platformManagerStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _authorization = null;
            sessionStorage.removeItem('authorization');
            platformManagerStore.emitChange();
            break;

        case ACTION_TYPES.CHANGE_PAGE:
            _page = action.page;
            location.hash = '#' + action.page;
            platformManagerStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORMS:
            _platforms = action.platforms;
            platformManagerStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORM:
            platformManagerStore.emitChange();
            break;
    }
});

module.exports = platformManagerStore;


},{"../constants/action-types":14,"../dispatcher":15,"../lib/store":19}]},{},[1])
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hcHAuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9hZ2VudC1yb3cuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb21wb3Nlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbnNvbGUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb252ZXJzYXRpb24uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9leGNoYW5nZS5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2hvbWUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9sb2ctb3V0LWJ1dHRvbi5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2xvZ2luLWZvcm0uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9uYXZpZ2F0aW9uLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb25zdGFudHMvYWN0aW9uLXR5cGVzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvZGlzcGF0Y2hlci9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2V4Y2hhbmdlLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9yZXF1ZXN0LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvc3RvcmVzL2NvbnNvbGUtc3RvcmUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlLmpzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBO0FDQUEsWUFBWSxDQUFDOztBQUViLElBQUksS0FBSyxHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUMsQ0FBQzs7QUFFN0IsSUFBSSxlQUFlLEdBQUcsT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUM7O0FBRS9ELEtBQUss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InNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzQ29udGVudCI6WyIoZnVuY3Rpb24gZSh0LG4scil7ZnVuY3Rpb24gcyhvLHUpe2lmKCFuW29dKXtpZighdFtvXSl7dmFyIGE9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtpZighdSYmYSlyZXR1cm4gYShvLCEwKTtpZihpKXJldHVybiBpKG8sITApO3ZhciBmPW5ldyBFcnJvcihcIkNhbm5vdCBmaW5kIG1vZHVsZSAnXCIrbytcIidcIik7dGhyb3cgZi5jb2RlPVwiTU9EVUxFX05PVF9GT1VORFwiLGZ9dmFyIGw9bltvXT17ZXhwb3J0czp7fX07dFtvXVswXS5jYWxsKGwuZXhwb3J0cyxmdW5jdGlvbihlKXt2YXIgbj10W29dWzFdW2VdO3JldHVybiBzKG4/bjplKX0sbCxsLmV4cG9ydHMsZSx0LG4scil9cmV0dXJuIG5bb10uZXhwb3J0c312YXIgaT10eXBlb2YgcmVxdWlyZT09XCJmdW5jdGlvblwiJiZyZXF1aXJlO2Zvcih2YXIgbz0wO288ci5sZW5ndGg7bysrKXMocltvXSk7cmV0dXJuIHN9KSIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIFBsYXRmb3JtTWFuYWdlciA9IHJlcXVpcmUoJy4vY29tcG9uZW50cy9wbGF0Zm9ybS1tYW5hZ2VyJyk7XG5cblJlYWN0LnJlbmRlcihcbiAgICA8UGxhdGZvcm1NYW5hZ2VyIC8+LFxuICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdhcHAnKVxuKTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIFJwY0V4Y2hhbmdlID0gcmVxdWlyZSgnLi4vbGliL3JwYy9leGNoYW5nZScpO1xuXG52YXIgY29uc29sZUFjdGlvbkNyZWF0b3JzID0ge1xuICAgIHRvZ2dsZUNvbnNvbGU6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuVE9HR0xFX0NPTlNPTEUsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgdXBkYXRlQ29tcG9zZXJWYWx1ZTogZnVuY3Rpb24gKHZhbHVlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlVQREFURV9DT01QT1NFUl9WQUxVRSxcbiAgICAgICAgICAgIHZhbHVlOiB2YWx1ZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBtYWtlUmVxdWVzdDogZnVuY3Rpb24gKG9wdHMpIHtcbiAgICAgICAgbmV3IFJwY0V4Y2hhbmdlKG9wdHMpLnByb21pc2UuY2F0Y2goZnVuY3Rpb24gaWdub3JlKCkge30pO1xuICAgIH1cbn07XG5cbm1vZHVsZS5leHBvcnRzID0gY29uc29sZUFjdGlvbkNyZWF0b3JzO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIHJwYyA9IHJlcXVpcmUoJy4uL2xpYi9ycGMnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0ge1xuICAgIHJlcXVlc3RBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAodXNlcm5hbWUsIHBhc3N3b3JkKSB7XG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAnZ2V0X2F1dGhvcml6YXRpb24nLFxuICAgICAgICAgICAgcGFyYW1zOiB7XG4gICAgICAgICAgICAgICAgdXNlcm5hbWU6IHVzZXJuYW1lLFxuICAgICAgICAgICAgICAgIHBhc3N3b3JkOiBwYXNzd29yZCxcbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChyZXN1bHQpIHtcbiAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTixcbiAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogcmVzdWx0LFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIC5jYXRjaChycGMuRXJyb3IsIGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgICAgIGlmIChlcnJvci5jb2RlICYmIGVycm9yLmNvZGUgPT09IDQwMSkge1xuICAgICAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSk7XG4gICAgfSxcbiAgICBjbGVhckF1dGhvcml6YXRpb246IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTixcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBnb1RvUGFnZTogZnVuY3Rpb24gKHBhZ2UpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuQ0hBTkdFX1BBR0UsXG4gICAgICAgICAgICBwYWdlOiBwYWdlLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIGxvYWRQbGF0Zm9ybXM6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGF1dGhvcml6YXRpb24gPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCk7XG5cbiAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICBtZXRob2Q6ICdsaXN0X3BsYXRmb3JtcycsXG4gICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocGxhdGZvcm1zKSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUyxcbiAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm1zOiBwbGF0Zm9ybXMsXG4gICAgICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgICAgICBwbGF0Zm9ybXMuZm9yRWFjaChmdW5jdGlvbiAocGxhdGZvcm0pIHtcbiAgICAgICAgICAgICAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcubGlzdF9hZ2VudHMnLFxuICAgICAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgICAgICAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKGFnZW50c0xpc3QpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybS5hZ2VudHMgPSBhZ2VudHNMaXN0O1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAoIWFnZW50c0xpc3QubGVuZ3RoKSB7IHJldHVybjsgfVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5zdGF0dXNfYWdlbnRzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChhZ2VudFN0YXR1c2VzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybS5hZ2VudHMuZm9yRWFjaChmdW5jdGlvbiAoYWdlbnQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAoIWFnZW50U3RhdHVzZXMuc29tZShmdW5jdGlvbiAoc3RhdHVzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChhZ2VudC51dWlkID09PSBzdGF0dXMudXVpZCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IGZhbHNlO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucHJvY2Vzc19pZCA9IHN0YXR1cy5wcm9jZXNzX2lkO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBzdGF0dXMucmV0dXJuX2NvZGU7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSkpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IGZhbHNlO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5wcm9jZXNzX2lkID0gbnVsbDtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBudWxsO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIC5jYXRjaChmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBpZiAoZXJyb3IuY29kZSAmJiBlcnJvci5jb2RlID09PSA0MDEpIHtcbiAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQsXG4gICAgICAgICAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgc3RhcnRBZ2VudDogZnVuY3Rpb24gKHBsYXRmb3JtLCBhZ2VudCkge1xuICAgICAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcblxuICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gdHJ1ZTtcblxuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICB9KTtcblxuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5zdGFydF9hZ2VudCcsXG4gICAgICAgICAgICBwYXJhbXM6IFthZ2VudC51dWlkXSxcbiAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChzdGF0dXMpIHtcbiAgICAgICAgICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gZmFsc2U7XG4gICAgICAgICAgICAgICAgYWdlbnQucHJvY2Vzc19pZCA9IHN0YXR1cy5wcm9jZXNzX2lkO1xuICAgICAgICAgICAgICAgIGFnZW50LnJldHVybl9jb2RlID0gc3RhdHVzLnJldHVybl9jb2RlO1xuXG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KTtcbiAgICB9LFxuICAgIHN0b3BBZ2VudDogZnVuY3Rpb24gKHBsYXRmb3JtLCBhZ2VudCkge1xuICAgICAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcblxuICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gdHJ1ZTtcblxuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICB9KTtcblxuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5zdG9wX2FnZW50JyxcbiAgICAgICAgICAgIHBhcmFtczogW2FnZW50LnV1aWRdLFxuICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHN0YXR1cykge1xuICAgICAgICAgICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICBhZ2VudC5wcm9jZXNzX2lkID0gc3RhdHVzLnByb2Nlc3NfaWQ7XG4gICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBzdGF0dXMucmV0dXJuX2NvZGU7XG5cbiAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk0sXG4gICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG59O1xuXG53aW5kb3cub25oYXNoY2hhbmdlID0gZnVuY3Rpb24gKCkge1xuICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLmdvVG9QYWdlKGxvY2F0aW9uLmhhc2guc3Vic3RyKDEpKTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnM7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xuXG52YXIgQWdlbnRSb3cgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgX29uU3RvcDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5zdG9wQWdlbnQodGhpcy5wcm9wcy5wbGF0Zm9ybSwgdGhpcy5wcm9wcy5hZ2VudCk7XG4gICAgfSxcbiAgICBfb25TdGFydDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5zdGFydEFnZW50KHRoaXMucHJvcHMucGxhdGZvcm0sIHRoaXMucHJvcHMuYWdlbnQpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBhZ2VudCA9IHRoaXMucHJvcHMuYWdlbnQsIHN0YXR1cywgYWN0aW9uO1xuXG4gICAgICAgIGlmIChhZ2VudC5hY3Rpb25QZW5kaW5nID09PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgIHN0YXR1cyA9ICdSZXRyaWV2aW5nIHN0YXR1cy4uLic7XG4gICAgICAgIH0gZWxzZSBpZiAoYWdlbnQuYWN0aW9uUGVuZGluZykge1xuICAgICAgICAgICAgaWYgKGFnZW50LnByb2Nlc3NfaWQgPT09IG51bGwgfHwgYWdlbnQucmV0dXJuX2NvZGUgIT09IG51bGwpIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnU3RhcnRpbmcuLi4nO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0YXJ0XCIgZGlzYWJsZWQgLz5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnU3RvcHBpbmcuLi4nO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0b3BcIiBkaXNhYmxlZCAvPlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBpZiAoYWdlbnQucHJvY2Vzc19pZCA9PT0gbnVsbCkge1xuICAgICAgICAgICAgICAgIHN0YXR1cyA9ICdOZXZlciBzdGFydGVkJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdGFydFwiIG9uQ2xpY2s9e3RoaXMuX29uU3RhcnR9IC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSBpZiAoYWdlbnQucmV0dXJuX2NvZGUgPT09IG51bGwpIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnUnVubmluZyAoUElEICcgKyBhZ2VudC5wcm9jZXNzX2lkICsgJyknO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0b3BcIiBvbkNsaWNrPXt0aGlzLl9vblN0b3B9IC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgc3RhdHVzID0gJ1N0b3BwZWQgKHJldHVybmVkICcgKyBhZ2VudC5yZXR1cm5fY29kZSArICcpJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdGFydFwiIG9uQ2xpY2s9e3RoaXMuX29uU3RhcnR9IC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8dHI+XG4gICAgICAgICAgICAgICAgPHRkPnthZ2VudC5uYW1lfTwvdGQ+XG4gICAgICAgICAgICAgICAgPHRkPnthZ2VudC51dWlkfTwvdGQ+XG4gICAgICAgICAgICAgICAgPHRkPntzdGF0dXN9PC90ZD5cbiAgICAgICAgICAgICAgICA8dGQ+e2FjdGlvbn08L3RkPlxuICAgICAgICAgICAgPC90cj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gQWdlbnRSb3c7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBjb25zb2xlQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xuXG52YXIgQ29tcG9zZXIgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5yZXBsYWNlU3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uU2VuZENsaWNrOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy5tYWtlUmVxdWVzdChKU09OLnBhcnNlKHRoaXMuc3RhdGUuY29tcG9zZXJWYWx1ZSkpO1xuICAgIH0sXG4gICAgX29uVGV4dGFyZWFDaGFuZ2U6IGZ1bmN0aW9uIChlKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy51cGRhdGVDb21wb3NlclZhbHVlKGUudGFyZ2V0LnZhbHVlKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJjb21wb3NlclwiPlxuICAgICAgICAgICAgICAgIDx0ZXh0YXJlYVxuICAgICAgICAgICAgICAgICAgICBrZXk9e3RoaXMuc3RhdGUuY29tcG9zZXJJZH1cbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3RoaXMuX29uVGV4dGFyZWFDaGFuZ2V9XG4gICAgICAgICAgICAgICAgICAgIGRlZmF1bHRWYWx1ZT17dGhpcy5zdGF0ZS5jb21wb3NlclZhbHVlfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHJlZj1cInNlbmRcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9XCJTZW5kXCJcbiAgICAgICAgICAgICAgICAgICAgZGlzYWJsZWQ9eyF0aGlzLnN0YXRlLnZhbGlkfVxuICAgICAgICAgICAgICAgICAgICBvbkNsaWNrPXt0aGlzLl9vblNlbmRDbGlja31cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfSxcbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgdmFyIGNvbXBvc2VyVmFsdWUgPSBjb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJWYWx1ZSgpO1xuICAgIHZhciB2YWxpZCA9IHRydWU7XG5cbiAgICB0cnkge1xuICAgICAgICBKU09OLnBhcnNlKGNvbXBvc2VyVmFsdWUpO1xuICAgIH0gY2F0Y2ggKGV4KSB7XG4gICAgICAgIGlmIChleCBpbnN0YW5jZW9mIFN5bnRheEVycm9yKSB7XG4gICAgICAgICAgICB2YWxpZCA9IGZhbHNlO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgdGhyb3cgZXg7XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgICBjb21wb3NlcklkOiBjb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJJZCgpLFxuICAgICAgICBjb21wb3NlclZhbHVlOiBjb21wb3NlclZhbHVlLFxuICAgICAgICB2YWxpZDogdmFsaWQsXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBDb21wb3NlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIENvbXBvc2VyID0gcmVxdWlyZSgnLi9jb21wb3NlcicpO1xudmFyIENvbnZlcnNhdGlvbiA9IHJlcXVpcmUoJy4vY29udmVyc2F0aW9uJyk7XG5cbnZhciBDb25zb2xlID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJjb25zb2xlXCI+XG4gICAgICAgICAgICAgICAgPENvbnZlcnNhdGlvbiAvPlxuICAgICAgICAgICAgICAgIDxDb21wb3NlciAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gQ29uc29sZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyICQgPSByZXF1aXJlKCdqcXVlcnknKTtcbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBFeGNoYW5nZSA9IHJlcXVpcmUoJy4vZXhjaGFuZ2UnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xuXG52YXIgQ29udmVyc2F0aW9uID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciAkY29udmVyc2F0aW9uID0gJCh0aGlzLnJlZnMuY29udmVyc2F0aW9uLmdldERPTU5vZGUoKSk7XG5cbiAgICAgICAgaWYgKCRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykgPiAkY29udmVyc2F0aW9uLmhlaWdodCgpKSB7XG4gICAgICAgICAgICAkY29udmVyc2F0aW9uLnNjcm9sbFRvcCgkY29udmVyc2F0aW9uLnByb3AoJ3Njcm9sbEhlaWdodCcpKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnNvbGVTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBjb21wb25lbnREaWRVcGRhdGU6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyICRjb252ZXJzYXRpb24gPSAkKHRoaXMucmVmcy5jb252ZXJzYXRpb24uZ2V0RE9NTm9kZSgpKTtcblxuICAgICAgICAkY29udmVyc2F0aW9uLnN0b3AoKS5hbmltYXRlKHsgc2Nyb2xsVG9wOiAkY29udmVyc2F0aW9uLnByb3AoJ3Njcm9sbEhlaWdodCcpIH0sIDUwMCk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IHJlZj1cImNvbnZlcnNhdGlvblwiIGNsYXNzTmFtZT1cImNvbnZlcnNhdGlvblwiPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmV4Y2hhbmdlcy5tYXAoZnVuY3Rpb24gKGV4Y2hhbmdlLCBpbmRleCkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPEV4Y2hhbmdlIGtleT17aW5kZXh9IGV4Y2hhbmdlPXtleGNoYW5nZX0gLz5cbiAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHsgZXhjaGFuZ2VzOiBjb25zb2xlU3RvcmUuZ2V0RXhjaGFuZ2VzKCkgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBDb252ZXJzYXRpb247XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBFeGNoYW5nZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfZm9ybWF0VGltZTogZnVuY3Rpb24gKHRpbWUpIHtcbiAgICAgICAgdmFyIGQgPSBuZXcgRGF0ZSgpO1xuXG4gICAgICAgIGQuc2V0VGltZSh0aW1lKTtcblxuICAgICAgICByZXR1cm4gZC50b0xvY2FsZVN0cmluZygpO1xuICAgIH0sXG4gICAgX2Zvcm1hdE1lc3NhZ2U6IGZ1bmN0aW9uIChtZXNzYWdlKSB7XG4gICAgICAgIHJldHVybiBKU09OLnN0cmluZ2lmeShtZXNzYWdlLCBudWxsLCAnICAgICcpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBleGNoYW5nZSA9IHRoaXMucHJvcHMuZXhjaGFuZ2U7XG4gICAgICAgIHZhciBjbGFzc2VzID0gWydyZXNwb25zZSddO1xuICAgICAgICB2YXIgcmVzcG9uc2VUZXh0O1xuXG4gICAgICAgIGlmICghZXhjaGFuZ2UuY29tcGxldGVkKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1wZW5kaW5nJyk7XG4gICAgICAgICAgICByZXNwb25zZVRleHQgPSAnV2FpdGluZyBmb3IgcmVzcG9uc2UuLi4nO1xuICAgICAgICB9IGVsc2UgaWYgKGV4Y2hhbmdlLmVycm9yKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1lcnJvcicpO1xuICAgICAgICAgICAgcmVzcG9uc2VUZXh0ID0gZXhjaGFuZ2UuZXJyb3IubWVzc2FnZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGlmIChleGNoYW5nZS5yZXNwb25zZS5lcnJvcikge1xuICAgICAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncmVzcG9uc2UtLWVycm9yJyk7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9IHRoaXMuX2Zvcm1hdE1lc3NhZ2UoZXhjaGFuZ2UucmVzcG9uc2UpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXhjaGFuZ2VcIj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInJlcXVlc3RcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJ0aW1lXCI+e3RoaXMuX2Zvcm1hdFRpbWUoZXhjaGFuZ2UuaW5pdGlhdGVkKX08L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgPHByZT57dGhpcy5fZm9ybWF0TWVzc2FnZShleGNoYW5nZS5yZXF1ZXN0KX08L3ByZT5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT17Y2xhc3Nlcy5qb2luKCcgJyl9PlxuICAgICAgICAgICAgICAgICAgICB7ZXhjaGFuZ2UuY29tcGxldGVkICYmIDxkaXYgY2xhc3NOYW1lPVwidGltZVwiPnt0aGlzLl9mb3JtYXRUaW1lKGV4Y2hhbmdlLmNvbXBsZXRlZCl9PC9kaXY+fVxuICAgICAgICAgICAgICAgICAgICA8cHJlPntyZXNwb25zZVRleHR9PC9wcmU+XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBFeGNoYW5nZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIEFnZW50Um93ID0gcmVxdWlyZSgnLi9hZ2VudC1yb3cnKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcblxudmFyIEhvbWUgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgICAgICBzZXRUaW1lb3V0KHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLmxvYWRQbGF0Zm9ybXMpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBwbGF0Zm9ybXM7XG5cbiAgICAgICAgaWYgKCF0aGlzLnN0YXRlLnBsYXRmb3Jtcykge1xuICAgICAgICAgICAgcGxhdGZvcm1zID0gKFxuICAgICAgICAgICAgICAgIDxwPkxvYWRpbmcgcGxhdGZvcm1zLi4uPC9wPlxuICAgICAgICAgICAgKTtcbiAgICAgICAgfSBlbHNlIGlmICghdGhpcy5zdGF0ZS5wbGF0Zm9ybXMubGVuZ3RoKSB7XG4gICAgICAgICAgICBwbGF0Zm9ybXMgPSAoXG4gICAgICAgICAgICAgICAgPHA+Tm8gcGxhdGZvcm1zIGZvdW5kLjwvcD5cbiAgICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBwbGF0Zm9ybXMgPSB0aGlzLnN0YXRlLnBsYXRmb3Jtcy5tYXAoZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgdmFyIGFnZW50cztcblxuICAgICAgICAgICAgICAgIGlmICghcGxhdGZvcm0uYWdlbnRzKSB7XG4gICAgICAgICAgICAgICAgICAgIGFnZW50cyA9IChcbiAgICAgICAgICAgICAgICAgICAgICAgIDxwPkxvYWRpbmcgYWdlbnRzLi4uPC9wPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAoIXBsYXRmb3JtLmFnZW50cy5sZW5ndGgpIHtcbiAgICAgICAgICAgICAgICAgICAgYWdlbnRzID0gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPHA+Tm8gYWdlbnRzIGluc3RhbGxlZC48L3A+XG4gICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgYWdlbnRzID0gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPHRhYmxlPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aGVhZD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRyPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoPkFnZW50PC90aD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5VVUlEPC90aD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5TdGF0dXM8L3RoPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoPkFjdGlvbjwvdGg+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvdHI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90aGVhZD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGJvZHk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtwbGF0Zm9ybS5hZ2VudHMubWFwKGZ1bmN0aW9uIChhZ2VudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8QWdlbnRSb3dcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAga2V5PXthZ2VudC51dWlkfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybT17cGxhdGZvcm19XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50PXthZ2VudH0gLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvdGJvZHk+XG4gICAgICAgICAgICAgICAgICAgICAgICA8L3RhYmxlPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwicGxhdGZvcm1cIiBrZXk9e3BsYXRmb3JtLnV1aWR9PlxuICAgICAgICAgICAgICAgICAgICAgICAgPGgyPntwbGF0Zm9ybS5uYW1lfSAoe3BsYXRmb3JtLnV1aWR9KTwvaDI+XG4gICAgICAgICAgICAgICAgICAgICAgICB7YWdlbnRzfVxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfSk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJob21lXCI+XG4gICAgICAgICAgICAgICAge3BsYXRmb3Jtc31cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH0sXG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7XG4gICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGxhdGZvcm1zKCksXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBIb21lO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcblxudmFyIExvZ091dEJ1dHRvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfb25DbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5jbGVhckF1dGhvcml6YXRpb24oKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGJ1dHRvbiBjbGFzc05hbWU9XCJidXR0b25cIiBvbkNsaWNrPXt0aGlzLl9vbkNsaWNrfT5Mb2cgb3V0PC9idXR0b24+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTG9nT3V0QnV0dG9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBsb2dpbkZvcm1TdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9sb2dpbi1mb3JtLXN0b3JlJyk7XG5cbnZhciBMb2dpbkZvcm0gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25TdG9yZXNDaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25TdG9yZXNDaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uU3RvcmVzQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uSW5wdXRDaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZSh7XG4gICAgICAgICAgICB1c2VybmFtZTogdGhpcy5yZWZzLnVzZXJuYW1lLmdldERPTU5vZGUoKS52YWx1ZSxcbiAgICAgICAgICAgIHBhc3N3b3JkOiB0aGlzLnJlZnMucGFzc3dvcmQuZ2V0RE9NTm9kZSgpLnZhbHVlLFxuICAgICAgICAgICAgZXJyb3I6IG51bGwsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgX29uU3VibWl0OiBmdW5jdGlvbiAoZSkge1xuICAgICAgICBlLnByZXZlbnREZWZhdWx0KCk7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLnJlcXVlc3RBdXRob3JpemF0aW9uKFxuICAgICAgICAgICAgdGhpcy5zdGF0ZS51c2VybmFtZSxcbiAgICAgICAgICAgIHRoaXMuc3RhdGUucGFzc3dvcmRcbiAgICAgICAgKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGZvcm0gY2xhc3NOYW1lPVwibG9naW4tZm9ybVwiIG9uU3VibWl0PXt0aGlzLl9vblN1Ym1pdH0+XG4gICAgICAgICAgICAgICAgPGgxPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9oMT5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwidXNlcm5hbWVcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwidGV4dFwiXG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiVXNlcm5hbWVcIlxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25JbnB1dENoYW5nZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICByZWY9XCJwYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJwYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiUGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25JbnB1dENoYW5nZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwic3VibWl0XCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9XCJMb2cgaW5cIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudXNlcm5hbWUgfHwgIXRoaXMuc3RhdGUucGFzc3dvcmR9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5lcnJvciA/IChcbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJlcnJvclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXJyb3IubWVzc2FnZX0gKHt0aGlzLnN0YXRlLmVycm9yLmNvZGV9KVxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICApIDogbnVsbCB9XG4gICAgICAgICAgICA8L2Zvcm0+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4geyBlcnJvcjogbG9naW5Gb3JtU3RvcmUuZ2V0TGFzdEVycm9yKCkgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBMb2dpbkZvcm07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBMb2dPdXRCdXR0b24gPSByZXF1aXJlKCcuL2xvZy1vdXQtYnV0dG9uJyk7XG5cbnZhciBOYXZpZ2F0aW9uID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJuYXZpZ2F0aW9uXCI+XG4gICAgICAgICAgICAgICAgPGgxPjxhIGhyZWY9XCIjaG9tZVwiPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9hPjwvaDE+XG4gICAgICAgICAgICAgICAgPExvZ091dEJ1dHRvbiAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTmF2aWdhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIENvbnNvbGUgPSByZXF1aXJlKCcuL2NvbnNvbGUnKTtcbnZhciBjb25zb2xlQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xudmFyIEhvbWUgPSByZXF1aXJlKCcuL2hvbWUnKTtcbnZhciBMb2dpbkZvcm0gPSByZXF1aXJlKCcuL2xvZ2luLWZvcm0nKTtcbnZhciBOYXZpZ2F0aW9uID0gcmVxdWlyZSgnLi9uYXZpZ2F0aW9uJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgUGxhdGZvcm1NYW5hZ2VyID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIF9vbkJ1dHRvbkNsaWNrOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy50b2dnbGVDb25zb2xlKCk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGNsYXNzZXMgPSBbJ3BsYXRmb3JtLW1hbmFnZXInXTtcblxuICAgICAgICBpZiAoIXRoaXMuc3RhdGUuY29uc29sZVNob3duKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3BsYXRmb3JtLW1hbmFnZXItLWNvbnNvbGUtaGlkZGVuJyk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9e2NsYXNzZXMuam9pbignICcpfT5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIm1haW5cIj5cbiAgICAgICAgICAgICAgICAgICAgeyF0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxMb2dpbkZvcm0gLz59XG4gICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxOYXZpZ2F0aW9uIC8+fVxuICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8SG9tZSAvPn1cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwidG9nZ2xlIGJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT17J0NvbnNvbGUgJyArICh0aGlzLnN0YXRlLmNvbnNvbGVTaG93biA/ICdcXHUyNWJjJyA6ICdcXHUyNWIyJyl9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uQnV0dG9uQ2xpY2t9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5jb25zb2xlU2hvd24gJiYgPENvbnNvbGUgY2xhc3NOYW1lPVwiY29uc29sZVwiIC8+fVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4ge1xuICAgICAgICBjb25zb2xlU2hvd246IGNvbnNvbGVTdG9yZS5nZXRDb25zb2xlU2hvd24oKSxcbiAgICAgICAgbG9nZ2VkSW46ICEhcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpLFxuICAgIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gUGxhdGZvcm1NYW5hZ2VyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIga2V5TWlycm9yID0gcmVxdWlyZSgncmVhY3QvbGliL2tleU1pcnJvcicpO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGtleU1pcnJvcih7XG4gICAgVE9HR0xFX0NPTlNPTEU6IG51bGwsXG5cbiAgICBVUERBVEVfQ09NUE9TRVJfVkFMVUU6IG51bGwsXG5cbiAgICBNQUtFX1JFUVVFU1Q6IG51bGwsXG4gICAgRkFJTF9SRVFVRVNUOiBudWxsLFxuICAgIFJFQ0VJVkVfUkVTUE9OU0U6IG51bGwsXG5cbiAgICBSRUNFSVZFX0FVVEhPUklaQVRJT046IG51bGwsXG4gICAgUkVDRUlWRV9VTkFVVEhPUklaRUQ6IG51bGwsXG4gICAgQ0xFQVJfQVVUSE9SSVpBVElPTjogbnVsbCxcblxuICAgIENIQU5HRV9QQUdFOiBudWxsLFxuXG4gICAgUkVDRUlWRV9QTEFURk9STVM6IG51bGwsXG4gICAgUkVDRUlWRV9QTEFURk9STTogbnVsbCxcbn0pO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgRGlzcGF0Y2hlciA9IHJlcXVpcmUoJ2ZsdXgnKS5EaXNwYXRjaGVyO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xuXG52YXIgZGlzcGF0Y2hlciA9IG5ldyBEaXNwYXRjaGVyKCk7XG5cbmRpc3BhdGNoZXIuZGlzcGF0Y2ggPSBmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgaWYgKGFjdGlvbi50eXBlIGluIEFDVElPTl9UWVBFUykge1xuICAgICAgICByZXR1cm4gT2JqZWN0LmdldFByb3RvdHlwZU9mKHRoaXMpLmRpc3BhdGNoLmNhbGwodGhpcywgYWN0aW9uKTtcbiAgICB9XG5cbiAgICB0aHJvdyAnRGlzcGF0Y2ggZXJyb3I6IGludmFsaWQgYWN0aW9uIHR5cGUgJyArIGFjdGlvbi50eXBlO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBkaXNwYXRjaGVyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5mdW5jdGlvbiBScGNFcnJvcihlcnJvcikge1xuICAgIHRoaXMubmFtZSA9ICdScGNFcnJvcic7XG4gICAgdGhpcy5jb2RlID0gZXJyb3IuY29kZTtcbiAgICB0aGlzLm1lc3NhZ2UgPSBlcnJvci5tZXNzYWdlO1xuICAgIHRoaXMuZGF0YSA9IGVycm9yLmRhdGE7XG59XG5ScGNFcnJvci5wcm90b3R5cGUgPSBPYmplY3QuY3JlYXRlKEVycm9yLnByb3RvdHlwZSk7XG5ScGNFcnJvci5wcm90b3R5cGUuY29uc3RydWN0b3IgPSBScGNFcnJvcjtcblxubW9kdWxlLmV4cG9ydHMgPSBScGNFcnJvcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIHV1aWQgPSByZXF1aXJlKCdub2RlLXV1aWQnKTtcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uLy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vLi4vZGlzcGF0Y2hlcicpO1xudmFyIFJwY0Vycm9yID0gcmVxdWlyZSgnLi9lcnJvcicpO1xudmFyIHhociA9IHJlcXVpcmUoJy4uL3hocicpO1xuXG5mdW5jdGlvbiBScGNFeGNoYW5nZShvcHRzKSB7XG4gICAgaWYgKCF0aGlzIGluc3RhbmNlb2YgUnBjRXhjaGFuZ2UpIHtcbiAgICAgICAgcmV0dXJuIG5ldyBScGNFeGNoYW5nZShvcHRzKTtcbiAgICB9XG5cbiAgICB2YXIgZXhjaGFuZ2UgPSB0aGlzO1xuXG4gICAgLy8gVE9ETzogdmFsaWRhdGUgb3B0c1xuICAgIG9wdHMuanNvbnJwYyA9ICcyLjAnO1xuICAgIG9wdHMuaWQgPSB1dWlkLnYxKCk7XG5cbiAgICBleGNoYW5nZS5pbml0aWF0ZWQgPSBEYXRlLm5vdygpO1xuICAgIGV4Y2hhbmdlLnJlcXVlc3QgPSBvcHRzO1xuXG4gICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5NQUtFX1JFUVVFU1QsXG4gICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgcmVxdWVzdDogZXhjaGFuZ2UucmVxdWVzdCxcbiAgICB9KTtcblxuICAgIGV4Y2hhbmdlLnByb21pc2UgPSBuZXcgeGhyLlJlcXVlc3Qoe1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgdXJsOiAnL2pzb25ycGMnLFxuICAgICAgICBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBkYXRhOiBKU09OLnN0cmluZ2lmeShleGNoYW5nZS5yZXF1ZXN0KSxcbiAgICAgICAgdGltZW91dDogNjAwMDAsXG4gICAgfSlcbiAgICAgICAgLmZpbmFsbHkoZnVuY3Rpb24gKCkge1xuICAgICAgICAgICAgZXhjaGFuZ2UuY29tcGxldGVkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgfSlcbiAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHJlc3BvbnNlKSB7XG4gICAgICAgICAgICBleGNoYW5nZS5yZXNwb25zZSA9IHJlc3BvbnNlO1xuXG4gICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9SRVNQT05TRSxcbiAgICAgICAgICAgICAgICBleGNoYW5nZTogZXhjaGFuZ2UsXG4gICAgICAgICAgICAgICAgcmVzcG9uc2U6IHJlc3BvbnNlLFxuICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgIGlmIChyZXNwb25zZS5lcnJvcikge1xuICAgICAgICAgICAgICAgIHRocm93IG5ldyBScGNFcnJvcihyZXNwb25zZS5lcnJvcik7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJldHVybiByZXNwb25zZS5yZXN1bHQ7XG4gICAgICAgIH0pXG4gICAgICAgIC5jYXRjaCh4aHIuRXJyb3IsIGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgZXhjaGFuZ2UuZXJyb3IgPSBlcnJvcjtcblxuICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkZBSUxfUkVRVUVTVCxcbiAgICAgICAgICAgICAgICBleGNoYW5nZTogZXhjaGFuZ2UsXG4gICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLFxuICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICB9KTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBScGNFeGNoYW5nZTtcbiIsIid1c2Ugc3RyaWN0JztcblxubW9kdWxlLmV4cG9ydHMgPSB7XG4gICAgRXJyb3I6IHJlcXVpcmUoJy4vZXJyb3InKSxcbiAgICBFeGNoYW5nZTogcmVxdWlyZSgnLi9leGNoYW5nZScpLFxufTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEV2ZW50RW1pdHRlciA9IHJlcXVpcmUoJ2V2ZW50cycpLkV2ZW50RW1pdHRlcjtcblxudmFyIENIQU5HRV9FVkVOVCA9ICdjaGFuZ2UnO1xuXG5mdW5jdGlvbiBTdG9yZSgpIHtcbiAgICBFdmVudEVtaXR0ZXIuY2FsbCh0aGlzKTtcbn1cblN0b3JlLnByb3RvdHlwZSA9IEV2ZW50RW1pdHRlci5wcm90b3R5cGU7XG5cblN0b3JlLnByb3RvdHlwZS5lbWl0Q2hhbmdlID0gZnVuY3Rpb24oKSB7XG4gICAgdGhpcy5lbWl0KENIQU5HRV9FVkVOVCk7XG59O1xuXG5TdG9yZS5wcm90b3R5cGUuYWRkQ2hhbmdlTGlzdGVuZXIgPSBmdW5jdGlvbiAoY2FsbGJhY2spIHtcbiAgICB0aGlzLm9uKENIQU5HRV9FVkVOVCwgY2FsbGJhY2spO1xufTtcblxuU3RvcmUucHJvdG90eXBlLnJlbW92ZUNoYW5nZUxpc3RlbmVyID0gZnVuY3Rpb24gKGNhbGxiYWNrKSB7XG4gICAgdGhpcy5yZW1vdmVMaXN0ZW5lcihDSEFOR0VfRVZFTlQsIGNhbGxiYWNrKTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbmZ1bmN0aW9uIFhockVycm9yKG1lc3NhZ2UsIHJlc3BvbnNlKSB7XG4gICAgdGhpcy5uYW1lID0gJ1hockVycm9yJztcbiAgICB0aGlzLm1lc3NhZ2UgPSBtZXNzYWdlO1xuICAgIHRoaXMucmVzcG9uc2UgPSByZXNwb25zZTtcbn1cblhockVycm9yLnByb3RvdHlwZSA9IE9iamVjdC5jcmVhdGUoRXJyb3IucHJvdG90eXBlKTtcblhockVycm9yLnByb3RvdHlwZS5jb25zdHJ1Y3RvciA9IFhockVycm9yO1xuXG5tb2R1bGUuZXhwb3J0cyA9IFhockVycm9yO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5tb2R1bGUuZXhwb3J0cyA9IHtcbiAgICBSZXF1ZXN0OiByZXF1aXJlKCcuL3JlcXVlc3QnKSxcbiAgICBFcnJvcjogcmVxdWlyZSgnLi9lcnJvcicpLFxufTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIGpRdWVyeSA9IHJlcXVpcmUoJ2pxdWVyeScpO1xudmFyIFByb21pc2UgPSByZXF1aXJlKCdibHVlYmlyZCcpO1xuXG52YXIgWGhyRXJyb3IgPSByZXF1aXJlKCcuL2Vycm9yJyk7XG5cbmZ1bmN0aW9uIFhoclJlcXVlc3Qob3B0cykge1xuICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbiAocmVzb2x2ZSwgcmVqZWN0KSB7XG4gICAgICAgIG9wdHMuc3VjY2VzcyA9IHJlc29sdmU7XG4gICAgICAgIG9wdHMuZXJyb3IgPSBmdW5jdGlvbiAocmVzcG9uc2UsIHR5cGUpIHtcbiAgICAgICAgICAgIHN3aXRjaCAodHlwZSkge1xuICAgICAgICAgICAgY2FzZSAnZXJyb3InOlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1NlcnZlciByZXR1cm5lZCAnICsgcmVzcG9uc2Uuc3RhdHVzICsgJyBzdGF0dXMnLCByZXNwb25zZSkpO1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgY2FzZSAndGltZW91dCc6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignUmVxdWVzdCB0aW1lZCBvdXQnLCByZXNwb25zZSkpO1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdSZXF1ZXN0IGZhaWxlZDogJyArIHR5cGUsIHJlc3BvbnNlKSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH07XG5cbiAgICAgICAgalF1ZXJ5LmFqYXgob3B0cyk7XG4gICAgfSk7XG59XG5cbm1vZHVsZS5leHBvcnRzID0gWGhyUmVxdWVzdDtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbnZhciBfY29tcG9zZXJWYWx1ZSA9ICcnO1xudmFyIF9jb25zb2xlU2hvd24gPSBmYWxzZTtcbnZhciBfZXhjaGFuZ2VzID0gW107XG5cbnZhciBjb25zb2xlU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxuY29uc29sZVN0b3JlLmdldENvbXBvc2VySWQgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9jb21wb3NlcklkO1xufTtcblxuY29uc29sZVN0b3JlLmdldENvbXBvc2VyVmFsdWUgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9jb21wb3NlclZhbHVlO1xufTtcblxuY29uc29sZVN0b3JlLmdldENvbnNvbGVTaG93biA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2NvbnNvbGVTaG93bjtcbn07XG5cbmNvbnNvbGVTdG9yZS5nZXRFeGNoYW5nZXMgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9leGNoYW5nZXM7XG59O1xuXG5mdW5jdGlvbiBfcmVzZXRDb21wb3NlclZhbHVlKHVwZGF0ZU1ldGhvZCkge1xuICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuICAgIHZhciBwYXJzZWQ7XG5cbiAgICB0cnkge1xuICAgICAgICBwYXJzZWQgPSBKU09OLnBhcnNlKF9jb21wb3NlclZhbHVlKTtcblxuICAgICAgICBpZiAodXBkYXRlTWV0aG9kKSB7XG4gICAgICAgICAgICBwYXJzZWQubWV0aG9kID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGFnZSgpO1xuICAgICAgICB9XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBwYXJzZWQgPSB7IG1ldGhvZDogcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGFnZSgpIH07XG4gICAgfVxuXG4gICAgaWYgKGF1dGhvcml6YXRpb24pIHtcbiAgICAgICAgcGFyc2VkLmF1dGhvcml6YXRpb24gPSBhdXRob3JpemF0aW9uO1xuICAgIH0gZWxzZSB7XG4gICAgICAgIGRlbGV0ZSBwYXJzZWQuYXV0aG9yaXphdGlvbjtcbiAgICB9XG5cbiAgICBfY29tcG9zZXJWYWx1ZSA9IEpTT04uc3RyaW5naWZ5KHBhcnNlZCwgbnVsbCwgJyAgICAnKTtcbn1cblxuX3Jlc2V0Q29tcG9zZXJWYWx1ZSgpO1xuXG5jb25zb2xlU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGRpc3BhdGNoZXIud2FpdEZvcihbcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbl0pO1xuXG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5UT0dHTEVfQ09OU09MRTpcbiAgICAgICAgICAgIF9jb25zb2xlU2hvd24gPSAhX2NvbnNvbGVTaG93bjtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5VUERBVEVfQ09NUE9TRVJfVkFMVUU6XG4gICAgICAgICAgICBfY29tcG9zZXJWYWx1ZSA9IGFjdGlvbi52YWx1ZTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DTEVBUl9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2NvbXBvc2VySWQgPSBEYXRlLm5vdygpO1xuICAgICAgICAgICAgX3Jlc2V0Q29tcG9zZXJWYWx1ZSgpO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFOlxuICAgICAgICAgICAgX2NvbXBvc2VySWQgPSBEYXRlLm5vdygpO1xuICAgICAgICAgICAgX3Jlc2V0Q29tcG9zZXJWYWx1ZSh0cnVlKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5NQUtFX1JFUVVFU1Q6XG4gICAgICAgICAgICBfZXhjaGFuZ2VzLnB1c2goYWN0aW9uLmV4Y2hhbmdlKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5GQUlMX1JFUVVFU1Q6XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUkVTUE9OU0U6XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gY29uc29sZVN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2xhc3RFcnJvciA9IG51bGw7XG5cbnZhciBsb2dpbkZvcm1TdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5sb2dpbkZvcm1TdG9yZS5nZXRMYXN0RXJyb3IgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9sYXN0RXJyb3I7XG59O1xuXG5sb2dpbkZvcm1TdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgZGlzcGF0Y2hlci53YWl0Rm9yKFtwbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuXSk7XG5cbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9sYXN0RXJyb3IgPSBudWxsO1xuICAgICAgICAgICAgbG9naW5Gb3JtU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQ6XG4gICAgICAgICAgICBfbGFzdEVycm9yID0gYWN0aW9uLmVycm9yO1xuICAgICAgICAgICAgbG9naW5Gb3JtU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gbG9naW5Gb3JtU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2F1dGhvcml6YXRpb24gPSBzZXNzaW9uU3RvcmFnZS5nZXRJdGVtKCdhdXRob3JpemF0aW9uJyk7XG52YXIgX3BhZ2UgPSBsb2NhdGlvbi5oYXNoLnN1YnN0cigxKTtcbnZhciBfcGxhdGZvcm1zID0gbnVsbDtcblxudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gbmV3IFN0b3JlKCk7XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24gPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9hdXRob3JpemF0aW9uO1xufTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGFnZSA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX3BhZ2U7XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQbGF0Zm9ybXMgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9wbGF0Zm9ybXM7XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfYXV0aG9yaXphdGlvbiA9IGFjdGlvbi5hdXRob3JpemF0aW9uO1xuICAgICAgICAgICAgc2Vzc2lvblN0b3JhZ2Uuc2V0SXRlbSgnYXV0aG9yaXphdGlvbicsIF9hdXRob3JpemF0aW9uKTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DTEVBUl9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2F1dGhvcml6YXRpb24gPSBudWxsO1xuICAgICAgICAgICAgc2Vzc2lvblN0b3JhZ2UucmVtb3ZlSXRlbSgnYXV0aG9yaXphdGlvbicpO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0hBTkdFX1BBR0U6XG4gICAgICAgICAgICBfcGFnZSA9IGFjdGlvbi5wYWdlO1xuICAgICAgICAgICAgbG9jYXRpb24uaGFzaCA9ICcjJyArIGFjdGlvbi5wYWdlO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STVM6XG4gICAgICAgICAgICBfcGxhdGZvcm1zID0gYWN0aW9uLnBsYXRmb3JtcztcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk06XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZTtcbiJdfQ==
