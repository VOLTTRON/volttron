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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hcHAuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9hZ2VudC1yb3cuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb21wb3Nlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbnNvbGUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb252ZXJzYXRpb24uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9leGNoYW5nZS5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2hvbWUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9sb2ctb3V0LWJ1dHRvbi5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2xvZ2luLWZvcm0uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9uYXZpZ2F0aW9uLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb25zdGFudHMvYWN0aW9uLXR5cGVzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvZGlzcGF0Y2hlci9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2V4Y2hhbmdlLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9yZXF1ZXN0LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvc3RvcmVzL2NvbnNvbGUtc3RvcmUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlLmpzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBO0FDQUEsWUFBWSxDQUFDOztBQUViLElBQUksS0FBSyxHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUMsQ0FBQzs7QUFFN0IsSUFBSSxlQUFlLEdBQUcsT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUM7O0FBRS9ELEtBQUss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LFVBQVUsQ0FBQyxRQUFRLENBQUMsVUFBVSxNQUFNLEVBQUU7SUFDdkUsUUFBUSxNQUFNLENBQUMsSUFBSTtRQUNmLEtBQUssWUFBWSxDQUFDLHFCQUFxQjtZQUNuQyxjQUFjLEdBQUcsTUFBTSxDQUFDLGFBQWEsQ0FBQztZQUN0QyxjQUFjLENBQUMsT0FBTyxDQUFDLGVBQWUsRUFBRSxjQUFjLENBQUMsQ0FBQztZQUN4RCxvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztBQUM5QyxZQUFZLE1BQU07O1FBRVYsS0FBSyxZQUFZLENBQUMsb0JBQW9CLENBQUM7UUFDdkMsS0FBSyxZQUFZLENBQUMsbUJBQW1CO1lBQ2pDLGNBQWMsR0FBRyxJQUFJLENBQUM7WUFDdEIsY0FBYyxDQUFDLFVBQVUsQ0FBQyxlQUFlLENBQUMsQ0FBQztZQUMzQyxvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztBQUM5QyxZQUFZLE1BQU07O1FBRVYsS0FBSyxZQUFZLENBQUMsV0FBVztZQUN6QixLQUFLLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQztZQUNwQixRQUFRLENBQUMsSUFBSSxHQUFHLEdBQUcsR0FBRyxNQUFNLENBQUMsSUFBSSxDQUFDO1lBQ2xDLG9CQUFvQixDQUFDLFVBQVUsRUFBRSxDQUFDO0FBQzlDLFlBQVksTUFBTTs7UUFFVixLQUFLLFlBQVksQ0FBQyxpQkFBaUI7WUFDL0IsVUFBVSxHQUFHLE1BQU0sQ0FBQyxTQUFTLENBQUM7WUFDOUIsb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7QUFDOUMsWUFBWSxNQUFNOztRQUVWLEtBQUssWUFBWSxDQUFDLGdCQUFnQjtZQUM5QixvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztZQUNsQyxNQUFNO0tBQ2I7QUFDTCxDQUFDLENBQUMsQ0FBQzs7QUFFSCxNQUFNLENBQUMsT0FBTyxHQUFHLG9CQUFvQixDQUFDIiwiZmlsZSI6ImdlbmVyYXRlZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzQ29udGVudCI6WyIoZnVuY3Rpb24gZSh0LG4scil7ZnVuY3Rpb24gcyhvLHUpe2lmKCFuW29dKXtpZighdFtvXSl7dmFyIGE9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtpZighdSYmYSlyZXR1cm4gYShvLCEwKTtpZihpKXJldHVybiBpKG8sITApO3ZhciBmPW5ldyBFcnJvcihcIkNhbm5vdCBmaW5kIG1vZHVsZSAnXCIrbytcIidcIik7dGhyb3cgZi5jb2RlPVwiTU9EVUxFX05PVF9GT1VORFwiLGZ9dmFyIGw9bltvXT17ZXhwb3J0czp7fX07dFtvXVswXS5jYWxsKGwuZXhwb3J0cyxmdW5jdGlvbihlKXt2YXIgbj10W29dWzFdW2VdO3JldHVybiBzKG4/bjplKX0sbCxsLmV4cG9ydHMsZSx0LG4scil9cmV0dXJuIG5bb10uZXhwb3J0c312YXIgaT10eXBlb2YgcmVxdWlyZT09XCJmdW5jdGlvblwiJiZyZXF1aXJlO2Zvcih2YXIgbz0wO288ci5sZW5ndGg7bysrKXMocltvXSk7cmV0dXJuIHN9KSIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIFBsYXRmb3JtTWFuYWdlciA9IHJlcXVpcmUoJy4vY29tcG9uZW50cy9wbGF0Zm9ybS1tYW5hZ2VyJyk7XG5cblJlYWN0LnJlbmRlcihcbiAgICA8UGxhdGZvcm1NYW5hZ2VyIC8+LFxuICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdhcHAnKVxuKTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIFJwY0V4Y2hhbmdlID0gcmVxdWlyZSgnLi4vbGliL3JwYy9leGNoYW5nZScpO1xuXG52YXIgY29uc29sZUFjdGlvbkNyZWF0b3JzID0ge1xuICAgIHRvZ2dsZUNvbnNvbGU6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuVE9HR0xFX0NPTlNPTEUsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgdXBkYXRlQ29tcG9zZXJWYWx1ZTogZnVuY3Rpb24gKHZhbHVlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlVQREFURV9DT01QT1NFUl9WQUxVRSxcbiAgICAgICAgICAgIHZhbHVlOiB2YWx1ZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBtYWtlUmVxdWVzdDogZnVuY3Rpb24gKG9wdHMpIHtcbiAgICAgICAgbmV3IFJwY0V4Y2hhbmdlKG9wdHMpLnByb21pc2UuY2F0Y2goZnVuY3Rpb24gaWdub3JlKCkge30pO1xuICAgIH1cbn07XG5cbm1vZHVsZS5leHBvcnRzID0gY29uc29sZUFjdGlvbkNyZWF0b3JzO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIHJwYyA9IHJlcXVpcmUoJy4uL2xpYi9ycGMnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0ge1xuICAgIHJlcXVlc3RBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAodXNlcm5hbWUsIHBhc3N3b3JkKSB7XG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAnZ2V0X2F1dGhvcml6YXRpb24nLFxuICAgICAgICAgICAgcGFyYW1zOiB7XG4gICAgICAgICAgICAgICAgdXNlcm5hbWU6IHVzZXJuYW1lLFxuICAgICAgICAgICAgICAgIHBhc3N3b3JkOiBwYXNzd29yZCxcbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChyZXN1bHQpIHtcbiAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTixcbiAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogcmVzdWx0LFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIC5jYXRjaChycGMuRXJyb3IsIGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgICAgIGlmIChlcnJvci5jb2RlICYmIGVycm9yLmNvZGUgPT09IDQwMSkge1xuICAgICAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSk7XG4gICAgfSxcbiAgICBjbGVhckF1dGhvcml6YXRpb246IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTixcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBnb1RvUGFnZTogZnVuY3Rpb24gKHBhZ2UpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuQ0hBTkdFX1BBR0UsXG4gICAgICAgICAgICBwYWdlOiBwYWdlLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIGxvYWRQbGF0Zm9ybXM6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGF1dGhvcml6YXRpb24gPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCk7XG5cbiAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICBtZXRob2Q6ICdsaXN0X3BsYXRmb3JtcycsXG4gICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocGxhdGZvcm1zKSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUyxcbiAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm1zOiBwbGF0Zm9ybXMsXG4gICAgICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgICAgICBwbGF0Zm9ybXMuZm9yRWFjaChmdW5jdGlvbiAocGxhdGZvcm0pIHtcbiAgICAgICAgICAgICAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcubGlzdF9hZ2VudHMnLFxuICAgICAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgICAgICAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKGFnZW50c0xpc3QpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybS5hZ2VudHMgPSBhZ2VudHNMaXN0O1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAncGxhdGZvcm1zLnV1aWQuJyArIHBsYXRmb3JtLnV1aWQgKyAnLnN0YXR1c19hZ2VudHMnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKGFnZW50U3RhdHVzZXMpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtLmFnZW50cy5mb3JFYWNoKGZ1bmN0aW9uIChhZ2VudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmICghYWdlbnRTdGF0dXNlcy5zb21lKGZ1bmN0aW9uIChzdGF0dXMpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKGFnZW50LnV1aWQgPT09IHN0YXR1cy51dWlkKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gZmFsc2U7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5wcm9jZXNzX2lkID0gc3RhdHVzLnByb2Nlc3NfaWQ7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5yZXR1cm5fY29kZSA9IHN0YXR1cy5yZXR1cm5fY29kZTtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gZmFsc2U7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50LnByb2Nlc3NfaWQgPSBudWxsO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5yZXR1cm5fY29kZSA9IG51bGw7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk0sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgLmNhdGNoKGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgICAgIGlmIChlcnJvci5jb2RlICYmIGVycm9yLmNvZGUgPT09IDQwMSkge1xuICAgICAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSk7XG4gICAgfSxcbiAgICBzdGFydEFnZW50OiBmdW5jdGlvbiAocGxhdGZvcm0sIGFnZW50KSB7XG4gICAgICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuXG4gICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSB0cnVlO1xuXG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk0sXG4gICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgIH0pO1xuXG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAncGxhdGZvcm1zLnV1aWQuJyArIHBsYXRmb3JtLnV1aWQgKyAnLnN0YXJ0X2FnZW50JyxcbiAgICAgICAgICAgIHBhcmFtczogW2FnZW50LnV1aWRdLFxuICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHN0YXR1cykge1xuICAgICAgICAgICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICBhZ2VudC5wcm9jZXNzX2lkID0gc3RhdHVzLnByb2Nlc3NfaWQ7XG4gICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBzdGF0dXMucmV0dXJuX2NvZGU7XG5cbiAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk0sXG4gICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgc3RvcEFnZW50OiBmdW5jdGlvbiAocGxhdGZvcm0sIGFnZW50KSB7XG4gICAgICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuXG4gICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSB0cnVlO1xuXG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk0sXG4gICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgIH0pO1xuXG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAncGxhdGZvcm1zLnV1aWQuJyArIHBsYXRmb3JtLnV1aWQgKyAnLnN0b3BfYWdlbnQnLFxuICAgICAgICAgICAgcGFyYW1zOiBbYWdlbnQudXVpZF0sXG4gICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAoc3RhdHVzKSB7XG4gICAgICAgICAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IGZhbHNlO1xuICAgICAgICAgICAgICAgIGFnZW50LnByb2Nlc3NfaWQgPSBzdGF0dXMucHJvY2Vzc19pZDtcbiAgICAgICAgICAgICAgICBhZ2VudC5yZXR1cm5fY29kZSA9IHN0YXR1cy5yZXR1cm5fY29kZTtcblxuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgfSxcbn07XG5cbndpbmRvdy5vbmhhc2hjaGFuZ2UgPSBmdW5jdGlvbiAoKSB7XG4gICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuZ29Ub1BhZ2UobG9jYXRpb24uaGFzaC5zdWJzdHIoMSkpO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG5cbnZhciBBZ2VudFJvdyA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfb25TdG9wOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLnN0b3BBZ2VudCh0aGlzLnByb3BzLnBsYXRmb3JtLCB0aGlzLnByb3BzLmFnZW50KTtcbiAgICB9LFxuICAgIF9vblN0YXJ0OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLnN0YXJ0QWdlbnQodGhpcy5wcm9wcy5wbGF0Zm9ybSwgdGhpcy5wcm9wcy5hZ2VudCk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGFnZW50ID0gdGhpcy5wcm9wcy5hZ2VudCwgc3RhdHVzLCBhY3Rpb247XG5cbiAgICAgICAgaWYgKGFnZW50LmFjdGlvblBlbmRpbmcgPT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgc3RhdHVzID0gJ1JldHJpZXZpbmcgc3RhdHVzLi4uJztcbiAgICAgICAgfSBlbHNlIGlmIChhZ2VudC5hY3Rpb25QZW5kaW5nKSB7XG4gICAgICAgICAgICBpZiAoYWdlbnQucHJvY2Vzc19pZCA9PT0gbnVsbCB8fCBhZ2VudC5yZXR1cm5fY29kZSAhPT0gbnVsbCkge1xuICAgICAgICAgICAgICAgIHN0YXR1cyA9ICdTdGFydGluZy4uLic7XG4gICAgICAgICAgICAgICAgYWN0aW9uID0gKFxuICAgICAgICAgICAgICAgICAgICA8aW5wdXQgY2xhc3NOYW1lPVwiYnV0dG9uXCIgdHlwZT1cImJ1dHRvblwiIHZhbHVlPVwiU3RhcnRcIiBkaXNhYmxlZCAvPlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIHN0YXR1cyA9ICdTdG9wcGluZy4uLic7XG4gICAgICAgICAgICAgICAgYWN0aW9uID0gKFxuICAgICAgICAgICAgICAgICAgICA8aW5wdXQgY2xhc3NOYW1lPVwiYnV0dG9uXCIgdHlwZT1cImJ1dHRvblwiIHZhbHVlPVwiU3RvcFwiIGRpc2FibGVkIC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGlmIChhZ2VudC5wcm9jZXNzX2lkID09PSBudWxsKSB7XG4gICAgICAgICAgICAgICAgc3RhdHVzID0gJ05ldmVyIHN0YXJ0ZWQnO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0YXJ0XCIgb25DbGljaz17dGhpcy5fb25TdGFydH0gLz5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfSBlbHNlIGlmIChhZ2VudC5yZXR1cm5fY29kZSA9PT0gbnVsbCkge1xuICAgICAgICAgICAgICAgIHN0YXR1cyA9ICdSdW5uaW5nIChQSUQgJyArIGFnZW50LnByb2Nlc3NfaWQgKyAnKSc7XG4gICAgICAgICAgICAgICAgYWN0aW9uID0gKFxuICAgICAgICAgICAgICAgICAgICA8aW5wdXQgY2xhc3NOYW1lPVwiYnV0dG9uXCIgdHlwZT1cImJ1dHRvblwiIHZhbHVlPVwiU3RvcFwiIG9uQ2xpY2s9e3RoaXMuX29uU3RvcH0gLz5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnU3RvcHBlZCAocmV0dXJuZWQgJyArIGFnZW50LnJldHVybl9jb2RlICsgJyknO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0YXJ0XCIgb25DbGljaz17dGhpcy5fb25TdGFydH0gLz5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDx0cj5cbiAgICAgICAgICAgICAgICA8dGQ+e2FnZW50Lm5hbWV9PC90ZD5cbiAgICAgICAgICAgICAgICA8dGQ+e2FnZW50LnV1aWR9PC90ZD5cbiAgICAgICAgICAgICAgICA8dGQ+e3N0YXR1c308L3RkPlxuICAgICAgICAgICAgICAgIDx0ZD57YWN0aW9ufTwvdGQ+XG4gICAgICAgICAgICA8L3RyPlxuICAgICAgICApO1xuICAgIH0sXG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBBZ2VudFJvdztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9jb25zb2xlLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG5cbnZhciBDb21wb3NlciA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnJlcGxhY2VTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICBfb25TZW5kQ2xpY2s6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLm1ha2VSZXF1ZXN0KEpTT04ucGFyc2UodGhpcy5zdGF0ZS5jb21wb3NlclZhbHVlKSk7XG4gICAgfSxcbiAgICBfb25UZXh0YXJlYUNoYW5nZTogZnVuY3Rpb24gKGUpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLnVwZGF0ZUNvbXBvc2VyVmFsdWUoZS50YXJnZXQudmFsdWUpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImNvbXBvc2VyXCI+XG4gICAgICAgICAgICAgICAgPHRleHRhcmVhXG4gICAgICAgICAgICAgICAgICAgIGtleT17dGhpcy5zdGF0ZS5jb21wb3NlcklkfVxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25UZXh0YXJlYUNoYW5nZX1cbiAgICAgICAgICAgICAgICAgICAgZGVmYXVsdFZhbHVlPXt0aGlzLnN0YXRlLmNvbXBvc2VyVmFsdWV9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwic2VuZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT1cIlNlbmRcIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudmFsaWR9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uU2VuZENsaWNrfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICB2YXIgY29tcG9zZXJWYWx1ZSA9IGNvbnNvbGVTdG9yZS5nZXRDb21wb3NlclZhbHVlKCk7XG4gICAgdmFyIHZhbGlkID0gdHJ1ZTtcblxuICAgIHRyeSB7XG4gICAgICAgIEpTT04ucGFyc2UoY29tcG9zZXJWYWx1ZSk7XG4gICAgfSBjYXRjaCAoZXgpIHtcbiAgICAgICAgaWYgKGV4IGluc3RhbmNlb2YgU3ludGF4RXJyb3IpIHtcbiAgICAgICAgICAgIHZhbGlkID0gZmFsc2U7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICB0aHJvdyBleDtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIGNvbXBvc2VySWQ6IGNvbnNvbGVTdG9yZS5nZXRDb21wb3NlcklkKCksXG4gICAgICAgIGNvbXBvc2VyVmFsdWU6IGNvbXBvc2VyVmFsdWUsXG4gICAgICAgIHZhbGlkOiB2YWxpZCxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbXBvc2VyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgQ29tcG9zZXIgPSByZXF1aXJlKCcuL2NvbXBvc2VyJyk7XG52YXIgQ29udmVyc2F0aW9uID0gcmVxdWlyZSgnLi9jb252ZXJzYXRpb24nKTtcblxudmFyIENvbnNvbGUgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImNvbnNvbGVcIj5cbiAgICAgICAgICAgICAgICA8Q29udmVyc2F0aW9uIC8+XG4gICAgICAgICAgICAgICAgPENvbXBvc2VyIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBDb25zb2xlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgJCA9IHJlcXVpcmUoJ2pxdWVyeScpO1xudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIEV4Y2hhbmdlID0gcmVxdWlyZSgnLi9leGNoYW5nZScpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG5cbnZhciBDb252ZXJzYXRpb24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyICRjb252ZXJzYXRpb24gPSAkKHRoaXMucmVmcy5jb252ZXJzYXRpb24uZ2V0RE9NTm9kZSgpKTtcblxuICAgICAgICBpZiAoJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSA+ICRjb252ZXJzYXRpb24uaGVpZ2h0KCkpIHtcbiAgICAgICAgICAgICRjb252ZXJzYXRpb24uc2Nyb2xsVG9wKCRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudERpZFVwZGF0ZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgJGNvbnZlcnNhdGlvbiA9ICQodGhpcy5yZWZzLmNvbnZlcnNhdGlvbi5nZXRET01Ob2RlKCkpO1xuXG4gICAgICAgICRjb252ZXJzYXRpb24uc3RvcCgpLmFuaW1hdGUoeyBzY3JvbGxUb3A6ICRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykgfSwgNTAwKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgcmVmPVwiY29udmVyc2F0aW9uXCIgY2xhc3NOYW1lPVwiY29udmVyc2F0aW9uXCI+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXhjaGFuZ2VzLm1hcChmdW5jdGlvbiAoZXhjaGFuZ2UsIGluZGV4KSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8RXhjaGFuZ2Uga2V5PXtpbmRleH0gZXhjaGFuZ2U9e2V4Y2hhbmdlfSAvPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4geyBleGNoYW5nZXM6IGNvbnNvbGVTdG9yZS5nZXRFeGNoYW5nZXMoKSB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbnZlcnNhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIEV4Y2hhbmdlID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIF9mb3JtYXRUaW1lOiBmdW5jdGlvbiAodGltZSkge1xuICAgICAgICB2YXIgZCA9IG5ldyBEYXRlKCk7XG5cbiAgICAgICAgZC5zZXRUaW1lKHRpbWUpO1xuXG4gICAgICAgIHJldHVybiBkLnRvTG9jYWxlU3RyaW5nKCk7XG4gICAgfSxcbiAgICBfZm9ybWF0TWVzc2FnZTogZnVuY3Rpb24gKG1lc3NhZ2UpIHtcbiAgICAgICAgcmV0dXJuIEpTT04uc3RyaW5naWZ5KG1lc3NhZ2UsIG51bGwsICcgICAgJyk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGV4Y2hhbmdlID0gdGhpcy5wcm9wcy5leGNoYW5nZTtcbiAgICAgICAgdmFyIGNsYXNzZXMgPSBbJ3Jlc3BvbnNlJ107XG4gICAgICAgIHZhciByZXNwb25zZVRleHQ7XG5cbiAgICAgICAgaWYgKCFleGNoYW5nZS5jb21wbGV0ZWQpIHtcbiAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncmVzcG9uc2UtLXBlbmRpbmcnKTtcbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9ICdXYWl0aW5nIGZvciByZXNwb25zZS4uLic7XG4gICAgICAgIH0gZWxzZSBpZiAoZXhjaGFuZ2UuZXJyb3IpIHtcbiAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncmVzcG9uc2UtLWVycm9yJyk7XG4gICAgICAgICAgICByZXNwb25zZVRleHQgPSBleGNoYW5nZS5lcnJvci5tZXNzYWdlO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgaWYgKGV4Y2hhbmdlLnJlc3BvbnNlLmVycm9yKSB7XG4gICAgICAgICAgICAgICAgY2xhc3Nlcy5wdXNoKCdyZXNwb25zZS0tZXJyb3InKTtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgcmVzcG9uc2VUZXh0ID0gdGhpcy5fZm9ybWF0TWVzc2FnZShleGNoYW5nZS5yZXNwb25zZSk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJleGNoYW5nZVwiPlxuICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwicmVxdWVzdFwiPlxuICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInRpbWVcIj57dGhpcy5fZm9ybWF0VGltZShleGNoYW5nZS5pbml0aWF0ZWQpfTwvZGl2PlxuICAgICAgICAgICAgICAgICAgICA8cHJlPnt0aGlzLl9mb3JtYXRNZXNzYWdlKGV4Y2hhbmdlLnJlcXVlc3QpfTwvcHJlPlxuICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPXtjbGFzc2VzLmpvaW4oJyAnKX0+XG4gICAgICAgICAgICAgICAgICAgIHtleGNoYW5nZS5jb21wbGV0ZWQgJiYgPGRpdiBjbGFzc05hbWU9XCJ0aW1lXCI+e3RoaXMuX2Zvcm1hdFRpbWUoZXhjaGFuZ2UuY29tcGxldGVkKX08L2Rpdj59XG4gICAgICAgICAgICAgICAgICAgIDxwcmU+e3Jlc3BvbnNlVGV4dH08L3ByZT5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IEV4Y2hhbmdlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgQWdlbnRSb3cgPSByZXF1aXJlKCcuL2FnZW50LXJvdycpO1xudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgSG9tZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIHNldFRpbWVvdXQocGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMubG9hZFBsYXRmb3Jtcyk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIHBsYXRmb3JtcztcblxuICAgICAgICBpZiAoIXRoaXMuc3RhdGUucGxhdGZvcm1zKSB7XG4gICAgICAgICAgICBwbGF0Zm9ybXMgPSAoXG4gICAgICAgICAgICAgICAgPHA+TG9hZGluZyBwbGF0Zm9ybXMuLi48L3A+XG4gICAgICAgICAgICApO1xuICAgICAgICB9IGVsc2UgaWYgKCF0aGlzLnN0YXRlLnBsYXRmb3Jtcy5sZW5ndGgpIHtcbiAgICAgICAgICAgIHBsYXRmb3JtcyA9IChcbiAgICAgICAgICAgICAgICA8cD5ObyBwbGF0Zm9ybXMgZm91bmQuPC9wPlxuICAgICAgICAgICAgKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIHBsYXRmb3JtcyA9IHRoaXMuc3RhdGUucGxhdGZvcm1zLm1hcChmdW5jdGlvbiAocGxhdGZvcm0pIHtcbiAgICAgICAgICAgICAgICB2YXIgYWdlbnRzO1xuXG4gICAgICAgICAgICAgICAgaWYgKCFwbGF0Zm9ybS5hZ2VudHMpIHtcbiAgICAgICAgICAgICAgICAgICAgYWdlbnRzID0gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPHA+TG9hZGluZyBhZ2VudHMuLi48L3A+XG4gICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmICghcGxhdGZvcm0uYWdlbnRzLmxlbmd0aCkge1xuICAgICAgICAgICAgICAgICAgICBhZ2VudHMgPSAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8cD5ObyBhZ2VudHMgaW5zdGFsbGVkLjwvcD5cbiAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICBhZ2VudHMgPSAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8dGFibGU+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoZWFkPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dHI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGg+QWdlbnQ8L3RoPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoPlVVSUQ8L3RoPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoPlN0YXR1czwvdGg+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGg+QWN0aW9uPC90aD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90cj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3RoZWFkPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0Ym9keT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAge3BsYXRmb3JtLmFnZW50cy5tYXAoZnVuY3Rpb24gKGFnZW50KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxBZ2VudFJvd1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBrZXk9e2FnZW50LnV1aWR9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtPXtwbGF0Zm9ybX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQ9e2FnZW50fSAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90Ym9keT5cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvdGFibGU+XG4gICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJwbGF0Zm9ybVwiIGtleT17cGxhdGZvcm0udXVpZH0+XG4gICAgICAgICAgICAgICAgICAgICAgICA8aDI+e3BsYXRmb3JtLm5hbWV9ICh7cGxhdGZvcm0udXVpZH0pPC9oMj5cbiAgICAgICAgICAgICAgICAgICAgICAgIHthZ2VudHN9XG4gICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImhvbWVcIj5cbiAgICAgICAgICAgICAgICB7cGxhdGZvcm1zfVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfSxcbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgICAgcGxhdGZvcm1zOiBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQbGF0Zm9ybXMoKSxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IEhvbWU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xuXG52YXIgTG9nT3V0QnV0dG9uID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIF9vbkNsaWNrOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLmNsZWFyQXV0aG9yaXphdGlvbigpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8YnV0dG9uIGNsYXNzTmFtZT1cImJ1dHRvblwiIG9uQ2xpY2s9e3RoaXMuX29uQ2xpY2t9PkxvZyBvdXQ8L2J1dHRvbj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBMb2dPdXRCdXR0b247XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIGxvZ2luRm9ybVN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL2xvZ2luLWZvcm0tc3RvcmUnKTtcblxudmFyIExvZ2luRm9ybSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBsb2dpbkZvcm1TdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vblN0b3Jlc0NoYW5nZSk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBsb2dpbkZvcm1TdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vblN0b3Jlc0NoYW5nZSk7XG4gICAgfSxcbiAgICBfb25TdG9yZXNDaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICBfb25JbnB1dENoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKHtcbiAgICAgICAgICAgIHVzZXJuYW1lOiB0aGlzLnJlZnMudXNlcm5hbWUuZ2V0RE9NTm9kZSgpLnZhbHVlLFxuICAgICAgICAgICAgcGFzc3dvcmQ6IHRoaXMucmVmcy5wYXNzd29yZC5nZXRET01Ob2RlKCkudmFsdWUsXG4gICAgICAgICAgICBlcnJvcjogbnVsbCxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBfb25TdWJtaXQ6IGZ1bmN0aW9uIChlKSB7XG4gICAgICAgIGUucHJldmVudERlZmF1bHQoKTtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMucmVxdWVzdEF1dGhvcml6YXRpb24oXG4gICAgICAgICAgICB0aGlzLnN0YXRlLnVzZXJuYW1lLFxuICAgICAgICAgICAgdGhpcy5zdGF0ZS5wYXNzd29yZFxuICAgICAgICApO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8Zm9ybSBjbGFzc05hbWU9XCJsb2dpbi1mb3JtXCIgb25TdWJtaXQ9e3RoaXMuX29uU3VibWl0fT5cbiAgICAgICAgICAgICAgICA8aDE+Vk9MVFRST04oVE0pIFBsYXRmb3JtIE1hbmFnZXI8L2gxPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICByZWY9XCJ1c2VybmFtZVwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJ0ZXh0XCJcbiAgICAgICAgICAgICAgICAgICAgcGxhY2Vob2xkZXI9XCJVc2VybmFtZVwiXG4gICAgICAgICAgICAgICAgICAgIG9uQ2hhbmdlPXt0aGlzLl9vbklucHV0Q2hhbmdlfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIHJlZj1cInBhc3N3b3JkXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cInBhc3N3b3JkXCJcbiAgICAgICAgICAgICAgICAgICAgcGxhY2Vob2xkZXI9XCJQYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIG9uQ2hhbmdlPXt0aGlzLl9vbklucHV0Q2hhbmdlfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJzdWJtaXRcIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT1cIkxvZyBpblwiXG4gICAgICAgICAgICAgICAgICAgIGRpc2FibGVkPXshdGhpcy5zdGF0ZS51c2VybmFtZSB8fCAhdGhpcy5zdGF0ZS5wYXNzd29yZH1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmVycm9yID8gKFxuICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImVycm9yXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5lcnJvci5tZXNzYWdlfSAoe3RoaXMuc3RhdGUuZXJyb3IuY29kZX0pXG4gICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICkgOiBudWxsIH1cbiAgICAgICAgICAgIDwvZm9ybT5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7IGVycm9yOiBsb2dpbkZvcm1TdG9yZS5nZXRMYXN0RXJyb3IoKSB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IExvZ2luRm9ybTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIExvZ091dEJ1dHRvbiA9IHJlcXVpcmUoJy4vbG9nLW91dC1idXR0b24nKTtcblxudmFyIE5hdmlnYXRpb24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIm5hdmlnYXRpb25cIj5cbiAgICAgICAgICAgICAgICA8aDE+PGEgaHJlZj1cIiNob21lXCI+Vk9MVFRST04oVE0pIFBsYXRmb3JtIE1hbmFnZXI8L2E+PC9oMT5cbiAgICAgICAgICAgICAgICA8TG9nT3V0QnV0dG9uIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBOYXZpZ2F0aW9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgQ29uc29sZSA9IHJlcXVpcmUoJy4vY29uc29sZScpO1xudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9jb25zb2xlLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG52YXIgSG9tZSA9IHJlcXVpcmUoJy4vaG9tZScpO1xudmFyIExvZ2luRm9ybSA9IHJlcXVpcmUoJy4vbG9naW4tZm9ybScpO1xudmFyIE5hdmlnYXRpb24gPSByZXF1aXJlKCcuL25hdmlnYXRpb24nKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG5cbnZhciBQbGF0Zm9ybU1hbmFnZXIgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgICAgICBjb25zb2xlU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgICAgICBjb25zb2xlU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uQnV0dG9uQ2xpY2s6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLnRvZ2dsZUNvbnNvbGUoKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgY2xhc3NlcyA9IFsncGxhdGZvcm0tbWFuYWdlciddO1xuXG4gICAgICAgIGlmICghdGhpcy5zdGF0ZS5jb25zb2xlU2hvd24pIHtcbiAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncGxhdGZvcm0tbWFuYWdlci0tY29uc29sZS1oaWRkZW4nKTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT17Y2xhc3Nlcy5qb2luKCcgJyl9PlxuICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwibWFpblwiPlxuICAgICAgICAgICAgICAgICAgICB7IXRoaXMuc3RhdGUubG9nZ2VkSW4gJiYgPExvZ2luRm9ybSAvPn1cbiAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUubG9nZ2VkSW4gJiYgPE5hdmlnYXRpb24gLz59XG4gICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxIb21lIC8+fVxuICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJ0b2dnbGUgYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHZhbHVlPXsnQ29uc29sZSAnICsgKHRoaXMuc3RhdGUuY29uc29sZVNob3duID8gJ1xcdTI1YmMnIDogJ1xcdTI1YjInKX1cbiAgICAgICAgICAgICAgICAgICAgb25DbGljaz17dGhpcy5fb25CdXR0b25DbGlja31cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmNvbnNvbGVTaG93biAmJiA8Q29uc29sZSBjbGFzc05hbWU9XCJjb25zb2xlXCIgLz59XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7XG4gICAgICAgIGNvbnNvbGVTaG93bjogY29uc29sZVN0b3JlLmdldENvbnNvbGVTaG93bigpLFxuICAgICAgICBsb2dnZWRJbjogISFwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCksXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBQbGF0Zm9ybU1hbmFnZXI7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBrZXlNaXJyb3IgPSByZXF1aXJlKCdyZWFjdC9saWIva2V5TWlycm9yJyk7XG5cbm1vZHVsZS5leHBvcnRzID0ga2V5TWlycm9yKHtcbiAgICBUT0dHTEVfQ09OU09MRTogbnVsbCxcblxuICAgIFVQREFURV9DT01QT1NFUl9WQUxVRTogbnVsbCxcblxuICAgIE1BS0VfUkVRVUVTVDogbnVsbCxcbiAgICBGQUlMX1JFUVVFU1Q6IG51bGwsXG4gICAgUkVDRUlWRV9SRVNQT05TRTogbnVsbCxcblxuICAgIFJFQ0VJVkVfQVVUSE9SSVpBVElPTjogbnVsbCxcbiAgICBSRUNFSVZFX1VOQVVUSE9SSVpFRDogbnVsbCxcbiAgICBDTEVBUl9BVVRIT1JJWkFUSU9OOiBudWxsLFxuXG4gICAgQ0hBTkdFX1BBR0U6IG51bGwsXG5cbiAgICBSRUNFSVZFX1BMQVRGT1JNUzogbnVsbCxcbiAgICBSRUNFSVZFX1BMQVRGT1JNOiBudWxsLFxufSk7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBEaXNwYXRjaGVyID0gcmVxdWlyZSgnZmx1eCcpLkRpc3BhdGNoZXI7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG5cbnZhciBkaXNwYXRjaGVyID0gbmV3IERpc3BhdGNoZXIoKTtcblxuZGlzcGF0Y2hlci5kaXNwYXRjaCA9IGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBpZiAoYWN0aW9uLnR5cGUgaW4gQUNUSU9OX1RZUEVTKSB7XG4gICAgICAgIHJldHVybiBPYmplY3QuZ2V0UHJvdG90eXBlT2YodGhpcykuZGlzcGF0Y2guY2FsbCh0aGlzLCBhY3Rpb24pO1xuICAgIH1cblxuICAgIHRocm93ICdEaXNwYXRjaCBlcnJvcjogaW52YWxpZCBhY3Rpb24gdHlwZSAnICsgYWN0aW9uLnR5cGU7XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IGRpc3BhdGNoZXI7XG4iLCIndXNlIHN0cmljdCc7XG5cbmZ1bmN0aW9uIFJwY0Vycm9yKGVycm9yKSB7XG4gICAgdGhpcy5uYW1lID0gJ1JwY0Vycm9yJztcbiAgICB0aGlzLmNvZGUgPSBlcnJvci5jb2RlO1xuICAgIHRoaXMubWVzc2FnZSA9IGVycm9yLm1lc3NhZ2U7XG4gICAgdGhpcy5kYXRhID0gZXJyb3IuZGF0YTtcbn1cblJwY0Vycm9yLnByb3RvdHlwZSA9IE9iamVjdC5jcmVhdGUoRXJyb3IucHJvdG90eXBlKTtcblJwY0Vycm9yLnByb3RvdHlwZS5jb25zdHJ1Y3RvciA9IFJwY0Vycm9yO1xuXG5tb2R1bGUuZXhwb3J0cyA9IFJwY0Vycm9yO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgdXVpZCA9IHJlcXVpcmUoJ25vZGUtdXVpZCcpO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi8uLi9kaXNwYXRjaGVyJyk7XG52YXIgUnBjRXJyb3IgPSByZXF1aXJlKCcuL2Vycm9yJyk7XG52YXIgeGhyID0gcmVxdWlyZSgnLi4veGhyJyk7XG5cbmZ1bmN0aW9uIFJwY0V4Y2hhbmdlKG9wdHMpIHtcbiAgICBpZiAoIXRoaXMgaW5zdGFuY2VvZiBScGNFeGNoYW5nZSkge1xuICAgICAgICByZXR1cm4gbmV3IFJwY0V4Y2hhbmdlKG9wdHMpO1xuICAgIH1cblxuICAgIHZhciBleGNoYW5nZSA9IHRoaXM7XG5cbiAgICAvLyBUT0RPOiB2YWxpZGF0ZSBvcHRzXG4gICAgb3B0cy5qc29ucnBjID0gJzIuMCc7XG4gICAgb3B0cy5pZCA9IHV1aWQudjEoKTtcblxuICAgIGV4Y2hhbmdlLmluaXRpYXRlZCA9IERhdGUubm93KCk7XG4gICAgZXhjaGFuZ2UucmVxdWVzdCA9IG9wdHM7XG5cbiAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLk1BS0VfUkVRVUVTVCxcbiAgICAgICAgZXhjaGFuZ2U6IGV4Y2hhbmdlLFxuICAgICAgICByZXF1ZXN0OiBleGNoYW5nZS5yZXF1ZXN0LFxuICAgIH0pO1xuXG4gICAgZXhjaGFuZ2UucHJvbWlzZSA9IG5ldyB4aHIuUmVxdWVzdCh7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICB1cmw6ICcvanNvbnJwYycsXG4gICAgICAgIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIGRhdGE6IEpTT04uc3RyaW5naWZ5KGV4Y2hhbmdlLnJlcXVlc3QpLFxuICAgICAgICB0aW1lb3V0OiA2MDAwMCxcbiAgICB9KVxuICAgICAgICAuZmluYWxseShmdW5jdGlvbiAoKSB7XG4gICAgICAgICAgICBleGNoYW5nZS5jb21wbGV0ZWQgPSBEYXRlLm5vdygpO1xuICAgICAgICB9KVxuICAgICAgICAudGhlbihmdW5jdGlvbiAocmVzcG9uc2UpIHtcbiAgICAgICAgICAgIGV4Y2hhbmdlLnJlc3BvbnNlID0gcmVzcG9uc2U7XG5cbiAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1JFU1BPTlNFLFxuICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICByZXNwb25zZTogcmVzcG9uc2UsXG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgaWYgKHJlc3BvbnNlLmVycm9yKSB7XG4gICAgICAgICAgICAgICAgdGhyb3cgbmV3IFJwY0Vycm9yKHJlc3BvbnNlLmVycm9yKTtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlLnJlc3VsdDtcbiAgICAgICAgfSlcbiAgICAgICAgLmNhdGNoKHhoci5FcnJvciwgZnVuY3Rpb24gKGVycm9yKSB7XG4gICAgICAgICAgICBleGNoYW5nZS5lcnJvciA9IGVycm9yO1xuXG4gICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuRkFJTF9SRVFVRVNULFxuICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgIH0pO1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFJwY0V4Y2hhbmdlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5tb2R1bGUuZXhwb3J0cyA9IHtcbiAgICBFcnJvcjogcmVxdWlyZSgnLi9lcnJvcicpLFxuICAgIEV4Y2hhbmdlOiByZXF1aXJlKCcuL2V4Y2hhbmdlJyksXG59O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgRXZlbnRFbWl0dGVyID0gcmVxdWlyZSgnZXZlbnRzJykuRXZlbnRFbWl0dGVyO1xuXG52YXIgQ0hBTkdFX0VWRU5UID0gJ2NoYW5nZSc7XG5cbmZ1bmN0aW9uIFN0b3JlKCkge1xuICAgIEV2ZW50RW1pdHRlci5jYWxsKHRoaXMpO1xufVxuU3RvcmUucHJvdG90eXBlID0gRXZlbnRFbWl0dGVyLnByb3RvdHlwZTtcblxuU3RvcmUucHJvdG90eXBlLmVtaXRDaGFuZ2UgPSBmdW5jdGlvbigpIHtcbiAgICB0aGlzLmVtaXQoQ0hBTkdFX0VWRU5UKTtcbn07XG5cblN0b3JlLnByb3RvdHlwZS5hZGRDaGFuZ2VMaXN0ZW5lciA9IGZ1bmN0aW9uIChjYWxsYmFjaykge1xuICAgIHRoaXMub24oQ0hBTkdFX0VWRU5ULCBjYWxsYmFjayk7XG59O1xuXG5TdG9yZS5wcm90b3R5cGUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIgPSBmdW5jdGlvbiAoY2FsbGJhY2spIHtcbiAgICB0aGlzLnJlbW92ZUxpc3RlbmVyKENIQU5HRV9FVkVOVCwgY2FsbGJhY2spO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBTdG9yZTtcbiIsIid1c2Ugc3RyaWN0JztcblxuZnVuY3Rpb24gWGhyRXJyb3IobWVzc2FnZSwgcmVzcG9uc2UpIHtcbiAgICB0aGlzLm5hbWUgPSAnWGhyRXJyb3InO1xuICAgIHRoaXMubWVzc2FnZSA9IG1lc3NhZ2U7XG4gICAgdGhpcy5yZXNwb25zZSA9IHJlc3BvbnNlO1xufVxuWGhyRXJyb3IucHJvdG90eXBlID0gT2JqZWN0LmNyZWF0ZShFcnJvci5wcm90b3R5cGUpO1xuWGhyRXJyb3IucHJvdG90eXBlLmNvbnN0cnVjdG9yID0gWGhyRXJyb3I7XG5cbm1vZHVsZS5leHBvcnRzID0gWGhyRXJyb3I7XG4iLCIndXNlIHN0cmljdCc7XG5cbm1vZHVsZS5leHBvcnRzID0ge1xuICAgIFJlcXVlc3Q6IHJlcXVpcmUoJy4vcmVxdWVzdCcpLFxuICAgIEVycm9yOiByZXF1aXJlKCcuL2Vycm9yJyksXG59O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgalF1ZXJ5ID0gcmVxdWlyZSgnanF1ZXJ5Jyk7XG52YXIgUHJvbWlzZSA9IHJlcXVpcmUoJ2JsdWViaXJkJyk7XG5cbnZhciBYaHJFcnJvciA9IHJlcXVpcmUoJy4vZXJyb3InKTtcblxuZnVuY3Rpb24gWGhyUmVxdWVzdChvcHRzKSB7XG4gICAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uIChyZXNvbHZlLCByZWplY3QpIHtcbiAgICAgICAgb3B0cy5zdWNjZXNzID0gcmVzb2x2ZTtcbiAgICAgICAgb3B0cy5lcnJvciA9IGZ1bmN0aW9uIChyZXNwb25zZSwgdHlwZSkge1xuICAgICAgICAgICAgc3dpdGNoICh0eXBlKSB7XG4gICAgICAgICAgICBjYXNlICdlcnJvcic6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignU2VydmVyIHJldHVybmVkICcgKyByZXNwb25zZS5zdGF0dXMgKyAnIHN0YXR1cycsIHJlc3BvbnNlKSk7XG4gICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICBjYXNlICd0aW1lb3V0JzpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdSZXF1ZXN0IHRpbWVkIG91dCcsIHJlc3BvbnNlKSk7XG4gICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICBkZWZhdWx0OlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1JlcXVlc3QgZmFpbGVkOiAnICsgdHlwZSwgcmVzcG9uc2UpKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfTtcblxuICAgICAgICBqUXVlcnkuYWpheChvcHRzKTtcbiAgICB9KTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBYaHJSZXF1ZXN0O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2NvbXBvc2VySWQgPSBEYXRlLm5vdygpO1xudmFyIF9jb21wb3NlclZhbHVlID0gJyc7XG52YXIgX2NvbnNvbGVTaG93biA9IGZhbHNlO1xudmFyIF9leGNoYW5nZXMgPSBbXTtcblxudmFyIGNvbnNvbGVTdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5jb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJJZCA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2NvbXBvc2VySWQ7XG59O1xuXG5jb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJWYWx1ZSA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2NvbXBvc2VyVmFsdWU7XG59O1xuXG5jb25zb2xlU3RvcmUuZ2V0Q29uc29sZVNob3duID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfY29uc29sZVNob3duO1xufTtcblxuY29uc29sZVN0b3JlLmdldEV4Y2hhbmdlcyA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2V4Y2hhbmdlcztcbn07XG5cbmZ1bmN0aW9uIF9yZXNldENvbXBvc2VyVmFsdWUodXBkYXRlTWV0aG9kKSB7XG4gICAgdmFyIGF1dGhvcml6YXRpb24gPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCk7XG4gICAgdmFyIHBhcnNlZDtcblxuICAgIHRyeSB7XG4gICAgICAgIHBhcnNlZCA9IEpTT04ucGFyc2UoX2NvbXBvc2VyVmFsdWUpO1xuXG4gICAgICAgIGlmICh1cGRhdGVNZXRob2QpIHtcbiAgICAgICAgICAgIHBhcnNlZC5tZXRob2QgPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlKCk7XG4gICAgICAgIH1cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIHBhcnNlZCA9IHsgbWV0aG9kOiBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlKCkgfTtcbiAgICB9XG5cbiAgICBpZiAoYXV0aG9yaXphdGlvbikge1xuICAgICAgICBwYXJzZWQuYXV0aG9yaXphdGlvbiA9IGF1dGhvcml6YXRpb247XG4gICAgfSBlbHNlIHtcbiAgICAgICAgZGVsZXRlIHBhcnNlZC5hdXRob3JpemF0aW9uO1xuICAgIH1cblxuICAgIF9jb21wb3NlclZhbHVlID0gSlNPTi5zdHJpbmdpZnkocGFyc2VkLCBudWxsLCAnICAgICcpO1xufVxuXG5fcmVzZXRDb21wb3NlclZhbHVlKCk7XG5cbmNvbnNvbGVTdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgZGlzcGF0Y2hlci53YWl0Rm9yKFtwbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuXSk7XG5cbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlRPR0dMRV9DT05TT0xFOlxuICAgICAgICAgICAgX2NvbnNvbGVTaG93biA9ICFfY29uc29sZVNob3duO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlVQREFURV9DT01QT1NFUl9WQUxVRTpcbiAgICAgICAgICAgIF9jb21wb3NlclZhbHVlID0gYWN0aW9uLnZhbHVlO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQ6XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfY29tcG9zZXJJZCA9IERhdGUubm93KCk7XG4gICAgICAgICAgICBfcmVzZXRDb21wb3NlclZhbHVlKCk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0hBTkdFX1BBR0U6XG4gICAgICAgICAgICBfY29tcG9zZXJJZCA9IERhdGUubm93KCk7XG4gICAgICAgICAgICBfcmVzZXRDb21wb3NlclZhbHVlKHRydWUpO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLk1BS0VfUkVRVUVTVDpcbiAgICAgICAgICAgIF9leGNoYW5nZXMucHVzaChhY3Rpb24uZXhjaGFuZ2UpO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkZBSUxfUkVRVUVTVDpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9SRVNQT05TRTpcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBjb25zb2xlU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4vcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIFN0b3JlID0gcmVxdWlyZSgnLi4vbGliL3N0b3JlJyk7XG5cbnZhciBfbGFzdEVycm9yID0gbnVsbDtcblxudmFyIGxvZ2luRm9ybVN0b3JlID0gbmV3IFN0b3JlKCk7XG5cbmxvZ2luRm9ybVN0b3JlLmdldExhc3RFcnJvciA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2xhc3RFcnJvcjtcbn07XG5cbmxvZ2luRm9ybVN0b3JlLmRpc3BhdGNoVG9rZW4gPSBkaXNwYXRjaGVyLnJlZ2lzdGVyKGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBkaXNwYXRjaGVyLndhaXRGb3IoW3BsYXRmb3JtTWFuYWdlclN0b3JlLmRpc3BhdGNoVG9rZW5dKTtcblxuICAgIHN3aXRjaCAoYWN0aW9uLnR5cGUpIHtcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2xhc3RFcnJvciA9IG51bGw7XG4gICAgICAgICAgICBsb2dpbkZvcm1TdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRDpcbiAgICAgICAgICAgIF9sYXN0RXJyb3IgPSBhY3Rpb24uZXJyb3I7XG4gICAgICAgICAgICBsb2dpbkZvcm1TdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBsb2dpbkZvcm1TdG9yZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIFN0b3JlID0gcmVxdWlyZSgnLi4vbGliL3N0b3JlJyk7XG5cbnZhciBfYXV0aG9yaXphdGlvbiA9IHNlc3Npb25TdG9yYWdlLmdldEl0ZW0oJ2F1dGhvcml6YXRpb24nKTtcbnZhciBfcGFnZSA9IGxvY2F0aW9uLmhhc2guc3Vic3RyKDEpO1xudmFyIF9wbGF0Zm9ybXMgPSBudWxsO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbiA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2F1dGhvcml6YXRpb247XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfcGFnZTtcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBsYXRmb3JtcyA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX3BsYXRmb3Jtcztcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmRpc3BhdGNoVG9rZW4gPSBkaXNwYXRjaGVyLnJlZ2lzdGVyKGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9hdXRob3JpemF0aW9uID0gYWN0aW9uLmF1dGhvcml6YXRpb247XG4gICAgICAgICAgICBzZXNzaW9uU3RvcmFnZS5zZXRJdGVtKCdhdXRob3JpemF0aW9uJywgX2F1dGhvcml6YXRpb24pO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQ6XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfYXV0aG9yaXphdGlvbiA9IG51bGw7XG4gICAgICAgICAgICBzZXNzaW9uU3RvcmFnZS5yZW1vdmVJdGVtKCdhdXRob3JpemF0aW9uJyk7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRTpcbiAgICAgICAgICAgIF9wYWdlID0gYWN0aW9uLnBhZ2U7XG4gICAgICAgICAgICBsb2NhdGlvbi5oYXNoID0gJyMnICsgYWN0aW9uLnBhZ2U7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUzpcbiAgICAgICAgICAgIF9wbGF0Zm9ybXMgPSBhY3Rpb24ucGxhdGZvcm1zO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STTpcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IHBsYXRmb3JtTWFuYWdlclN0b3JlO1xuIl19
