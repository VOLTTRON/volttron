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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYXBwLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzLmpzIiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvYWdlbnQtcm93LmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbXBvc2VyLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbnNvbGUuanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvY29udmVyc2F0aW9uLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2V4Y2hhbmdlLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2hvbWUuanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbG9nLW91dC1idXR0b24uanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbG9naW4tZm9ybS5qc3giLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9uYXZpZ2F0aW9uLmpzeCIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL3BsYXRmb3JtLW1hbmFnZXIuanN4IiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvZGlzcGF0Y2hlci9pbmRleC5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2Vycm9yLmpzIiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvZXhjaGFuZ2UuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvc3RvcmUuanMiLCIvaG9tZS9jcmFpZzgvZ2l0L3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9lcnJvci5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL2hvbWUvY3JhaWc4L2dpdC92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvcmVxdWVzdC5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvY29uc29sZS1zdG9yZS5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZS5qcyIsIi9ob21lL2NyYWlnOC9naXQvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZS5qcyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQTtBQ0FBLFlBQVksQ0FBQzs7QUFFYixJQUFJLEtBQUssR0FBRyxPQUFPLENBQUMsT0FBTyxDQUFDLENBQUM7O0FBRTdCLElBQUksZUFBZSxHQUFHLE9BQU8sQ0FBQywrQkFBK0IsQ0FBQyxDQUFDOztBQUUvRCxLQUFLLENBQUMsTUFBTTtJQUNSLG9CQUFDLGVBQWUsRUFBQSxJQUFBLENBQUcsQ0FBQTtJQUNuQixRQUFRLENBQUMsY0FBYyxDQUFDLEtBQUssQ0FBQztDQUNqQyxDQUFDOzs7O0FDVEYsWUFBWSxDQUFDOztBQUViLElBQUksWUFBWSxHQUFHLE9BQU8sQ0FBQywyQkFBMkIsQ0FBQyxDQUFDO0FBQ3hELElBQUksVUFBVSxHQUFHLE9BQU8sQ0FBQyxlQUFlLENBQUMs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QUFFLENBQUM7QUFDOUMsWUFBWSxNQUFNOztRQUVWLEtBQUssWUFBWSxDQUFDLG9CQUFvQixDQUFDO1FBQ3ZDLEtBQUssWUFBWSxDQUFDLG1CQUFtQjtZQUNqQyxjQUFjLEdBQUcsSUFBSSxDQUFDO1lBQ3RCLGNBQWMsQ0FBQyxVQUFVLENBQUMsZUFBZSxDQUFDLENBQUM7WUFDM0Msb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7QUFDOUMsWUFBWSxNQUFNOztRQUVWLEtBQUssWUFBWSxDQUFDLFdBQVc7WUFDekIsS0FBSyxHQUFHLE1BQU0sQ0FBQyxJQUFJLENBQUM7WUFDcEIsUUFBUSxDQUFDLElBQUksR0FBRyxHQUFHLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQztZQUNsQyxvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztBQUM5QyxZQUFZLE1BQU07O1FBRVYsS0FBSyxZQUFZLENBQUMsaUJBQWlCO1lBQy9CLFVBQVUsR0FBRyxNQUFNLENBQUMsU0FBUyxDQUFDO1lBQzlCLG9CQUFvQixDQUFDLFVBQVUsRUFBRSxDQUFDO0FBQzlDLFlBQVksTUFBTTs7UUFFVixLQUFLLFlBQVksQ0FBQyxnQkFBZ0I7WUFDOUIsb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDbEMsTUFBTTtLQUNiO0FBQ0wsQ0FBQyxDQUFDLENBQUM7O0FBRUgsTUFBTSxDQUFDLE9BQU8sR0FBRyxvQkFBb0IsQ0FBQyIsImZpbGUiOiJnZW5lcmF0ZWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlc0NvbnRlbnQiOlsiKGZ1bmN0aW9uIGUodCxuLHIpe2Z1bmN0aW9uIHMobyx1KXtpZighbltvXSl7aWYoIXRbb10pe3ZhciBhPXR5cGVvZiByZXF1aXJlPT1cImZ1bmN0aW9uXCImJnJlcXVpcmU7aWYoIXUmJmEpcmV0dXJuIGEobywhMCk7aWYoaSlyZXR1cm4gaShvLCEwKTt2YXIgZj1uZXcgRXJyb3IoXCJDYW5ub3QgZmluZCBtb2R1bGUgJ1wiK28rXCInXCIpO3Rocm93IGYuY29kZT1cIk1PRFVMRV9OT1RfRk9VTkRcIixmfXZhciBsPW5bb109e2V4cG9ydHM6e319O3Rbb11bMF0uY2FsbChsLmV4cG9ydHMsZnVuY3Rpb24oZSl7dmFyIG49dFtvXVsxXVtlXTtyZXR1cm4gcyhuP246ZSl9LGwsbC5leHBvcnRzLGUsdCxuLHIpfXJldHVybiBuW29dLmV4cG9ydHN9dmFyIGk9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtmb3IodmFyIG89MDtvPHIubGVuZ3RoO28rKylzKHJbb10pO3JldHVybiBzfSkiLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBQbGF0Zm9ybU1hbmFnZXIgPSByZXF1aXJlKCcuL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlcicpO1xuXG5SZWFjdC5yZW5kZXIoXG4gICAgPFBsYXRmb3JtTWFuYWdlciAvPixcbiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnYXBwJylcbik7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBScGNFeGNoYW5nZSA9IHJlcXVpcmUoJy4uL2xpYi9ycGMvZXhjaGFuZ2UnKTtcblxudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHtcbiAgICB0b2dnbGVDb25zb2xlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlRPR0dMRV9DT05TT0xFLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIHVwZGF0ZUNvbXBvc2VyVmFsdWU6IGZ1bmN0aW9uICh2YWx1ZSkge1xuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5VUERBVEVfQ09NUE9TRVJfVkFMVUUsXG4gICAgICAgICAgICB2YWx1ZTogdmFsdWUsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgbWFrZVJlcXVlc3Q6IGZ1bmN0aW9uIChvcHRzKSB7XG4gICAgICAgIG5ldyBScGNFeGNoYW5nZShvcHRzKS5wcm9taXNlLmNhdGNoKGZ1bmN0aW9uIGlnbm9yZSgpIHt9KTtcbiAgICB9XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IGNvbnNvbGVBY3Rpb25DcmVhdG9ycztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBycGMgPSByZXF1aXJlKCcuLi9saWIvcnBjJyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHtcbiAgICByZXF1ZXN0QXV0aG9yaXphdGlvbjogZnVuY3Rpb24gKHVzZXJuYW1lLCBwYXNzd29yZCkge1xuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ2dldF9hdXRob3JpemF0aW9uJyxcbiAgICAgICAgICAgIHBhcmFtczoge1xuICAgICAgICAgICAgICAgIHVzZXJuYW1lOiB1c2VybmFtZSxcbiAgICAgICAgICAgICAgICBwYXNzd29yZDogcGFzc3dvcmQsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocmVzdWx0KSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT04sXG4gICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IHJlc3VsdCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAuY2F0Y2gocnBjLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBpZiAoZXJyb3IuY29kZSAmJiBlcnJvci5jb2RlID09PSA0MDEpIHtcbiAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQsXG4gICAgICAgICAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgY2xlYXJBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT04sXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgZ29Ub1BhZ2U6IGZ1bmN0aW9uIChwYWdlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFLFxuICAgICAgICAgICAgcGFnZTogcGFnZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBsb2FkUGxhdGZvcm1zOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuXG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAnbGlzdF9wbGF0Zm9ybXMnLFxuICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHBsYXRmb3Jtcykge1xuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STVMsXG4gICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1zLFxuICAgICAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICAgICAgcGxhdGZvcm1zLmZvckVhY2goZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAncGxhdGZvcm1zLnV1aWQuJyArIHBsYXRmb3JtLnV1aWQgKyAnLmxpc3RfYWdlbnRzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgICAgICAgICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgICAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChhZ2VudHNMaXN0KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm0uYWdlbnRzID0gYWdlbnRzTGlzdDtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5zdGF0dXNfYWdlbnRzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChhZ2VudFN0YXR1c2VzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybS5hZ2VudHMuZm9yRWFjaChmdW5jdGlvbiAoYWdlbnQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAoIWFnZW50U3RhdHVzZXMuc29tZShmdW5jdGlvbiAoc3RhdHVzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChhZ2VudC51dWlkID09PSBzdGF0dXMudXVpZCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IGZhbHNlO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucHJvY2Vzc19pZCA9IHN0YXR1cy5wcm9jZXNzX2lkO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBzdGF0dXMucmV0dXJuX2NvZGU7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSkpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQuYWN0aW9uUGVuZGluZyA9IGZhbHNlO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhZ2VudC5wcm9jZXNzX2lkID0gbnVsbDtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBudWxsO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIC5jYXRjaChmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBpZiAoZXJyb3IuY29kZSAmJiBlcnJvci5jb2RlID09PSA0MDEpIHtcbiAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQsXG4gICAgICAgICAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgc3RhcnRBZ2VudDogZnVuY3Rpb24gKHBsYXRmb3JtLCBhZ2VudCkge1xuICAgICAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcblxuICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gdHJ1ZTtcblxuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICB9KTtcblxuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5zdGFydF9hZ2VudCcsXG4gICAgICAgICAgICBwYXJhbXM6IFthZ2VudC51dWlkXSxcbiAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgIH0pLnByb21pc2VcbiAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChzdGF0dXMpIHtcbiAgICAgICAgICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gZmFsc2U7XG4gICAgICAgICAgICAgICAgYWdlbnQucHJvY2Vzc19pZCA9IHN0YXR1cy5wcm9jZXNzX2lkO1xuICAgICAgICAgICAgICAgIGFnZW50LnJldHVybl9jb2RlID0gc3RhdHVzLnJldHVybl9jb2RlO1xuXG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybTogcGxhdGZvcm0sXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KTtcbiAgICB9LFxuICAgIHN0b3BBZ2VudDogZnVuY3Rpb24gKHBsYXRmb3JtLCBhZ2VudCkge1xuICAgICAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcblxuICAgICAgICBhZ2VudC5hY3Rpb25QZW5kaW5nID0gdHJ1ZTtcblxuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNLFxuICAgICAgICAgICAgcGxhdGZvcm06IHBsYXRmb3JtLFxuICAgICAgICB9KTtcblxuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5zdG9wX2FnZW50JyxcbiAgICAgICAgICAgIHBhcmFtczogW2FnZW50LnV1aWRdLFxuICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHN0YXR1cykge1xuICAgICAgICAgICAgICAgIGFnZW50LmFjdGlvblBlbmRpbmcgPSBmYWxzZTtcbiAgICAgICAgICAgICAgICBhZ2VudC5wcm9jZXNzX2lkID0gc3RhdHVzLnByb2Nlc3NfaWQ7XG4gICAgICAgICAgICAgICAgYWdlbnQucmV0dXJuX2NvZGUgPSBzdGF0dXMucmV0dXJuX2NvZGU7XG5cbiAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk0sXG4gICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtOiBwbGF0Zm9ybSxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG59O1xuXG53aW5kb3cub25oYXNoY2hhbmdlID0gZnVuY3Rpb24gKCkge1xuICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLmdvVG9QYWdlKGxvY2F0aW9uLmhhc2guc3Vic3RyKDEpKTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnM7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xuXG52YXIgQWdlbnRSb3cgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgX29uU3RvcDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5zdG9wQWdlbnQodGhpcy5wcm9wcy5wbGF0Zm9ybSwgdGhpcy5wcm9wcy5hZ2VudCk7XG4gICAgfSxcbiAgICBfb25TdGFydDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5zdGFydEFnZW50KHRoaXMucHJvcHMucGxhdGZvcm0sIHRoaXMucHJvcHMuYWdlbnQpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBhZ2VudCA9IHRoaXMucHJvcHMuYWdlbnQsIHN0YXR1cywgYWN0aW9uO1xuXG4gICAgICAgIGlmIChhZ2VudC5hY3Rpb25QZW5kaW5nID09PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgIHN0YXR1cyA9ICdSZXRyaWV2aW5nIHN0YXR1cy4uLic7XG4gICAgICAgIH0gZWxzZSBpZiAoYWdlbnQuYWN0aW9uUGVuZGluZykge1xuICAgICAgICAgICAgaWYgKGFnZW50LnByb2Nlc3NfaWQgPT09IG51bGwgfHwgYWdlbnQucmV0dXJuX2NvZGUgIT09IG51bGwpIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnU3RhcnRpbmcuLi4nO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0YXJ0XCIgZGlzYWJsZWQgLz5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnU3RvcHBpbmcuLi4nO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0b3BcIiBkaXNhYmxlZCAvPlxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBpZiAoYWdlbnQucHJvY2Vzc19pZCA9PT0gbnVsbCkge1xuICAgICAgICAgICAgICAgIHN0YXR1cyA9ICdOZXZlciBzdGFydGVkJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdGFydFwiIG9uQ2xpY2s9e3RoaXMuX29uU3RhcnR9IC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSBpZiAoYWdlbnQucmV0dXJuX2NvZGUgPT09IG51bGwpIHtcbiAgICAgICAgICAgICAgICBzdGF0dXMgPSAnUnVubmluZyAoUElEICcgKyBhZ2VudC5wcm9jZXNzX2lkICsgJyknO1xuICAgICAgICAgICAgICAgIGFjdGlvbiA9IChcbiAgICAgICAgICAgICAgICAgICAgPGlucHV0IGNsYXNzTmFtZT1cImJ1dHRvblwiIHR5cGU9XCJidXR0b25cIiB2YWx1ZT1cIlN0b3BcIiBvbkNsaWNrPXt0aGlzLl9vblN0b3B9IC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgc3RhdHVzID0gJ1N0b3BwZWQgKHJldHVybmVkICcgKyBhZ2VudC5yZXR1cm5fY29kZSArICcpJztcbiAgICAgICAgICAgICAgICBhY3Rpb24gPSAoXG4gICAgICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwiYnV0dG9uXCIgdmFsdWU9XCJTdGFydFwiIG9uQ2xpY2s9e3RoaXMuX29uU3RhcnR9IC8+XG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8dHI+XG4gICAgICAgICAgICAgICAgPHRkPnthZ2VudC5uYW1lfTwvdGQ+XG4gICAgICAgICAgICAgICAgPHRkPnthZ2VudC51dWlkfTwvdGQ+XG4gICAgICAgICAgICAgICAgPHRkPntzdGF0dXN9PC90ZD5cbiAgICAgICAgICAgICAgICA8dGQ+e2FjdGlvbn08L3RkPlxuICAgICAgICAgICAgPC90cj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gQWdlbnRSb3c7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBjb25zb2xlQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xuXG52YXIgQ29tcG9zZXIgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5yZXBsYWNlU3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uU2VuZENsaWNrOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy5tYWtlUmVxdWVzdChKU09OLnBhcnNlKHRoaXMuc3RhdGUuY29tcG9zZXJWYWx1ZSkpO1xuICAgIH0sXG4gICAgX29uVGV4dGFyZWFDaGFuZ2U6IGZ1bmN0aW9uIChlKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy51cGRhdGVDb21wb3NlclZhbHVlKGUudGFyZ2V0LnZhbHVlKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJjb21wb3NlclwiPlxuICAgICAgICAgICAgICAgIDx0ZXh0YXJlYVxuICAgICAgICAgICAgICAgICAgICBrZXk9e3RoaXMuc3RhdGUuY29tcG9zZXJJZH1cbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3RoaXMuX29uVGV4dGFyZWFDaGFuZ2V9XG4gICAgICAgICAgICAgICAgICAgIGRlZmF1bHRWYWx1ZT17dGhpcy5zdGF0ZS5jb21wb3NlclZhbHVlfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHJlZj1cInNlbmRcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9XCJTZW5kXCJcbiAgICAgICAgICAgICAgICAgICAgZGlzYWJsZWQ9eyF0aGlzLnN0YXRlLnZhbGlkfVxuICAgICAgICAgICAgICAgICAgICBvbkNsaWNrPXt0aGlzLl9vblNlbmRDbGlja31cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfSxcbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgdmFyIGNvbXBvc2VyVmFsdWUgPSBjb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJWYWx1ZSgpO1xuICAgIHZhciB2YWxpZCA9IHRydWU7XG5cbiAgICB0cnkge1xuICAgICAgICBKU09OLnBhcnNlKGNvbXBvc2VyVmFsdWUpO1xuICAgIH0gY2F0Y2ggKGV4KSB7XG4gICAgICAgIGlmIChleCBpbnN0YW5jZW9mIFN5bnRheEVycm9yKSB7XG4gICAgICAgICAgICB2YWxpZCA9IGZhbHNlO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgdGhyb3cgZXg7XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgICBjb21wb3NlcklkOiBjb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJJZCgpLFxuICAgICAgICBjb21wb3NlclZhbHVlOiBjb21wb3NlclZhbHVlLFxuICAgICAgICB2YWxpZDogdmFsaWQsXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBDb21wb3NlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIENvbXBvc2VyID0gcmVxdWlyZSgnLi9jb21wb3NlcicpO1xudmFyIENvbnZlcnNhdGlvbiA9IHJlcXVpcmUoJy4vY29udmVyc2F0aW9uJyk7XG5cbnZhciBDb25zb2xlID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJjb25zb2xlXCI+XG4gICAgICAgICAgICAgICAgPENvbnZlcnNhdGlvbiAvPlxuICAgICAgICAgICAgICAgIDxDb21wb3NlciAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gQ29uc29sZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyICQgPSByZXF1aXJlKCdqcXVlcnknKTtcbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBFeGNoYW5nZSA9IHJlcXVpcmUoJy4vZXhjaGFuZ2UnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xuXG52YXIgQ29udmVyc2F0aW9uID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciAkY29udmVyc2F0aW9uID0gJCh0aGlzLnJlZnMuY29udmVyc2F0aW9uLmdldERPTU5vZGUoKSk7XG5cbiAgICAgICAgaWYgKCRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykgPiAkY29udmVyc2F0aW9uLmhlaWdodCgpKSB7XG4gICAgICAgICAgICAkY29udmVyc2F0aW9uLnNjcm9sbFRvcCgkY29udmVyc2F0aW9uLnByb3AoJ3Njcm9sbEhlaWdodCcpKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnNvbGVTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBjb21wb25lbnREaWRVcGRhdGU6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyICRjb252ZXJzYXRpb24gPSAkKHRoaXMucmVmcy5jb252ZXJzYXRpb24uZ2V0RE9NTm9kZSgpKTtcblxuICAgICAgICAkY29udmVyc2F0aW9uLnN0b3AoKS5hbmltYXRlKHsgc2Nyb2xsVG9wOiAkY29udmVyc2F0aW9uLnByb3AoJ3Njcm9sbEhlaWdodCcpIH0sIDUwMCk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IHJlZj1cImNvbnZlcnNhdGlvblwiIGNsYXNzTmFtZT1cImNvbnZlcnNhdGlvblwiPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmV4Y2hhbmdlcy5tYXAoZnVuY3Rpb24gKGV4Y2hhbmdlLCBpbmRleCkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPEV4Y2hhbmdlIGtleT17aW5kZXh9IGV4Y2hhbmdlPXtleGNoYW5nZX0gLz5cbiAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHsgZXhjaGFuZ2VzOiBjb25zb2xlU3RvcmUuZ2V0RXhjaGFuZ2VzKCkgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBDb252ZXJzYXRpb247XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBFeGNoYW5nZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfZm9ybWF0VGltZTogZnVuY3Rpb24gKHRpbWUpIHtcbiAgICAgICAgdmFyIGQgPSBuZXcgRGF0ZSgpO1xuXG4gICAgICAgIGQuc2V0VGltZSh0aW1lKTtcblxuICAgICAgICByZXR1cm4gZC50b0xvY2FsZVN0cmluZygpO1xuICAgIH0sXG4gICAgX2Zvcm1hdE1lc3NhZ2U6IGZ1bmN0aW9uIChtZXNzYWdlKSB7XG4gICAgICAgIHJldHVybiBKU09OLnN0cmluZ2lmeShtZXNzYWdlLCBudWxsLCAnICAgICcpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBleGNoYW5nZSA9IHRoaXMucHJvcHMuZXhjaGFuZ2U7XG4gICAgICAgIHZhciBjbGFzc2VzID0gWydyZXNwb25zZSddO1xuICAgICAgICB2YXIgcmVzcG9uc2VUZXh0O1xuXG4gICAgICAgIGlmICghZXhjaGFuZ2UuY29tcGxldGVkKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1wZW5kaW5nJyk7XG4gICAgICAgICAgICByZXNwb25zZVRleHQgPSAnV2FpdGluZyBmb3IgcmVzcG9uc2UuLi4nO1xuICAgICAgICB9IGVsc2UgaWYgKGV4Y2hhbmdlLmVycm9yKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1lcnJvcicpO1xuICAgICAgICAgICAgcmVzcG9uc2VUZXh0ID0gZXhjaGFuZ2UuZXJyb3IubWVzc2FnZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGlmIChleGNoYW5nZS5yZXNwb25zZS5lcnJvcikge1xuICAgICAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncmVzcG9uc2UtLWVycm9yJyk7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9IHRoaXMuX2Zvcm1hdE1lc3NhZ2UoZXhjaGFuZ2UucmVzcG9uc2UpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXhjaGFuZ2VcIj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInJlcXVlc3RcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJ0aW1lXCI+e3RoaXMuX2Zvcm1hdFRpbWUoZXhjaGFuZ2UuaW5pdGlhdGVkKX08L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgPHByZT57dGhpcy5fZm9ybWF0TWVzc2FnZShleGNoYW5nZS5yZXF1ZXN0KX08L3ByZT5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT17Y2xhc3Nlcy5qb2luKCcgJyl9PlxuICAgICAgICAgICAgICAgICAgICB7ZXhjaGFuZ2UuY29tcGxldGVkICYmIDxkaXYgY2xhc3NOYW1lPVwidGltZVwiPnt0aGlzLl9mb3JtYXRUaW1lKGV4Y2hhbmdlLmNvbXBsZXRlZCl9PC9kaXY+fVxuICAgICAgICAgICAgICAgICAgICA8cHJlPntyZXNwb25zZVRleHR9PC9wcmU+XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBFeGNoYW5nZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIEFnZW50Um93ID0gcmVxdWlyZSgnLi9hZ2VudC1yb3cnKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcblxudmFyIEhvbWUgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgICAgICBzZXRUaW1lb3V0KHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLmxvYWRQbGF0Zm9ybXMpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBwbGF0Zm9ybXM7XG5cbiAgICAgICAgaWYgKCF0aGlzLnN0YXRlLnBsYXRmb3Jtcykge1xuICAgICAgICAgICAgcGxhdGZvcm1zID0gKFxuICAgICAgICAgICAgICAgIDxwPkxvYWRpbmcgcGxhdGZvcm1zLi4uPC9wPlxuICAgICAgICAgICAgKTtcbiAgICAgICAgfSBlbHNlIGlmICghdGhpcy5zdGF0ZS5wbGF0Zm9ybXMubGVuZ3RoKSB7XG4gICAgICAgICAgICBwbGF0Zm9ybXMgPSAoXG4gICAgICAgICAgICAgICAgPHA+Tm8gcGxhdGZvcm1zIGZvdW5kLjwvcD5cbiAgICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBwbGF0Zm9ybXMgPSB0aGlzLnN0YXRlLnBsYXRmb3Jtcy5tYXAoZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgdmFyIGFnZW50cztcblxuICAgICAgICAgICAgICAgIGlmICghcGxhdGZvcm0uYWdlbnRzKSB7XG4gICAgICAgICAgICAgICAgICAgIGFnZW50cyA9IChcbiAgICAgICAgICAgICAgICAgICAgICAgIDxwPkxvYWRpbmcgYWdlbnRzLi4uPC9wPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAoIXBsYXRmb3JtLmFnZW50cy5sZW5ndGgpIHtcbiAgICAgICAgICAgICAgICAgICAgYWdlbnRzID0gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPHA+Tm8gYWdlbnRzIGluc3RhbGxlZC48L3A+XG4gICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgYWdlbnRzID0gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPHRhYmxlPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aGVhZD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRyPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoPkFnZW50PC90aD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5VVUlEPC90aD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx0aD5TdGF0dXM8L3RoPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHRoPkFjdGlvbjwvdGg+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvdHI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC90aGVhZD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8dGJvZHk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtwbGF0Zm9ybS5hZ2VudHMubWFwKGZ1bmN0aW9uIChhZ2VudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8QWdlbnRSb3dcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAga2V5PXthZ2VudC51dWlkfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGF0Zm9ybT17cGxhdGZvcm19XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50PXthZ2VudH0gLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvdGJvZHk+XG4gICAgICAgICAgICAgICAgICAgICAgICA8L3RhYmxlPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwicGxhdGZvcm1cIiBrZXk9e3BsYXRmb3JtLnV1aWR9PlxuICAgICAgICAgICAgICAgICAgICAgICAgPGgyPntwbGF0Zm9ybS5uYW1lfSAoe3BsYXRmb3JtLnV1aWR9KTwvaDI+XG4gICAgICAgICAgICAgICAgICAgICAgICB7YWdlbnRzfVxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfSk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJob21lXCI+XG4gICAgICAgICAgICAgICAge3BsYXRmb3Jtc31cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH0sXG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7XG4gICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGxhdGZvcm1zKCksXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBIb21lO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcblxudmFyIExvZ091dEJ1dHRvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfb25DbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5jbGVhckF1dGhvcml6YXRpb24oKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGJ1dHRvbiBjbGFzc05hbWU9XCJidXR0b25cIiBvbkNsaWNrPXt0aGlzLl9vbkNsaWNrfT5Mb2cgb3V0PC9idXR0b24+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTG9nT3V0QnV0dG9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBsb2dpbkZvcm1TdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9sb2dpbi1mb3JtLXN0b3JlJyk7XG5cbnZhciBMb2dpbkZvcm0gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25TdG9yZXNDaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25TdG9yZXNDaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uU3RvcmVzQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uSW5wdXRDaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZSh7XG4gICAgICAgICAgICB1c2VybmFtZTogdGhpcy5yZWZzLnVzZXJuYW1lLmdldERPTU5vZGUoKS52YWx1ZSxcbiAgICAgICAgICAgIHBhc3N3b3JkOiB0aGlzLnJlZnMucGFzc3dvcmQuZ2V0RE9NTm9kZSgpLnZhbHVlLFxuICAgICAgICAgICAgZXJyb3I6IG51bGwsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgX29uU3VibWl0OiBmdW5jdGlvbiAoZSkge1xuICAgICAgICBlLnByZXZlbnREZWZhdWx0KCk7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLnJlcXVlc3RBdXRob3JpemF0aW9uKFxuICAgICAgICAgICAgdGhpcy5zdGF0ZS51c2VybmFtZSxcbiAgICAgICAgICAgIHRoaXMuc3RhdGUucGFzc3dvcmRcbiAgICAgICAgKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGZvcm0gY2xhc3NOYW1lPVwibG9naW4tZm9ybVwiIG9uU3VibWl0PXt0aGlzLl9vblN1Ym1pdH0+XG4gICAgICAgICAgICAgICAgPGgxPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9oMT5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwidXNlcm5hbWVcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwidGV4dFwiXG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiVXNlcm5hbWVcIlxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25JbnB1dENoYW5nZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICByZWY9XCJwYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJwYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiUGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25JbnB1dENoYW5nZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwic3VibWl0XCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9XCJMb2cgaW5cIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudXNlcm5hbWUgfHwgIXRoaXMuc3RhdGUucGFzc3dvcmR9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5lcnJvciA/IChcbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJlcnJvclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXJyb3IubWVzc2FnZX0gKHt0aGlzLnN0YXRlLmVycm9yLmNvZGV9KVxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICApIDogbnVsbCB9XG4gICAgICAgICAgICA8L2Zvcm0+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4geyBlcnJvcjogbG9naW5Gb3JtU3RvcmUuZ2V0TGFzdEVycm9yKCkgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBMb2dpbkZvcm07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBMb2dPdXRCdXR0b24gPSByZXF1aXJlKCcuL2xvZy1vdXQtYnV0dG9uJyk7XG5cbnZhciBOYXZpZ2F0aW9uID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJuYXZpZ2F0aW9uXCI+XG4gICAgICAgICAgICAgICAgPGgxPjxhIGhyZWY9XCIjaG9tZVwiPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9hPjwvaDE+XG4gICAgICAgICAgICAgICAgPExvZ091dEJ1dHRvbiAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTmF2aWdhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIENvbnNvbGUgPSByZXF1aXJlKCcuL2NvbnNvbGUnKTtcbnZhciBjb25zb2xlQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xudmFyIEhvbWUgPSByZXF1aXJlKCcuL2hvbWUnKTtcbnZhciBMb2dpbkZvcm0gPSByZXF1aXJlKCcuL2xvZ2luLWZvcm0nKTtcbnZhciBOYXZpZ2F0aW9uID0gcmVxdWlyZSgnLi9uYXZpZ2F0aW9uJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgUGxhdGZvcm1NYW5hZ2VyID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIF9vbkJ1dHRvbkNsaWNrOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy50b2dnbGVDb25zb2xlKCk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGNsYXNzZXMgPSBbJ3BsYXRmb3JtLW1hbmFnZXInXTtcblxuICAgICAgICBpZiAoIXRoaXMuc3RhdGUuY29uc29sZVNob3duKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3BsYXRmb3JtLW1hbmFnZXItLWNvbnNvbGUtaGlkZGVuJyk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9e2NsYXNzZXMuam9pbignICcpfT5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIm1haW5cIj5cbiAgICAgICAgICAgICAgICAgICAgeyF0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxMb2dpbkZvcm0gLz59XG4gICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxOYXZpZ2F0aW9uIC8+fVxuICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8SG9tZSAvPn1cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwidG9nZ2xlIGJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT17J0NvbnNvbGUgJyArICh0aGlzLnN0YXRlLmNvbnNvbGVTaG93biA/ICdcXHUyNWJjJyA6ICdcXHUyNWIyJyl9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uQnV0dG9uQ2xpY2t9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5jb25zb2xlU2hvd24gJiYgPENvbnNvbGUgY2xhc3NOYW1lPVwiY29uc29sZVwiIC8+fVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4ge1xuICAgICAgICBjb25zb2xlU2hvd246IGNvbnNvbGVTdG9yZS5nZXRDb25zb2xlU2hvd24oKSxcbiAgICAgICAgbG9nZ2VkSW46ICEhcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpLFxuICAgIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gUGxhdGZvcm1NYW5hZ2VyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIga2V5TWlycm9yID0gcmVxdWlyZSgncmVhY3QvbGliL2tleU1pcnJvcicpO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGtleU1pcnJvcih7XG4gICAgVE9HR0xFX0NPTlNPTEU6IG51bGwsXG5cbiAgICBVUERBVEVfQ09NUE9TRVJfVkFMVUU6IG51bGwsXG5cbiAgICBNQUtFX1JFUVVFU1Q6IG51bGwsXG4gICAgRkFJTF9SRVFVRVNUOiBudWxsLFxuICAgIFJFQ0VJVkVfUkVTUE9OU0U6IG51bGwsXG5cbiAgICBSRUNFSVZFX0FVVEhPUklaQVRJT046IG51bGwsXG4gICAgUkVDRUlWRV9VTkFVVEhPUklaRUQ6IG51bGwsXG4gICAgQ0xFQVJfQVVUSE9SSVpBVElPTjogbnVsbCxcblxuICAgIENIQU5HRV9QQUdFOiBudWxsLFxuXG4gICAgUkVDRUlWRV9QTEFURk9STVM6IG51bGwsXG4gICAgUkVDRUlWRV9QTEFURk9STTogbnVsbCxcbn0pO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgRGlzcGF0Y2hlciA9IHJlcXVpcmUoJ2ZsdXgnKS5EaXNwYXRjaGVyO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xuXG52YXIgZGlzcGF0Y2hlciA9IG5ldyBEaXNwYXRjaGVyKCk7XG5cbmRpc3BhdGNoZXIuZGlzcGF0Y2ggPSBmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgaWYgKGFjdGlvbi50eXBlIGluIEFDVElPTl9UWVBFUykge1xuICAgICAgICByZXR1cm4gT2JqZWN0LmdldFByb3RvdHlwZU9mKHRoaXMpLmRpc3BhdGNoLmNhbGwodGhpcywgYWN0aW9uKTtcbiAgICB9XG5cbiAgICB0aHJvdyAnRGlzcGF0Y2ggZXJyb3I6IGludmFsaWQgYWN0aW9uIHR5cGUgJyArIGFjdGlvbi50eXBlO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBkaXNwYXRjaGVyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5mdW5jdGlvbiBScGNFcnJvcihlcnJvcikge1xuICAgIHRoaXMubmFtZSA9ICdScGNFcnJvcic7XG4gICAgdGhpcy5jb2RlID0gZXJyb3IuY29kZTtcbiAgICB0aGlzLm1lc3NhZ2UgPSBlcnJvci5tZXNzYWdlO1xuICAgIHRoaXMuZGF0YSA9IGVycm9yLmRhdGE7XG59XG5ScGNFcnJvci5wcm90b3R5cGUgPSBPYmplY3QuY3JlYXRlKEVycm9yLnByb3RvdHlwZSk7XG5ScGNFcnJvci5wcm90b3R5cGUuY29uc3RydWN0b3IgPSBScGNFcnJvcjtcblxubW9kdWxlLmV4cG9ydHMgPSBScGNFcnJvcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIHV1aWQgPSByZXF1aXJlKCdub2RlLXV1aWQnKTtcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uLy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vLi4vZGlzcGF0Y2hlcicpO1xudmFyIFJwY0Vycm9yID0gcmVxdWlyZSgnLi9lcnJvcicpO1xudmFyIHhociA9IHJlcXVpcmUoJy4uL3hocicpO1xuXG5mdW5jdGlvbiBScGNFeGNoYW5nZShvcHRzKSB7XG4gICAgaWYgKCF0aGlzIGluc3RhbmNlb2YgUnBjRXhjaGFuZ2UpIHtcbiAgICAgICAgcmV0dXJuIG5ldyBScGNFeGNoYW5nZShvcHRzKTtcbiAgICB9XG5cbiAgICB2YXIgZXhjaGFuZ2UgPSB0aGlzO1xuXG4gICAgLy8gVE9ETzogdmFsaWRhdGUgb3B0c1xuICAgIG9wdHMuanNvbnJwYyA9ICcyLjAnO1xuICAgIG9wdHMuaWQgPSB1dWlkLnYxKCk7XG5cbiAgICBleGNoYW5nZS5pbml0aWF0ZWQgPSBEYXRlLm5vdygpO1xuICAgIGV4Y2hhbmdlLnJlcXVlc3QgPSBvcHRzO1xuXG4gICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5NQUtFX1JFUVVFU1QsXG4gICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgcmVxdWVzdDogZXhjaGFuZ2UucmVxdWVzdCxcbiAgICB9KTtcblxuICAgIGV4Y2hhbmdlLnByb21pc2UgPSBuZXcgeGhyLlJlcXVlc3Qoe1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgdXJsOiAnL2pzb25ycGMnLFxuICAgICAgICBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBkYXRhOiBKU09OLnN0cmluZ2lmeShleGNoYW5nZS5yZXF1ZXN0KSxcbiAgICAgICAgdGltZW91dDogNjAwMDAsXG4gICAgfSlcbiAgICAgICAgLmZpbmFsbHkoZnVuY3Rpb24gKCkge1xuICAgICAgICAgICAgZXhjaGFuZ2UuY29tcGxldGVkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgfSlcbiAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHJlc3BvbnNlKSB7XG4gICAgICAgICAgICBleGNoYW5nZS5yZXNwb25zZSA9IHJlc3BvbnNlO1xuXG4gICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9SRVNQT05TRSxcbiAgICAgICAgICAgICAgICBleGNoYW5nZTogZXhjaGFuZ2UsXG4gICAgICAgICAgICAgICAgcmVzcG9uc2U6IHJlc3BvbnNlLFxuICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgIGlmIChyZXNwb25zZS5lcnJvcikge1xuICAgICAgICAgICAgICAgIHRocm93IG5ldyBScGNFcnJvcihyZXNwb25zZS5lcnJvcik7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJldHVybiByZXNwb25zZS5yZXN1bHQ7XG4gICAgICAgIH0pXG4gICAgICAgIC5jYXRjaCh4aHIuRXJyb3IsIGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgZXhjaGFuZ2UuZXJyb3IgPSBlcnJvcjtcblxuICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkZBSUxfUkVRVUVTVCxcbiAgICAgICAgICAgICAgICBleGNoYW5nZTogZXhjaGFuZ2UsXG4gICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLFxuICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICB9KTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBScGNFeGNoYW5nZTtcbiIsIid1c2Ugc3RyaWN0JztcblxubW9kdWxlLmV4cG9ydHMgPSB7XG4gICAgRXJyb3I6IHJlcXVpcmUoJy4vZXJyb3InKSxcbiAgICBFeGNoYW5nZTogcmVxdWlyZSgnLi9leGNoYW5nZScpLFxufTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEV2ZW50RW1pdHRlciA9IHJlcXVpcmUoJ2V2ZW50cycpLkV2ZW50RW1pdHRlcjtcblxudmFyIENIQU5HRV9FVkVOVCA9ICdjaGFuZ2UnO1xuXG5mdW5jdGlvbiBTdG9yZSgpIHtcbiAgICBFdmVudEVtaXR0ZXIuY2FsbCh0aGlzKTtcbn1cblN0b3JlLnByb3RvdHlwZSA9IEV2ZW50RW1pdHRlci5wcm90b3R5cGU7XG5cblN0b3JlLnByb3RvdHlwZS5lbWl0Q2hhbmdlID0gZnVuY3Rpb24oKSB7XG4gICAgdGhpcy5lbWl0KENIQU5HRV9FVkVOVCk7XG59O1xuXG5TdG9yZS5wcm90b3R5cGUuYWRkQ2hhbmdlTGlzdGVuZXIgPSBmdW5jdGlvbiAoY2FsbGJhY2spIHtcbiAgICB0aGlzLm9uKENIQU5HRV9FVkVOVCwgY2FsbGJhY2spO1xufTtcblxuU3RvcmUucHJvdG90eXBlLnJlbW92ZUNoYW5nZUxpc3RlbmVyID0gZnVuY3Rpb24gKGNhbGxiYWNrKSB7XG4gICAgdGhpcy5yZW1vdmVMaXN0ZW5lcihDSEFOR0VfRVZFTlQsIGNhbGxiYWNrKTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbmZ1bmN0aW9uIFhockVycm9yKG1lc3NhZ2UsIHJlc3BvbnNlKSB7XG4gICAgdGhpcy5uYW1lID0gJ1hockVycm9yJztcbiAgICB0aGlzLm1lc3NhZ2UgPSBtZXNzYWdlO1xuICAgIHRoaXMucmVzcG9uc2UgPSByZXNwb25zZTtcbn1cblhockVycm9yLnByb3RvdHlwZSA9IE9iamVjdC5jcmVhdGUoRXJyb3IucHJvdG90eXBlKTtcblhockVycm9yLnByb3RvdHlwZS5jb25zdHJ1Y3RvciA9IFhockVycm9yO1xuXG5tb2R1bGUuZXhwb3J0cyA9IFhockVycm9yO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5tb2R1bGUuZXhwb3J0cyA9IHtcbiAgICBSZXF1ZXN0OiByZXF1aXJlKCcuL3JlcXVlc3QnKSxcbiAgICBFcnJvcjogcmVxdWlyZSgnLi9lcnJvcicpLFxufTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIGpRdWVyeSA9IHJlcXVpcmUoJ2pxdWVyeScpO1xudmFyIFByb21pc2UgPSByZXF1aXJlKCdibHVlYmlyZCcpO1xuXG52YXIgWGhyRXJyb3IgPSByZXF1aXJlKCcuL2Vycm9yJyk7XG5cbmZ1bmN0aW9uIFhoclJlcXVlc3Qob3B0cykge1xuICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbiAocmVzb2x2ZSwgcmVqZWN0KSB7XG4gICAgICAgIG9wdHMuc3VjY2VzcyA9IHJlc29sdmU7XG4gICAgICAgIG9wdHMuZXJyb3IgPSBmdW5jdGlvbiAocmVzcG9uc2UsIHR5cGUpIHtcbiAgICAgICAgICAgIHN3aXRjaCAodHlwZSkge1xuICAgICAgICAgICAgY2FzZSAnZXJyb3InOlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1NlcnZlciByZXR1cm5lZCAnICsgcmVzcG9uc2Uuc3RhdHVzICsgJyBzdGF0dXMnLCByZXNwb25zZSkpO1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgY2FzZSAndGltZW91dCc6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignUmVxdWVzdCB0aW1lZCBvdXQnLCByZXNwb25zZSkpO1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdSZXF1ZXN0IGZhaWxlZDogJyArIHR5cGUsIHJlc3BvbnNlKSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH07XG5cbiAgICAgICAgalF1ZXJ5LmFqYXgob3B0cyk7XG4gICAgfSk7XG59XG5cbm1vZHVsZS5leHBvcnRzID0gWGhyUmVxdWVzdDtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbnZhciBfY29tcG9zZXJWYWx1ZSA9ICcnO1xudmFyIF9jb25zb2xlU2hvd24gPSBmYWxzZTtcbnZhciBfZXhjaGFuZ2VzID0gW107XG5cbnZhciBjb25zb2xlU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxuY29uc29sZVN0b3JlLmdldENvbXBvc2VySWQgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9jb21wb3NlcklkO1xufTtcblxuY29uc29sZVN0b3JlLmdldENvbXBvc2VyVmFsdWUgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9jb21wb3NlclZhbHVlO1xufTtcblxuY29uc29sZVN0b3JlLmdldENvbnNvbGVTaG93biA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2NvbnNvbGVTaG93bjtcbn07XG5cbmNvbnNvbGVTdG9yZS5nZXRFeGNoYW5nZXMgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9leGNoYW5nZXM7XG59O1xuXG5mdW5jdGlvbiBfcmVzZXRDb21wb3NlclZhbHVlKHVwZGF0ZU1ldGhvZCkge1xuICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuICAgIHZhciBwYXJzZWQ7XG5cbiAgICB0cnkge1xuICAgICAgICBwYXJzZWQgPSBKU09OLnBhcnNlKF9jb21wb3NlclZhbHVlKTtcblxuICAgICAgICBpZiAodXBkYXRlTWV0aG9kKSB7XG4gICAgICAgICAgICBwYXJzZWQubWV0aG9kID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGFnZSgpO1xuICAgICAgICB9XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBwYXJzZWQgPSB7IG1ldGhvZDogcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGFnZSgpIH07XG4gICAgfVxuXG4gICAgaWYgKGF1dGhvcml6YXRpb24pIHtcbiAgICAgICAgcGFyc2VkLmF1dGhvcml6YXRpb24gPSBhdXRob3JpemF0aW9uO1xuICAgIH0gZWxzZSB7XG4gICAgICAgIGRlbGV0ZSBwYXJzZWQuYXV0aG9yaXphdGlvbjtcbiAgICB9XG5cbiAgICBfY29tcG9zZXJWYWx1ZSA9IEpTT04uc3RyaW5naWZ5KHBhcnNlZCwgbnVsbCwgJyAgICAnKTtcbn1cblxuX3Jlc2V0Q29tcG9zZXJWYWx1ZSgpO1xuXG5jb25zb2xlU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGRpc3BhdGNoZXIud2FpdEZvcihbcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbl0pO1xuXG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5UT0dHTEVfQ09OU09MRTpcbiAgICAgICAgICAgIF9jb25zb2xlU2hvd24gPSAhX2NvbnNvbGVTaG93bjtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5VUERBVEVfQ09NUE9TRVJfVkFMVUU6XG4gICAgICAgICAgICBfY29tcG9zZXJWYWx1ZSA9IGFjdGlvbi52YWx1ZTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DTEVBUl9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2NvbXBvc2VySWQgPSBEYXRlLm5vdygpO1xuICAgICAgICAgICAgX3Jlc2V0Q29tcG9zZXJWYWx1ZSgpO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFOlxuICAgICAgICAgICAgX2NvbXBvc2VySWQgPSBEYXRlLm5vdygpO1xuICAgICAgICAgICAgX3Jlc2V0Q29tcG9zZXJWYWx1ZSh0cnVlKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5NQUtFX1JFUVVFU1Q6XG4gICAgICAgICAgICBfZXhjaGFuZ2VzLnB1c2goYWN0aW9uLmV4Y2hhbmdlKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5GQUlMX1JFUVVFU1Q6XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUkVTUE9OU0U6XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gY29uc29sZVN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2xhc3RFcnJvciA9IG51bGw7XG5cbnZhciBsb2dpbkZvcm1TdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5sb2dpbkZvcm1TdG9yZS5nZXRMYXN0RXJyb3IgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9sYXN0RXJyb3I7XG59O1xuXG5sb2dpbkZvcm1TdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgZGlzcGF0Y2hlci53YWl0Rm9yKFtwbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuXSk7XG5cbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9sYXN0RXJyb3IgPSBudWxsO1xuICAgICAgICAgICAgbG9naW5Gb3JtU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQ6XG4gICAgICAgICAgICBfbGFzdEVycm9yID0gYWN0aW9uLmVycm9yO1xuICAgICAgICAgICAgbG9naW5Gb3JtU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gbG9naW5Gb3JtU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2F1dGhvcml6YXRpb24gPSBzZXNzaW9uU3RvcmFnZS5nZXRJdGVtKCdhdXRob3JpemF0aW9uJyk7XG52YXIgX3BhZ2UgPSBsb2NhdGlvbi5oYXNoLnN1YnN0cigxKTtcbnZhciBfcGxhdGZvcm1zID0gbnVsbDtcblxudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gbmV3IFN0b3JlKCk7XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24gPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9hdXRob3JpemF0aW9uO1xufTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGFnZSA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX3BhZ2U7XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQbGF0Zm9ybXMgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9wbGF0Zm9ybXM7XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfYXV0aG9yaXphdGlvbiA9IGFjdGlvbi5hdXRob3JpemF0aW9uO1xuICAgICAgICAgICAgc2Vzc2lvblN0b3JhZ2Uuc2V0SXRlbSgnYXV0aG9yaXphdGlvbicsIF9hdXRob3JpemF0aW9uKTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DTEVBUl9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2F1dGhvcml6YXRpb24gPSBudWxsO1xuICAgICAgICAgICAgc2Vzc2lvblN0b3JhZ2UucmVtb3ZlSXRlbSgnYXV0aG9yaXphdGlvbicpO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0hBTkdFX1BBR0U6XG4gICAgICAgICAgICBfcGFnZSA9IGFjdGlvbi5wYWdlO1xuICAgICAgICAgICAgbG9jYXRpb24uaGFzaCA9ICcjJyArIGFjdGlvbi5wYWdlO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STVM6XG4gICAgICAgICAgICBfcGxhdGZvcm1zID0gYWN0aW9uLnBsYXRmb3JtcztcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk06XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZTtcbiJdfQ==
