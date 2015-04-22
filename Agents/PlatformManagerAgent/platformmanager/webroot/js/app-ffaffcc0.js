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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYXBwLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzLmpzIiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvYWdlbnQtcm93LmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbXBvc2VyLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbnNvbGUuanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvY29udmVyc2F0aW9uLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2V4Y2hhbmdlLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2hvbWUuanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbG9nLW91dC1idXR0b24uanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbG9naW4tZm9ybS5qc3giLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9uYXZpZ2F0aW9uLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL3BsYXRmb3JtLW1hbmFnZXIuanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvZGlzcGF0Y2hlci9pbmRleC5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2Vycm9yLmpzIiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvZXhjaGFuZ2UuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvc3RvcmUuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9lcnJvci5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvcmVxdWVzdC5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvY29uc29sZS1zdG9yZS5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZS5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZS5qcyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQTtBQ0FBLFlBQVksQ0FBQzs7QUFFYixJQUFJLEtBQUssR0FBRyxPQUFPLENBQUMsT0FBTyxDQUFDLENBQUM7O0FBRTdCLElBQUksZUFBZSxHQUFHLE9BQU8sQ0FBQywrQkFBK0IsQ0FBQyxDQUFDOztBQUUvRCxLQUFLLENBQUMsTUFBTTtJQUNSLG9CQUFDLGVBQWUsRUFBQSxJQUFBLENBQUcsQ0FBQTtJQUNuQixRQUFRLENBQUMsY0FBYyxDQUFDLEtBQUssQ0FBQztDQUNqQyxDQUFDOzs7O0FDVEYsWUFBWSxDQUFDOztBQUViLElBQUksWUFBWSxHQUFHLE9BQU8sQ0FBQywyQkFBMkIsQ0FBQyxDQUFDO0FBQ3hELElBQUksVUFBVSxHQUFHLE9BQU8sQ0FBQyxlQUFlLENBQUMs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LE9BQU8sQ0FBQyxlQUFlLEVBQUUsY0FBYyxDQUFDLENBQUM7WUFDeEQsb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7QUFDOUMsWUFBWSxNQUFNOztRQUVWLEtBQUssWUFBWSxDQUFDLG9CQUFvQixDQUFDO1FBQ3ZDLEtBQUssWUFBWSxDQUFDLG1CQUFtQjtZQUNqQyxjQUFjLEdBQUcsSUFBSSxDQUFDO1lBQ3RCLGNBQWMsQ0FBQyxVQUFVLENBQUMsZUFBZSxDQUFDLENBQUM7WUFDM0Msb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7QUFDOUMsWUFBWSxNQUFNOztRQUVWLEtBQUssWUFBWSxDQUFDLFdBQVc7WUFDekIsS0FBSyxHQUFHLE1BQU0sQ0FBQyxJQUFJLENBQUM7WUFDcEIsUUFBUSxDQUFDLElBQUksR0FBRyxHQUFHLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQztZQUNsQyxvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztBQUM5QyxZQUFZLE1BQU07O1FBRVYsS0FBSyxZQUFZLENBQUMsaUJBQWlCO1lBQy9CLFVBQVUsR0FBRyxNQUFNLENBQUMsU0FBUyxDQUFDO1lBQzlCLG9CQUFvQixDQUFDLFVBQVUsRUFBRSxDQUFDO0FBQzlDLFlBQVksTUFBTTs7UUFFVixLQUFLLFlBQVksQ0FBQyxnQkFBZ0I7WUFDOUIsb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDbEMsTUFBTTtLQUNiO0FBQ0wsQ0FBQyxDQUFDLENBQUM7O0FBRUgsTUFBTSxDQUFDLE9BQU8sR0FBRyxvQkFBb0IsQ0FBQyIsImZpbGUiOiJnZW5lcmF0ZWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlc0NvbnRlbnQiOlsiKGZ1bmN0aW9uIGUodCxuLHIpe2Z1bmN0aW9uIHMobyx1KXtpZighbltvXSl7aWYoIXRbb10pe3ZhciBhPXR5cGVvZiByZXF1aXJlPT1cImZ1bmN0aW9uXCImJnJlcXVpcmU7aWYoIXUmJmEpcmV0dXJuIGEobywhMCk7aWYoaSlyZXR1cm4gaShvLCEwKTt2YXIgZj1uZXcgRXJyb3IoXCJDYW5ub3QgZmluZCBtb2R1bGUgJ1wiK28rXCInXCIpO3Rocm93IGYuY29kZT1cIk1PRFVMRV9OT1RfRk9VTkRcIixmfXZhciBsPW5bb109e2V4cG9ydHM6e319O3Rbb11bMF0uY2FsbChsLmV4cG9ydHMsZnVuY3Rpb24oZSl7dmFyIG49dFtvXVsxXVtlXTtyZXR1cm4gcyhuP246ZSl9LGwsbC5leHBvcnRzLGUsdCxuLHIpfXJldHVybiBuW29dLmV4cG9ydHN9dmFyIGk9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtmb3IodmFyIG89MDtvPHIubGVuZ3RoO28rKylzKHJbb10pO3JldHVybiBzfSkiLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBQbGF0Zm9ybU1hbmFnZXIgPSByZXF1aXJlKCcuL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlcicpO1xuXG5SZWFjdC5yZW5kZXIoXG4gICAgPFBsYXRmb3JtTWFuYWdlciAvPixcbiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnYXBwJylcbik7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBScGNFeGNoYW5nZSA9IHJlcXVpcmUoJy4uL2xpYi9ycGMvZXhjaGFuZ2UnKTtcblxudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHtcbiAgICB0b2dnbGVDb25zb2xlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlRPR0dMRV9DT05TT0xFLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIHVwZGF0ZUNvbXBvc2VyVmFsdWU6IGZ1bmN0aW9uICh2YWx1ZSkge1xuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5VUERBVEVfQ09NUE9TRVJfVkFMVUUsXG4gICAgICAgICAgICB2YWx1ZTogdmFsdWUsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgbWFrZVJlcXVlc3Q6IGZ1bmN0aW9uIChvcHRzKSB7XG4gICAgICAgIG5ldyBScGNFeGNoYW5nZShvcHRzKS5wcm9taXNlLmNhdGNoKGZ1bmN0aW9uIGlnbm9yZSgpIHt9KTtcbiAgICB9XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IGNvbnNvbGVBY3Rpb25DcmVhdG9ycztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBycGMgPSByZXF1aXJlKCcuLi9saWIvcnBjJyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHtcbiAgICByZXF1ZXN0QXV0aG9yaXphdGlvbjogZnVuY3Rpb24gKHVzZXJuYW1lLCBwYXNzd29yZCkge1xuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ2dldF9hdXRob3JpemF0aW9uJyxcbiAgICAgICAgICAgIHBhcmFtczoge1xuICAgICAgICAgICAgICAgIHVzZXJuYW1lOiB1c2VybmFtZSxcbiAgICAgICAgICAgICAgICBwYXNzd29yZDogcGFzc3dvcmQsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocmVzdWx0KSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT04sXG4gICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IHJlc3VsdCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAuY2F0Y2gocnBjLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBpZiAoZXJyb3IuY29kZSAmJiBlcnJvci5jb2RlID09PSA0MDEpIHtcbiAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQsXG4gICAgICAgICAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgY2xlYXJBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT04sXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgZ29Ub1BhZ2U6IGZ1bmN0aW9uIChwYWdlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFLFxuICAgICAgICAgICAgcGFnZTogcGFnZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBsb2FkUGxhdGZvcm1zOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuXG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAnbGlzdF9wbGF0Zm9ybXMnLFxuICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHBsYXRmb3Jtcykge1xuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STVMsXG4gICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1zLFxuICAgICAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICAgICAgcGxhdGZvcm1zLmZvckVhY2goZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAncGxhdGZvcm1zLnV1aWQuJyArIHBsYXRmb3JtLnV1aWQgKyAnLmxpc3RfYWdlbnRzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgICAgICAgICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgICAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChhZ2VudHNMaXN0KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm0uYWdlbnRzID0gYWdlbnRzTGlzdDtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKCFhZ2VudHNMaXN0Lmxlbmd0aCkgeyByZXR1cm47IH1cblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcuc3RhdHVzX2FnZW50cycsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAudGhlbihmdW5jdGlvbiAoYWdlbnRTdGF0dXNlcykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm0uYWdlbnRzLmZvckVhY2goZnVuY3Rpb24gKGFnZW50KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKCFhZ2VudFN0YXR1c2VzLnNvbWUoZnVuY3Rpb24gKHN0YXR1cykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAoYWdlbnQudXVpZCA9PT0gc3RhdHVzLnV1aWQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50LnByb2Nlc3NfaWQgPSBzdGF0dXMucHJvY2Vzc19pZDtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50LnJldHVybl9jb2RlID0gc3RhdHVzLnJldHVybl9jb2RlO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucHJvY2Vzc19pZCA9IG51bGw7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50LnJldHVybl9jb2RlID0gbnVsbDtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAuY2F0Y2goZnVuY3Rpb24gKGVycm9yKSB7XG4gICAgICAgICAgICAgICAgaWYgKGVycm9yLmNvZGUgJiYgZXJyb3IuY29kZSA9PT0gNDAxKSB7XG4gICAgICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVELFxuICAgICAgICAgICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLFxuICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICB0aHJvdyBlcnJvcjtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9KTtcbiAgICB9LFxuICAgIHN0YXJ0QWdlbnQ6IGZ1bmN0aW9uIChwbGF0Zm9ybSwgYWdlbnQpIHtcbiAgICAgICAgdmFyIGF1dGhvcml6YXRpb24gPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCk7XG5cbiAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IHRydWU7XG5cbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgfSk7XG5cbiAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcuc3RhcnRfYWdlbnQnLFxuICAgICAgICAgICAgcGFyYW1zOiBbYWdlbnQudXVpZF0sXG4gICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAoc3RhdHVzKSB7XG4gICAgICAgICAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IGZhbHNlO1xuICAgICAgICAgICAgICAgIGFnZW50LnByb2Nlc3NfaWQgPSBzdGF0dXMucHJvY2Vzc19pZDtcbiAgICAgICAgICAgICAgICBhZ2VudC5yZXR1cm5fY29kZSA9IHN0YXR1cy5yZXR1cm5fY29kZTtcblxuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgfSxcbiAgICBzdG9wQWdlbnQ6IGZ1bmN0aW9uIChwbGF0Zm9ybSwgYWdlbnQpIHtcbiAgICAgICAgdmFyIGF1dGhvcml6YXRpb24gPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCk7XG5cbiAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IHRydWU7XG5cbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgfSk7XG5cbiAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcuc3RvcF9hZ2VudCcsXG4gICAgICAgICAgICBwYXJhbXM6IFthZ2VudC51dWlkXSxcbiAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChzdGF0dXMpIHtcbiAgICAgICAgICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gZmFsc2U7XG4gICAgICAgICAgICAgICAgYWdlbnQucHJvY2Vzc19pZCA9IHN0YXR1cy5wcm9jZXNzX2lkO1xuICAgICAgICAgICAgICAgIGFnZW50LnJldHVybl9jb2RlID0gc3RhdHVzLnJldHVybl9jb2RlO1xuXG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KTtcbiAgICB9LFxufTtcblxud2luZG93Lm9uaGFzaGNoYW5nZSA9IGZ1bmN0aW9uICgpIHtcbiAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5nb1RvUGFnZShsb2NhdGlvbi5oYXNoLnN1YnN0cigxKSk7XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcblxudmFyIEFnZW50Um93ID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIF9vblN0b3A6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuc3RvcEFnZW50KHRoaXMucHJvcHMucGxhdGZvcm0sIHRoaXMucHJvcHMuYWdlbnQpO1xuICAgIH0sXG4gICAgX29uU3RhcnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuc3RhcnRBZ2VudCh0aGlzLnByb3BzLnBsYXRmb3JtLCB0aGlzLnByb3BzLmFnZW50KTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgYWdlbnQgPSB0aGlzLnByb3BzLmFnZW50LCBzdGF0dXMsIGFjdGlvbjtcblxuICAgICAgICBpZiAoYWdlbnQuYWN0aW9uUGVuZGluZyA9PT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICBzdGF0dXMgPSAnUmV0cmlldmluZyBzdGF0dXMuLi4nO1xuICAgICAgICB9IGVsc2UgaWYgKGFnZW50LmFjdGlvblBlbmRpbmcpIHtcbiAgICAgICAgICAgIGlmIChhZ2VudC5wcm9jZXNzX2lkID09PSBudWxsIHx8IGFnZW50LnJldHVybl9jb2RlICE9PSBudWxsKSB7XG4gICAgICAgICAgICAgICAgc3RhdHVzID0gJ1N0YXJ0aW5nLi4uJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdGFydFwiIGRpc2FibGVkIC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgc3RhdHVzID0gJ1N0b3BwaW5nLi4uJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdG9wXCIgZGlzYWJsZWQgLz5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfVxuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgaWYgKGFnZW50LnByb2Nlc3NfaWQgPT09IG51bGwpIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnTmV2ZXIgc3RhcnRlZCc7XG4gICAgICAgICAgICAgICAgYWN0aW9uID0gKFxuICAgICAgICAgICAgICAgICAgICA8aW5wdXQgY2xhc3NOYW1lPVwiYnV0dG9uXCIgdHlwZT1cImJ1dHRvblwiIHZhbHVlPVwiU3RhcnRcIiBvbkNsaWNrPXt0aGlzLl9vblN0YXJ0fSAvPlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9IGVsc2UgaWYgKGFnZW50LnJldHVybl9jb2RlID09PSBudWxsKSB7XG4gICAgICAgICAgICAgICAgc3RhdHVzID0gJ1J1bm5pbmcgKFBJRCAnICsgYWdlbnQucHJvY2Vzc19pZCArICcpJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdG9wXCIgb25DbGljaz17dGhpcy5fb25TdG9wfSAvPlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIHN0YXR1cyA9ICdTdG9wcGVkIChyZXR1cm5lZCAnICsgYWdlbnQucmV0dXJuX2NvZGUgKyAnKSc7XG4gICAgICAgICAgICAgICAgYWN0aW9uID0gKFxuICAgICAgICAgICAgICAgICAgICA8aW5wdXQgY2xhc3NOYW1lPVwiYnV0dG9uXCIgdHlwZT1cImJ1dHRvblwiIHZhbHVlPVwiU3RhcnRcIiBvbkNsaWNrPXt0aGlzLl9vblN0YXJ0fSAvPlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPHRyPlxuICAgICAgICAgICAgICAgIDx0ZD57YWdlbnQubmFtZX08L3RkPlxuICAgICAgICAgICAgICAgIDx0ZD57YWdlbnQudXVpZH08L3RkPlxuICAgICAgICAgICAgICAgIDx0ZD57c3RhdHVzfTwvdGQ+XG4gICAgICAgICAgICAgICAgPHRkPnthY3Rpb259PC90ZD5cbiAgICAgICAgICAgIDwvdHI+XG4gICAgICAgICk7XG4gICAgfSxcbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IEFnZW50Um93O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgY29uc29sZUFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgY29uc29sZVN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL2NvbnNvbGUtc3RvcmUnKTtcblxudmFyIENvbXBvc2VyID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMucmVwbGFjZVN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIF9vblNlbmRDbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlQWN0aW9uQ3JlYXRvcnMubWFrZVJlcXVlc3QoSlNPTi5wYXJzZSh0aGlzLnN0YXRlLmNvbXBvc2VyVmFsdWUpKTtcbiAgICB9LFxuICAgIF9vblRleHRhcmVhQ2hhbmdlOiBmdW5jdGlvbiAoZSkge1xuICAgICAgICBjb25zb2xlQWN0aW9uQ3JlYXRvcnMudXBkYXRlQ29tcG9zZXJWYWx1ZShlLnRhcmdldC52YWx1ZSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiY29tcG9zZXJcIj5cbiAgICAgICAgICAgICAgICA8dGV4dGFyZWFcbiAgICAgICAgICAgICAgICAgICAga2V5PXt0aGlzLnN0YXRlLmNvbXBvc2VySWR9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2hhbmdlPXt0aGlzLl9vblRleHRhcmVhQ2hhbmdlfVxuICAgICAgICAgICAgICAgICAgICBkZWZhdWx0VmFsdWU9e3RoaXMuc3RhdGUuY29tcG9zZXJWYWx1ZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICByZWY9XCJzZW5kXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHZhbHVlPVwiU2VuZFwiXG4gICAgICAgICAgICAgICAgICAgIGRpc2FibGVkPXshdGhpcy5zdGF0ZS52YWxpZH1cbiAgICAgICAgICAgICAgICAgICAgb25DbGljaz17dGhpcy5fb25TZW5kQ2xpY2t9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH0sXG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHZhciBjb21wb3NlclZhbHVlID0gY29uc29sZVN0b3JlLmdldENvbXBvc2VyVmFsdWUoKTtcbiAgICB2YXIgdmFsaWQgPSB0cnVlO1xuXG4gICAgdHJ5IHtcbiAgICAgICAgSlNPTi5wYXJzZShjb21wb3NlclZhbHVlKTtcbiAgICB9IGNhdGNoIChleCkge1xuICAgICAgICBpZiAoZXggaW5zdGFuY2VvZiBTeW50YXhFcnJvcikge1xuICAgICAgICAgICAgdmFsaWQgPSBmYWxzZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIHRocm93IGV4O1xuICAgICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgICAgY29tcG9zZXJJZDogY29uc29sZVN0b3JlLmdldENvbXBvc2VySWQoKSxcbiAgICAgICAgY29tcG9zZXJWYWx1ZTogY29tcG9zZXJWYWx1ZSxcbiAgICAgICAgdmFsaWQ6IHZhbGlkLFxuICAgIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gQ29tcG9zZXI7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBDb21wb3NlciA9IHJlcXVpcmUoJy4vY29tcG9zZXInKTtcbnZhciBDb252ZXJzYXRpb24gPSByZXF1aXJlKCcuL2NvbnZlcnNhdGlvbicpO1xuXG52YXIgQ29uc29sZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiY29uc29sZVwiPlxuICAgICAgICAgICAgICAgIDxDb252ZXJzYXRpb24gLz5cbiAgICAgICAgICAgICAgICA8Q29tcG9zZXIgLz5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IENvbnNvbGU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciAkID0gcmVxdWlyZSgnanF1ZXJ5Jyk7XG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgRXhjaGFuZ2UgPSByZXF1aXJlKCcuL2V4Y2hhbmdlJyk7XG52YXIgY29uc29sZVN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL2NvbnNvbGUtc3RvcmUnKTtcblxudmFyIENvbnZlcnNhdGlvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgJGNvbnZlcnNhdGlvbiA9ICQodGhpcy5yZWZzLmNvbnZlcnNhdGlvbi5nZXRET01Ob2RlKCkpO1xuXG4gICAgICAgIGlmICgkY29udmVyc2F0aW9uLnByb3AoJ3Njcm9sbEhlaWdodCcpID4gJGNvbnZlcnNhdGlvbi5oZWlnaHQoKSkge1xuICAgICAgICAgICAgJGNvbnZlcnNhdGlvbi5zY3JvbGxUb3AoJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zb2xlU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50RGlkVXBkYXRlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciAkY29udmVyc2F0aW9uID0gJCh0aGlzLnJlZnMuY29udmVyc2F0aW9uLmdldERPTU5vZGUoKSk7XG5cbiAgICAgICAgJGNvbnZlcnNhdGlvbi5zdG9wKCkuYW5pbWF0ZSh7IHNjcm9sbFRvcDogJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSB9LCA1MDApO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiByZWY9XCJjb252ZXJzYXRpb25cIiBjbGFzc05hbWU9XCJjb252ZXJzYXRpb25cIj5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5leGNoYW5nZXMubWFwKGZ1bmN0aW9uIChleGNoYW5nZSwgaW5kZXgpIHtcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgICAgIDxFeGNoYW5nZSBrZXk9e2luZGV4fSBleGNoYW5nZT17ZXhjaGFuZ2V9IC8+XG4gICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7IGV4Y2hhbmdlczogY29uc29sZVN0b3JlLmdldEV4Y2hhbmdlcygpIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gQ29udmVyc2F0aW9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgRXhjaGFuZ2UgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgX2Zvcm1hdFRpbWU6IGZ1bmN0aW9uICh0aW1lKSB7XG4gICAgICAgIHZhciBkID0gbmV3IERhdGUoKTtcblxuICAgICAgICBkLnNldFRpbWUodGltZSk7XG5cbiAgICAgICAgcmV0dXJuIGQudG9Mb2NhbGVTdHJpbmcoKTtcbiAgICB9LFxuICAgIF9mb3JtYXRNZXNzYWdlOiBmdW5jdGlvbiAobWVzc2FnZSkge1xuICAgICAgICByZXR1cm4gSlNPTi5zdHJpbmdpZnkobWVzc2FnZSwgbnVsbCwgJyAgICAnKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgZXhjaGFuZ2UgPSB0aGlzLnByb3BzLmV4Y2hhbmdlO1xuICAgICAgICB2YXIgY2xhc3NlcyA9IFsncmVzcG9uc2UnXTtcbiAgICAgICAgdmFyIHJlc3BvbnNlVGV4dDtcblxuICAgICAgICBpZiAoIWV4Y2hhbmdlLmNvbXBsZXRlZCkge1xuICAgICAgICAgICAgY2xhc3Nlcy5wdXNoKCdyZXNwb25zZS0tcGVuZGluZycpO1xuICAgICAgICAgICAgcmVzcG9uc2VUZXh0ID0gJ1dhaXRpbmcgZm9yIHJlc3BvbnNlLi4uJztcbiAgICAgICAgfSBlbHNlIGlmIChleGNoYW5nZS5lcnJvcikge1xuICAgICAgICAgICAgY2xhc3Nlcy5wdXNoKCdyZXNwb25zZS0tZXJyb3InKTtcbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9IGV4Y2hhbmdlLmVycm9yLm1lc3NhZ2U7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBpZiAoZXhjaGFuZ2UucmVzcG9uc2UuZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1lcnJvcicpO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICByZXNwb25zZVRleHQgPSB0aGlzLl9mb3JtYXRNZXNzYWdlKGV4Y2hhbmdlLnJlc3BvbnNlKTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImV4Y2hhbmdlXCI+XG4gICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJyZXF1ZXN0XCI+XG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwidGltZVwiPnt0aGlzLl9mb3JtYXRUaW1lKGV4Y2hhbmdlLmluaXRpYXRlZCl9PC9kaXY+XG4gICAgICAgICAgICAgICAgICAgIDxwcmU+e3RoaXMuX2Zvcm1hdE1lc3NhZ2UoZXhjaGFuZ2UucmVxdWVzdCl9PC9wcmU+XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9e2NsYXNzZXMuam9pbignICcpfT5cbiAgICAgICAgICAgICAgICAgICAge2V4Y2hhbmdlLmNvbXBsZXRlZCAmJiA8ZGl2IGNsYXNzTmFtZT1cInRpbWVcIj57dGhpcy5fZm9ybWF0VGltZShleGNoYW5nZS5jb21wbGV0ZWQpfTwvZGl2Pn1cbiAgICAgICAgICAgICAgICAgICAgPHByZT57cmVzcG9uc2VUZXh0fTwvcHJlPlxuICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gRXhjaGFuZ2U7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBBZ2VudFJvdyA9IHJlcXVpcmUoJy4vYWdlbnQtcm93Jyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG5cbnZhciBIb21lID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgc2V0VGltZW91dChwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5sb2FkUGxhdGZvcm1zKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgcGxhdGZvcm1zO1xuXG4gICAgICAgIGlmICghdGhpcy5zdGF0ZS5wbGF0Zm9ybXMpIHtcbiAgICAgICAgICAgIHBsYXRmb3JtcyA9IChcbiAgICAgICAgICAgICAgICA8cD5Mb2FkaW5nIHBsYXRmb3Jtcy4uLjwvcD5cbiAgICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSBpZiAoIXRoaXMuc3RhdGUucGxhdGZvcm1zLmxlbmd0aCkge1xuICAgICAgICAgICAgcGxhdGZvcm1zID0gKFxuICAgICAgICAgICAgICAgIDxwPk5vIHBsYXRmb3JtcyBmb3VuZC48L3A+XG4gICAgICAgICAgICApO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgcGxhdGZvcm1zID0gdGhpcy5zdGF0ZS5wbGF0Zm9ybXMubWFwKGZ1bmN0aW9uIChwbGF0Zm9ybSkge1xuICAgICAgICAgICAgICAgIHZhciBhZ2VudHM7XG5cbiAgICAgICAgICAgICAgICBpZiAoIXBsYXRmb3JtLmFnZW50cykge1xuICAgICAgICAgICAgICAgICAgICBhZ2VudHMgPSAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8cD5Mb2FkaW5nIGFnZW50cy4uLjwvcD5cbiAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKCFwbGF0Zm9ybS5hZ2VudHMubGVuZ3RoKSB7XG4gICAgICAgICAgICAgICAgICAgIGFnZW50cyA9IChcbiAgICAgICAgICAgICAgICAgICAgICAgIDxwPk5vIGFnZW50cyBpbnN0YWxsZWQuPC9wPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIGFnZW50cyA9IChcbiAgICAgICAgICAgICAgICAgICAgICAgIDx0YWJsZT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGhlYWQ+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0cj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5BZ2VudDwvdGg+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGg+VVVJRDwvdGg+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGg+U3RhdHVzPC90aD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5BY3Rpb248L3RoPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RyPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvdGhlYWQ+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRib2R5PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cGxhdGZvcm0uYWdlbnRzLm1hcChmdW5jdGlvbiAoYWdlbnQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPEFnZW50Um93XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGtleT17YWdlbnQudXVpZH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm09e3BsYXRmb3JtfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudD17YWdlbnR9IC8+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3Rib2R5PlxuICAgICAgICAgICAgICAgICAgICAgICAgPC90YWJsZT5cbiAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInBsYXRmb3JtXCIga2V5PXtwbGF0Zm9ybS51dWlkfT5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxoMj57cGxhdGZvcm0ubmFtZX0gKHtwbGF0Zm9ybS51dWlkfSk8L2gyPlxuICAgICAgICAgICAgICAgICAgICAgICAge2FnZW50c31cbiAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0pO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiaG9tZVwiPlxuICAgICAgICAgICAgICAgIHtwbGF0Zm9ybXN9XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4ge1xuICAgICAgICBwbGF0Zm9ybXM6IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBsYXRmb3JtcygpLFxuICAgIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gSG9tZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG5cbnZhciBMb2dPdXRCdXR0b24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgX29uQ2xpY2s6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuY2xlYXJBdXRob3JpemF0aW9uKCk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxidXR0b24gY2xhc3NOYW1lPVwiYnV0dG9uXCIgb25DbGljaz17dGhpcy5fb25DbGlja30+TG9nIG91dDwvYnV0dG9uPlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IExvZ091dEJ1dHRvbjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgbG9naW5Gb3JtU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZScpO1xuXG52YXIgTG9naW5Gb3JtID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGxvZ2luRm9ybVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uU3RvcmVzQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGxvZ2luRm9ybVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uU3RvcmVzQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vblN0b3Jlc0NoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIF9vbklucHV0Q2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoe1xuICAgICAgICAgICAgdXNlcm5hbWU6IHRoaXMucmVmcy51c2VybmFtZS5nZXRET01Ob2RlKCkudmFsdWUsXG4gICAgICAgICAgICBwYXNzd29yZDogdGhpcy5yZWZzLnBhc3N3b3JkLmdldERPTU5vZGUoKS52YWx1ZSxcbiAgICAgICAgICAgIGVycm9yOiBudWxsLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIF9vblN1Ym1pdDogZnVuY3Rpb24gKGUpIHtcbiAgICAgICAgZS5wcmV2ZW50RGVmYXVsdCgpO1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5yZXF1ZXN0QXV0aG9yaXphdGlvbihcbiAgICAgICAgICAgIHRoaXMuc3RhdGUudXNlcm5hbWUsXG4gICAgICAgICAgICB0aGlzLnN0YXRlLnBhc3N3b3JkXG4gICAgICAgICk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxmb3JtIGNsYXNzTmFtZT1cImxvZ2luLWZvcm1cIiBvblN1Ym1pdD17dGhpcy5fb25TdWJtaXR9PlxuICAgICAgICAgICAgICAgIDxoMT5WT0xUVFJPTihUTSkgUGxhdGZvcm0gTWFuYWdlcjwvaDE+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIHJlZj1cInVzZXJuYW1lXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cInRleHRcIlxuICAgICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlcj1cIlVzZXJuYW1lXCJcbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3RoaXMuX29uSW5wdXRDaGFuZ2V9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwicGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwicGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlcj1cIlBhc3N3b3JkXCJcbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3RoaXMuX29uSW5wdXRDaGFuZ2V9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cInN1Ym1pdFwiXG4gICAgICAgICAgICAgICAgICAgIHZhbHVlPVwiTG9nIGluXCJcbiAgICAgICAgICAgICAgICAgICAgZGlzYWJsZWQ9eyF0aGlzLnN0YXRlLnVzZXJuYW1lIHx8ICF0aGlzLnN0YXRlLnBhc3N3b3JkfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXJyb3IgPyAoXG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXJyb3JcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmVycm9yLm1lc3NhZ2V9ICh7dGhpcy5zdGF0ZS5lcnJvci5jb2RlfSlcbiAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgKSA6IG51bGwgfVxuICAgICAgICAgICAgPC9mb3JtPlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHsgZXJyb3I6IGxvZ2luRm9ybVN0b3JlLmdldExhc3RFcnJvcigpIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gTG9naW5Gb3JtO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgTG9nT3V0QnV0dG9uID0gcmVxdWlyZSgnLi9sb2ctb3V0LWJ1dHRvbicpO1xuXG52YXIgTmF2aWdhdGlvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwibmF2aWdhdGlvblwiPlxuICAgICAgICAgICAgICAgIDxoMT48YSBocmVmPVwiI2hvbWVcIj5WT0xUVFJPTihUTSkgUGxhdGZvcm0gTWFuYWdlcjwvYT48L2gxPlxuICAgICAgICAgICAgICAgIDxMb2dPdXRCdXR0b24gLz5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IE5hdmlnYXRpb247XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBDb25zb2xlID0gcmVxdWlyZSgnLi9jb25zb2xlJyk7XG52YXIgY29uc29sZUFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgY29uc29sZVN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL2NvbnNvbGUtc3RvcmUnKTtcbnZhciBIb21lID0gcmVxdWlyZSgnLi9ob21lJyk7XG52YXIgTG9naW5Gb3JtID0gcmVxdWlyZSgnLi9sb2dpbi1mb3JtJyk7XG52YXIgTmF2aWdhdGlvbiA9IHJlcXVpcmUoJy4vbmF2aWdhdGlvbicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcblxudmFyIFBsYXRmb3JtTWFuYWdlciA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICBfb25CdXR0b25DbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlQWN0aW9uQ3JlYXRvcnMudG9nZ2xlQ29uc29sZSgpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBjbGFzc2VzID0gWydwbGF0Zm9ybS1tYW5hZ2VyJ107XG5cbiAgICAgICAgaWYgKCF0aGlzLnN0YXRlLmNvbnNvbGVTaG93bikge1xuICAgICAgICAgICAgY2xhc3Nlcy5wdXNoKCdwbGF0Zm9ybS1tYW5hZ2VyLS1jb25zb2xlLWhpZGRlbicpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPXtjbGFzc2VzLmpvaW4oJyAnKX0+XG4gICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJtYWluXCI+XG4gICAgICAgICAgICAgICAgICAgIHshdGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8TG9naW5Gb3JtIC8+fVxuICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8TmF2aWdhdGlvbiAvPn1cbiAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUubG9nZ2VkSW4gJiYgPEhvbWUgLz59XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cInRvZ2dsZSBidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9eydDb25zb2xlICcgKyAodGhpcy5zdGF0ZS5jb25zb2xlU2hvd24gPyAnXFx1MjViYycgOiAnXFx1MjViMicpfVxuICAgICAgICAgICAgICAgICAgICBvbkNsaWNrPXt0aGlzLl9vbkJ1dHRvbkNsaWNrfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuY29uc29sZVNob3duICYmIDxDb25zb2xlIGNsYXNzTmFtZT1cImNvbnNvbGVcIiAvPn1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgICAgY29uc29sZVNob3duOiBjb25zb2xlU3RvcmUuZ2V0Q29uc29sZVNob3duKCksXG4gICAgICAgIGxvZ2dlZEluOiAhIXBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKSxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFBsYXRmb3JtTWFuYWdlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIGtleU1pcnJvciA9IHJlcXVpcmUoJ3JlYWN0L2xpYi9rZXlNaXJyb3InKTtcblxubW9kdWxlLmV4cG9ydHMgPSBrZXlNaXJyb3Ioe1xuICAgIFRPR0dMRV9DT05TT0xFOiBudWxsLFxuXG4gICAgVVBEQVRFX0NPTVBPU0VSX1ZBTFVFOiBudWxsLFxuXG4gICAgTUFLRV9SRVFVRVNUOiBudWxsLFxuICAgIEZBSUxfUkVRVUVTVDogbnVsbCxcbiAgICBSRUNFSVZFX1JFU1BPTlNFOiBudWxsLFxuXG4gICAgUkVDRUlWRV9BVVRIT1JJWkFUSU9OOiBudWxsLFxuICAgIFJFQ0VJVkVfVU5BVVRIT1JJWkVEOiBudWxsLFxuICAgIENMRUFSX0FVVEhPUklaQVRJT046IG51bGwsXG5cbiAgICBDSEFOR0VfUEFHRTogbnVsbCxcblxuICAgIFJFQ0VJVkVfUExBVEZPUk1TOiBudWxsLFxuICAgIFJFQ0VJVkVfUExBVEZPUk06IG51bGwsXG59KTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIERpc3BhdGNoZXIgPSByZXF1aXJlKCdmbHV4JykuRGlzcGF0Y2hlcjtcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcblxudmFyIGRpc3BhdGNoZXIgPSBuZXcgRGlzcGF0Y2hlcigpO1xuXG5kaXNwYXRjaGVyLmRpc3BhdGNoID0gZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGlmIChhY3Rpb24udHlwZSBpbiBBQ1RJT05fVFlQRVMpIHtcbiAgICAgICAgcmV0dXJuIE9iamVjdC5nZXRQcm90b3R5cGVPZih0aGlzKS5kaXNwYXRjaC5jYWxsKHRoaXMsIGFjdGlvbik7XG4gICAgfVxuXG4gICAgdGhyb3cgJ0Rpc3BhdGNoIGVycm9yOiBpbnZhbGlkIGFjdGlvbiB0eXBlICcgKyBhY3Rpb24udHlwZTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gZGlzcGF0Y2hlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxuZnVuY3Rpb24gUnBjRXJyb3IoZXJyb3IpIHtcbiAgICB0aGlzLm5hbWUgPSAnUnBjRXJyb3InO1xuICAgIHRoaXMuY29kZSA9IGVycm9yLmNvZGU7XG4gICAgdGhpcy5tZXNzYWdlID0gZXJyb3IubWVzc2FnZTtcbiAgICB0aGlzLmRhdGEgPSBlcnJvci5kYXRhO1xufVxuUnBjRXJyb3IucHJvdG90eXBlID0gT2JqZWN0LmNyZWF0ZShFcnJvci5wcm90b3R5cGUpO1xuUnBjRXJyb3IucHJvdG90eXBlLmNvbnN0cnVjdG9yID0gUnBjRXJyb3I7XG5cbm1vZHVsZS5leHBvcnRzID0gUnBjRXJyb3I7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciB1dWlkID0gcmVxdWlyZSgnbm9kZS11dWlkJyk7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi8uLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uLy4uL2Rpc3BhdGNoZXInKTtcbnZhciBScGNFcnJvciA9IHJlcXVpcmUoJy4vZXJyb3InKTtcbnZhciB4aHIgPSByZXF1aXJlKCcuLi94aHInKTtcblxuZnVuY3Rpb24gUnBjRXhjaGFuZ2Uob3B0cykge1xuICAgIGlmICghdGhpcyBpbnN0YW5jZW9mIFJwY0V4Y2hhbmdlKSB7XG4gICAgICAgIHJldHVybiBuZXcgUnBjRXhjaGFuZ2Uob3B0cyk7XG4gICAgfVxuXG4gICAgdmFyIGV4Y2hhbmdlID0gdGhpcztcblxuICAgIC8vIFRPRE86IHZhbGlkYXRlIG9wdHNcbiAgICBvcHRzLmpzb25ycGMgPSAnMi4wJztcbiAgICBvcHRzLmlkID0gdXVpZC52MSgpO1xuXG4gICAgZXhjaGFuZ2UuaW5pdGlhdGVkID0gRGF0ZS5ub3coKTtcbiAgICBleGNoYW5nZS5yZXF1ZXN0ID0gb3B0cztcblxuICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuTUFLRV9SRVFVRVNULFxuICAgICAgICBleGNoYW5nZTogZXhjaGFuZ2UsXG4gICAgICAgIHJlcXVlc3Q6IGV4Y2hhbmdlLnJlcXVlc3QsXG4gICAgfSk7XG5cbiAgICBleGNoYW5nZS5wcm9taXNlID0gbmV3IHhoci5SZXF1ZXN0KHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIHVybDogJy9qc29ucnBjJyxcbiAgICAgICAgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgZGF0YTogSlNPTi5zdHJpbmdpZnkoZXhjaGFuZ2UucmVxdWVzdCksXG4gICAgICAgIHRpbWVvdXQ6IDYwMDAwLFxuICAgIH0pXG4gICAgICAgIC5maW5hbGx5KGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgIGV4Y2hhbmdlLmNvbXBsZXRlZCA9IERhdGUubm93KCk7XG4gICAgICAgIH0pXG4gICAgICAgIC50aGVuKGZ1bmN0aW9uIChyZXNwb25zZSkge1xuICAgICAgICAgICAgZXhjaGFuZ2UucmVzcG9uc2UgPSByZXNwb25zZTtcblxuICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUkVTUE9OU0UsXG4gICAgICAgICAgICAgICAgZXhjaGFuZ2U6IGV4Y2hhbmdlLFxuICAgICAgICAgICAgICAgIHJlc3BvbnNlOiByZXNwb25zZSxcbiAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICBpZiAocmVzcG9uc2UuZXJyb3IpIHtcbiAgICAgICAgICAgICAgICB0aHJvdyBuZXcgUnBjRXJyb3IocmVzcG9uc2UuZXJyb3IpO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICByZXR1cm4gcmVzcG9uc2UucmVzdWx0O1xuICAgICAgICB9KVxuICAgICAgICAuY2F0Y2goeGhyLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgIGV4Y2hhbmdlLmVycm9yID0gZXJyb3I7XG5cbiAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5GQUlMX1JFUVVFU1QsXG4gICAgICAgICAgICAgICAgZXhjaGFuZ2U6IGV4Y2hhbmdlLFxuICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICB0aHJvdyBlcnJvcjtcbiAgICAgICAgfSk7XG59XG5cbm1vZHVsZS5leHBvcnRzID0gUnBjRXhjaGFuZ2U7XG4iLCIndXNlIHN0cmljdCc7XG5cbm1vZHVsZS5leHBvcnRzID0ge1xuICAgIEVycm9yOiByZXF1aXJlKCcuL2Vycm9yJyksXG4gICAgRXhjaGFuZ2U6IHJlcXVpcmUoJy4vZXhjaGFuZ2UnKSxcbn07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBFdmVudEVtaXR0ZXIgPSByZXF1aXJlKCdldmVudHMnKS5FdmVudEVtaXR0ZXI7XG5cbnZhciBDSEFOR0VfRVZFTlQgPSAnY2hhbmdlJztcblxuZnVuY3Rpb24gU3RvcmUoKSB7XG4gICAgRXZlbnRFbWl0dGVyLmNhbGwodGhpcyk7XG59XG5TdG9yZS5wcm90b3R5cGUgPSBFdmVudEVtaXR0ZXIucHJvdG90eXBlO1xuXG5TdG9yZS5wcm90b3R5cGUuZW1pdENoYW5nZSA9IGZ1bmN0aW9uKCkge1xuICAgIHRoaXMuZW1pdChDSEFOR0VfRVZFTlQpO1xufTtcblxuU3RvcmUucHJvdG90eXBlLmFkZENoYW5nZUxpc3RlbmVyID0gZnVuY3Rpb24gKGNhbGxiYWNrKSB7XG4gICAgdGhpcy5vbihDSEFOR0VfRVZFTlQsIGNhbGxiYWNrKTtcbn07XG5cblN0b3JlLnByb3RvdHlwZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lciA9IGZ1bmN0aW9uIChjYWxsYmFjaykge1xuICAgIHRoaXMucmVtb3ZlTGlzdGVuZXIoQ0hBTkdFX0VWRU5ULCBjYWxsYmFjayk7XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IFN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5mdW5jdGlvbiBYaHJFcnJvcihtZXNzYWdlLCByZXNwb25zZSkge1xuICAgIHRoaXMubmFtZSA9ICdYaHJFcnJvcic7XG4gICAgdGhpcy5tZXNzYWdlID0gbWVzc2FnZTtcbiAgICB0aGlzLnJlc3BvbnNlID0gcmVzcG9uc2U7XG59XG5YaHJFcnJvci5wcm90b3R5cGUgPSBPYmplY3QuY3JlYXRlKEVycm9yLnByb3RvdHlwZSk7XG5YaHJFcnJvci5wcm90b3R5cGUuY29uc3RydWN0b3IgPSBYaHJFcnJvcjtcblxubW9kdWxlLmV4cG9ydHMgPSBYaHJFcnJvcjtcbiIsIid1c2Ugc3RyaWN0JztcblxubW9kdWxlLmV4cG9ydHMgPSB7XG4gICAgUmVxdWVzdDogcmVxdWlyZSgnLi9yZXF1ZXN0JyksXG4gICAgRXJyb3I6IHJlcXVpcmUoJy4vZXJyb3InKSxcbn07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBqUXVlcnkgPSByZXF1aXJlKCdqcXVlcnknKTtcbnZhciBQcm9taXNlID0gcmVxdWlyZSgnYmx1ZWJpcmQnKTtcblxudmFyIFhockVycm9yID0gcmVxdWlyZSgnLi9lcnJvcicpO1xuXG5mdW5jdGlvbiBYaHJSZXF1ZXN0KG9wdHMpIHtcbiAgICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24gKHJlc29sdmUsIHJlamVjdCkge1xuICAgICAgICBvcHRzLnN1Y2Nlc3MgPSByZXNvbHZlO1xuICAgICAgICBvcHRzLmVycm9yID0gZnVuY3Rpb24gKHJlc3BvbnNlLCB0eXBlKSB7XG4gICAgICAgICAgICBzd2l0Y2ggKHR5cGUpIHtcbiAgICAgICAgICAgIGNhc2UgJ2Vycm9yJzpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdTZXJ2ZXIgcmV0dXJuZWQgJyArIHJlc3BvbnNlLnN0YXR1cyArICcgc3RhdHVzJywgcmVzcG9uc2UpKTtcbiAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIGNhc2UgJ3RpbWVvdXQnOlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1JlcXVlc3QgdGltZWQgb3V0JywgcmVzcG9uc2UpKTtcbiAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignUmVxdWVzdCBmYWlsZWQ6ICcgKyB0eXBlLCByZXNwb25zZSkpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9O1xuXG4gICAgICAgIGpRdWVyeS5hamF4KG9wdHMpO1xuICAgIH0pO1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFhoclJlcXVlc3Q7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4vcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIFN0b3JlID0gcmVxdWlyZSgnLi4vbGliL3N0b3JlJyk7XG5cbnZhciBfY29tcG9zZXJJZCA9IERhdGUubm93KCk7XG52YXIgX2NvbXBvc2VyVmFsdWUgPSAnJztcbnZhciBfY29uc29sZVNob3duID0gZmFsc2U7XG52YXIgX2V4Y2hhbmdlcyA9IFtdO1xuXG52YXIgY29uc29sZVN0b3JlID0gbmV3IFN0b3JlKCk7XG5cbmNvbnNvbGVTdG9yZS5nZXRDb21wb3NlcklkID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfY29tcG9zZXJJZDtcbn07XG5cbmNvbnNvbGVTdG9yZS5nZXRDb21wb3NlclZhbHVlID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfY29tcG9zZXJWYWx1ZTtcbn07XG5cbmNvbnNvbGVTdG9yZS5nZXRDb25zb2xlU2hvd24gPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9jb25zb2xlU2hvd247XG59O1xuXG5jb25zb2xlU3RvcmUuZ2V0RXhjaGFuZ2VzID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfZXhjaGFuZ2VzO1xufTtcblxuZnVuY3Rpb24gX3Jlc2V0Q29tcG9zZXJWYWx1ZSh1cGRhdGVNZXRob2QpIHtcbiAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcbiAgICB2YXIgcGFyc2VkO1xuXG4gICAgdHJ5IHtcbiAgICAgICAgcGFyc2VkID0gSlNPTi5wYXJzZShfY29tcG9zZXJWYWx1ZSk7XG5cbiAgICAgICAgaWYgKHVwZGF0ZU1ldGhvZCkge1xuICAgICAgICAgICAgcGFyc2VkLm1ldGhvZCA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UoKTtcbiAgICAgICAgfVxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgcGFyc2VkID0geyBtZXRob2Q6IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UoKSB9O1xuICAgIH1cblxuICAgIGlmIChhdXRob3JpemF0aW9uKSB7XG4gICAgICAgIHBhcnNlZC5hdXRob3JpemF0aW9uID0gYXV0aG9yaXphdGlvbjtcbiAgICB9IGVsc2Uge1xuICAgICAgICBkZWxldGUgcGFyc2VkLmF1dGhvcml6YXRpb247XG4gICAgfVxuXG4gICAgX2NvbXBvc2VyVmFsdWUgPSBKU09OLnN0cmluZ2lmeShwYXJzZWQsIG51bGwsICcgICAgJyk7XG59XG5cbl9yZXNldENvbXBvc2VyVmFsdWUoKTtcblxuY29uc29sZVN0b3JlLmRpc3BhdGNoVG9rZW4gPSBkaXNwYXRjaGVyLnJlZ2lzdGVyKGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBkaXNwYXRjaGVyLndhaXRGb3IoW3BsYXRmb3JtTWFuYWdlclN0b3JlLmRpc3BhdGNoVG9rZW5dKTtcblxuICAgIHN3aXRjaCAoYWN0aW9uLnR5cGUpIHtcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuVE9HR0xFX0NPTlNPTEU6XG4gICAgICAgICAgICBfY29uc29sZVNob3duID0gIV9jb25zb2xlU2hvd247XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuVVBEQVRFX0NPTVBPU0VSX1ZBTFVFOlxuICAgICAgICAgICAgX2NvbXBvc2VyVmFsdWUgPSBhY3Rpb24udmFsdWU7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9BVVRIT1JJWkFUSU9OOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRDpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgIF9yZXNldENvbXBvc2VyVmFsdWUoKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRTpcbiAgICAgICAgICAgIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgIF9yZXNldENvbXBvc2VyVmFsdWUodHJ1ZSk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuTUFLRV9SRVFVRVNUOlxuICAgICAgICAgICAgX2V4Y2hhbmdlcy5wdXNoKGFjdGlvbi5leGNoYW5nZSk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuRkFJTF9SRVFVRVNUOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1JFU1BPTlNFOlxuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGNvbnNvbGVTdG9yZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9sYXN0RXJyb3IgPSBudWxsO1xuXG52YXIgbG9naW5Gb3JtU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxubG9naW5Gb3JtU3RvcmUuZ2V0TGFzdEVycm9yID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfbGFzdEVycm9yO1xufTtcblxubG9naW5Gb3JtU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGRpc3BhdGNoZXIud2FpdEZvcihbcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbl0pO1xuXG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfbGFzdEVycm9yID0gbnVsbDtcbiAgICAgICAgICAgIGxvZ2luRm9ybVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICAgICAgX2xhc3RFcnJvciA9IGFjdGlvbi5lcnJvcjtcbiAgICAgICAgICAgIGxvZ2luRm9ybVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGxvZ2luRm9ybVN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9hdXRob3JpemF0aW9uID0gc2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbSgnYXV0aG9yaXphdGlvbicpO1xudmFyIF9wYWdlID0gbG9jYXRpb24uaGFzaC5zdWJzdHIoMSk7XG52YXIgX3BsYXRmb3JtcyA9IG51bGw7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfYXV0aG9yaXphdGlvbjtcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9wYWdlO1xufTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGxhdGZvcm1zID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfcGxhdGZvcm1zO1xufTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIHN3aXRjaCAoYWN0aW9uLnR5cGUpIHtcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2F1dGhvcml6YXRpb24gPSBhY3Rpb24uYXV0aG9yaXphdGlvbjtcbiAgICAgICAgICAgIHNlc3Npb25TdG9yYWdlLnNldEl0ZW0oJ2F1dGhvcml6YXRpb24nLCBfYXV0aG9yaXphdGlvbik7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRDpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9hdXRob3JpemF0aW9uID0gbnVsbDtcbiAgICAgICAgICAgIHNlc3Npb25TdG9yYWdlLnJlbW92ZUl0ZW0oJ2F1dGhvcml6YXRpb24nKTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFOlxuICAgICAgICAgICAgX3BhZ2UgPSBhY3Rpb24ucGFnZTtcbiAgICAgICAgICAgIGxvY2F0aW9uLmhhc2ggPSAnIycgKyBhY3Rpb24ucGFnZTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk1TOlxuICAgICAgICAgICAgX3BsYXRmb3JtcyA9IGFjdGlvbi5wbGF0Zm9ybXM7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNOlxuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmU7XG4iXX0=
