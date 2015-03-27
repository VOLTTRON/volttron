(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');

var PlatformManager = require('./components/platform-manager');

React.render(
    React.createElement(PlatformManager, null),
    document.getElementById('app')
);


},{"./components/platform-manager":12,"react":undefined}],2:[function(require,module,exports){
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


},{"../constants/action-types":13,"../dispatcher":14,"../lib/rpc/exchange":16}],3:[function(require,module,exports){
'use strict';

var Promise = require('bluebird');

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    requestAuthorization: function (username, password) {
        new rpc.Exchange({
            method: 'getAuthorization',
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
            method: 'listPlatforms',
            authorization: authorization,
        }).promise
            .then(function (platforms) {
                return Promise.all(platforms.map(function (platform) {
                    return new rpc.Exchange({
                        method: 'platforms.uuid.' + platform.uuid + '.listAgents',
                        authorization: authorization,
                    })
                        .then(function (agents) {
                            return Promise.all(agents.map(function (agent) {
                                return new rpc.Exchange({
                                    method: 'platforms.uuid.' + platform.uuid + '.agents.uuid.' + agent.uuid + '.listMethods',
                                    authorization: authorization,
                                })
                                    .then(function (methods) {
                                        agent.methods = methods;
                                        return agent;
                                    });
                                }));
                        })
                        .then(function (agents) {
                            platform.agents = agents;
                            return platform;
                        });
                }));
            })
            .then(function (platforms) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_PLATFORMS,
                    platforms: platforms,
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
};

window.onhashchange = function () {
    platformManagerActionCreators.goToPage(location.hash.substr(1));
};

module.exports = platformManagerActionCreators;


},{"../constants/action-types":13,"../dispatcher":14,"../lib/rpc":17,"../stores/platform-manager-store":24,"bluebird":undefined}],4:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../stores/console-store":22,"react":undefined}],5:[function(require,module,exports){
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


},{"./composer":4,"./conversation":6,"react":undefined}],6:[function(require,module,exports){
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


},{"../stores/console-store":22,"./exchange":7,"jquery":undefined,"react":undefined}],7:[function(require,module,exports){
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


},{"react":undefined}],8:[function(require,module,exports){
'use strict';

var React = require('react');

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
        return (
            React.createElement("div", {className: "home"}, 
                this.state.platforms.length ?
                React.createElement("ul", null, 
                    this.state.platforms.map(function (platform) {
                        return (
                            React.createElement("li", null, 
                                platform.platform, " (", platform.uuid, ")", 
                                React.createElement("ul", null, 
                                    platform.agents.map(function (agent) {
                                        return (
                                            React.createElement("li", null, 
                                                agent.agent, " (", agent.uuid, ")", 
                                                React.createElement("ul", null, 
                                                    agent.methods.map(function (method) {
                                                        var href = [
                                                            '#platforms',
                                                            'uuid',
                                                            platform.uuid,
                                                            'agents.uuid',
                                                            agent.uuid,
                                                            'methods',
                                                            method.method,
                                                        ].join('.');

                                                        return (
                                                            React.createElement("li", null, 
                                                                React.createElement("a", {href: href}, 
                                                                    method.method
                                                                )
                                                            )
                                                        );
                                                    })
                                                )
                                            )
                                        );
                                    })
                                )
                            )
                        );
                    })
                )
                :
                React.createElement("p", null, "No platforms found.")
                
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/platform-manager-store":24,"react":undefined}],9:[function(require,module,exports){
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


},{"../action-creators/platform-manager-action-creators":3,"react":undefined}],10:[function(require,module,exports){
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/login-form-store":23,"react":undefined}],11:[function(require,module,exports){
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


},{"./log-out-button":9,"react":undefined}],12:[function(require,module,exports){
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


},{"../action-creators/console-action-creators":2,"../stores/console-store":22,"../stores/platform-manager-store":24,"./console":5,"./home":8,"./login-form":10,"./navigation":11,"react":undefined}],13:[function(require,module,exports){
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
});


},{"react/lib/keyMirror":undefined}],14:[function(require,module,exports){
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


},{"../constants/action-types":13,"flux":undefined}],15:[function(require,module,exports){
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


},{}],16:[function(require,module,exports){
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


},{"../../constants/action-types":13,"../../dispatcher":14,"../xhr":20,"./error":15,"node-uuid":undefined}],17:[function(require,module,exports){
'use strict';

module.exports = {
    Error: require('./error'),
    Exchange: require('./exchange'),
};


},{"./error":15,"./exchange":16}],18:[function(require,module,exports){
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


},{"events":undefined}],19:[function(require,module,exports){
'use strict';

function XhrError(message, response) {
    this.name = 'XhrError';
    this.message = message;
    this.response = response;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;


},{}],20:[function(require,module,exports){
'use strict';

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":19,"./request":21}],21:[function(require,module,exports){
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


},{"./error":19,"bluebird":undefined,"jquery":undefined}],22:[function(require,module,exports){
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


},{"../constants/action-types":13,"../dispatcher":14,"../lib/store":18,"./platform-manager-store":24}],23:[function(require,module,exports){
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


},{"../constants/action-types":13,"../dispatcher":14,"../lib/store":18,"./platform-manager-store":24}],24:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _authorization = sessionStorage.getItem('authorization');
var _page = location.hash.substr(1);
var _platforms = [];

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
    }
});

module.exports = platformManagerStore;


},{"../constants/action-types":13,"../dispatcher":14,"../lib/store":18}]},{},[1])
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hcHAuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb21wb3Nlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbnNvbGUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb252ZXJzYXRpb24uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9leGNoYW5nZS5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2hvbWUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9sb2ctb3V0LWJ1dHRvbi5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2xvZ2luLWZvcm0uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9uYXZpZ2F0aW9uLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb25zdGFudHMvYWN0aW9uLXR5cGVzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvZGlzcGF0Y2hlci9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2V4Y2hhbmdlLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9yZXF1ZXN0LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvc3RvcmVzL2NvbnNvbGUtc3RvcmUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlLmpzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBO0FDQUEsWUFBWSxDQUFDOztBQUViLElBQUksS0FBSyxHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUMsQ0FBQzs7QUFFN0IsSUFBSSxlQUFlLEdBQUcsT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUM7O0FBRS9ELEtBQUssQ0FBQyxNQUFNO0lBQ1Isb0JBQUMsZUFBZSxFQUFBLElBQUEsQ0FBRyxDQUFBO0lBQ25CLFFBQVEsQ0FBQyxjQUFjLENBQUMsS0FBSyxDQUFDO0NBQ2pDLENBQUM7Ozs7QUNU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ZUFBZSxFQUFFLGNBQWMsQ0FBQyxDQUFDO1lBQ3hELG9CQUFvQixDQUFDLFVBQVUsRUFBRSxDQUFDO0FBQzlDLFlBQVksTUFBTTs7UUFFVixLQUFLLFlBQVksQ0FBQyxvQkFBb0IsQ0FBQztRQUN2QyxLQUFLLFlBQVksQ0FBQyxtQkFBbUI7WUFDakMsY0FBYyxHQUFHLElBQUksQ0FBQztZQUN0QixjQUFjLENBQUMsVUFBVSxDQUFDLGVBQWUsQ0FBQyxDQUFDO1lBQzNDLG9CQUFvQixDQUFDLFVBQVUsRUFBRSxDQUFDO0FBQzlDLFlBQVksTUFBTTs7UUFFVixLQUFLLFlBQVksQ0FBQyxXQUFXO1lBQ3pCLEtBQUssR0FBRyxNQUFNLENBQUMsSUFBSSxDQUFDO1lBQ3BCLFFBQVEsQ0FBQyxJQUFJLEdBQUcsR0FBRyxHQUFHLE1BQU0sQ0FBQyxJQUFJLENBQUM7WUFDbEMsb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7QUFDOUMsWUFBWSxNQUFNOztRQUVWLEtBQUssWUFBWSxDQUFDLGlCQUFpQjtZQUMvQixVQUFVLEdBQUcsTUFBTSxDQUFDLFNBQVMsQ0FBQztZQUM5QixvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztZQUNsQyxNQUFNO0tBQ2I7QUFDTCxDQUFDLENBQUMsQ0FBQzs7QUFFSCxNQUFNLENBQUMsT0FBTyxHQUFHLG9CQUFvQixDQUFDIiwiZmlsZSI6ImdlbmVyYXRlZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzQ29udGVudCI6WyIoZnVuY3Rpb24gZSh0LG4scil7ZnVuY3Rpb24gcyhvLHUpe2lmKCFuW29dKXtpZighdFtvXSl7dmFyIGE9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtpZighdSYmYSlyZXR1cm4gYShvLCEwKTtpZihpKXJldHVybiBpKG8sITApO3ZhciBmPW5ldyBFcnJvcihcIkNhbm5vdCBmaW5kIG1vZHVsZSAnXCIrbytcIidcIik7dGhyb3cgZi5jb2RlPVwiTU9EVUxFX05PVF9GT1VORFwiLGZ9dmFyIGw9bltvXT17ZXhwb3J0czp7fX07dFtvXVswXS5jYWxsKGwuZXhwb3J0cyxmdW5jdGlvbihlKXt2YXIgbj10W29dWzFdW2VdO3JldHVybiBzKG4/bjplKX0sbCxsLmV4cG9ydHMsZSx0LG4scil9cmV0dXJuIG5bb10uZXhwb3J0c312YXIgaT10eXBlb2YgcmVxdWlyZT09XCJmdW5jdGlvblwiJiZyZXF1aXJlO2Zvcih2YXIgbz0wO288ci5sZW5ndGg7bysrKXMocltvXSk7cmV0dXJuIHN9KSIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIFBsYXRmb3JtTWFuYWdlciA9IHJlcXVpcmUoJy4vY29tcG9uZW50cy9wbGF0Zm9ybS1tYW5hZ2VyJyk7XG5cblJlYWN0LnJlbmRlcihcbiAgICA8UGxhdGZvcm1NYW5hZ2VyIC8+LFxuICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdhcHAnKVxuKTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIFJwY0V4Y2hhbmdlID0gcmVxdWlyZSgnLi4vbGliL3JwYy9leGNoYW5nZScpO1xuXG52YXIgY29uc29sZUFjdGlvbkNyZWF0b3JzID0ge1xuICAgIHRvZ2dsZUNvbnNvbGU6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuVE9HR0xFX0NPTlNPTEUsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgdXBkYXRlQ29tcG9zZXJWYWx1ZTogZnVuY3Rpb24gKHZhbHVlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlVQREFURV9DT01QT1NFUl9WQUxVRSxcbiAgICAgICAgICAgIHZhbHVlOiB2YWx1ZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBtYWtlUmVxdWVzdDogZnVuY3Rpb24gKG9wdHMpIHtcbiAgICAgICAgbmV3IFJwY0V4Y2hhbmdlKG9wdHMpLnByb21pc2UuY2F0Y2goZnVuY3Rpb24gaWdub3JlKCkge30pO1xuICAgIH1cbn07XG5cbm1vZHVsZS5leHBvcnRzID0gY29uc29sZUFjdGlvbkNyZWF0b3JzO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUHJvbWlzZSA9IHJlcXVpcmUoJ2JsdWViaXJkJyk7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgcnBjID0gcmVxdWlyZSgnLi4vbGliL3JwYycpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSB7XG4gICAgcmVxdWVzdEF1dGhvcml6YXRpb246IGZ1bmN0aW9uICh1c2VybmFtZSwgcGFzc3dvcmQpIHtcbiAgICAgICAgbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICBtZXRob2Q6ICdnZXRBdXRob3JpemF0aW9uJyxcbiAgICAgICAgICAgIHBhcmFtczoge1xuICAgICAgICAgICAgICAgIHVzZXJuYW1lOiB1c2VybmFtZSxcbiAgICAgICAgICAgICAgICBwYXNzd29yZDogcGFzc3dvcmQsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocmVzdWx0KSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT04sXG4gICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IHJlc3VsdCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAuY2F0Y2gocnBjLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBpZiAoZXJyb3IuY29kZSAmJiBlcnJvci5jb2RlID09PSA0MDEpIHtcbiAgICAgICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQsXG4gICAgICAgICAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHRocm93IGVycm9yO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgY2xlYXJBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT04sXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgZ29Ub1BhZ2U6IGZ1bmN0aW9uIChwYWdlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFLFxuICAgICAgICAgICAgcGFnZTogcGFnZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBsb2FkUGxhdGZvcm1zOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuXG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAnbGlzdFBsYXRmb3JtcycsXG4gICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocGxhdGZvcm1zKSB7XG4gICAgICAgICAgICAgICAgcmV0dXJuIFByb21pc2UuYWxsKHBsYXRmb3Jtcy5tYXAoZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5saXN0QWdlbnRzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgICAgICAudGhlbihmdW5jdGlvbiAoYWdlbnRzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIFByb21pc2UuYWxsKGFnZW50cy5tYXAoZnVuY3Rpb24gKGFnZW50KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZDogJ3BsYXRmb3Jtcy51dWlkLicgKyBwbGF0Zm9ybS51dWlkICsgJy5hZ2VudHMudXVpZC4nICsgYWdlbnQudXVpZCArICcubGlzdE1ldGhvZHMnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChtZXRob2RzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQubWV0aG9kcyA9IG1ldGhvZHM7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGFnZW50O1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pKTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgICAgICAudGhlbihmdW5jdGlvbiAoYWdlbnRzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm0uYWdlbnRzID0gYWdlbnRzO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBwbGF0Zm9ybTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0pKTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocGxhdGZvcm1zKSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUyxcbiAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm1zOiBwbGF0Zm9ybXMsXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgLmNhdGNoKGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgICAgIGlmIChlcnJvci5jb2RlICYmIGVycm9yLmNvZGUgPT09IDQwMSkge1xuICAgICAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSk7XG4gICAgfSxcbn07XG5cbndpbmRvdy5vbmhhc2hjaGFuZ2UgPSBmdW5jdGlvbiAoKSB7XG4gICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuZ29Ub1BhZ2UobG9jYXRpb24uaGFzaC5zdWJzdHIoMSkpO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9jb25zb2xlLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG5cbnZhciBDb21wb3NlciA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnJlcGxhY2VTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICBfb25TZW5kQ2xpY2s6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLm1ha2VSZXF1ZXN0KEpTT04ucGFyc2UodGhpcy5zdGF0ZS5jb21wb3NlclZhbHVlKSk7XG4gICAgfSxcbiAgICBfb25UZXh0YXJlYUNoYW5nZTogZnVuY3Rpb24gKGUpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLnVwZGF0ZUNvbXBvc2VyVmFsdWUoZS50YXJnZXQudmFsdWUpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImNvbXBvc2VyXCI+XG4gICAgICAgICAgICAgICAgPHRleHRhcmVhXG4gICAgICAgICAgICAgICAgICAgIGtleT17dGhpcy5zdGF0ZS5jb21wb3NlcklkfVxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25UZXh0YXJlYUNoYW5nZX1cbiAgICAgICAgICAgICAgICAgICAgZGVmYXVsdFZhbHVlPXt0aGlzLnN0YXRlLmNvbXBvc2VyVmFsdWV9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwic2VuZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT1cIlNlbmRcIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudmFsaWR9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uU2VuZENsaWNrfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICB2YXIgY29tcG9zZXJWYWx1ZSA9IGNvbnNvbGVTdG9yZS5nZXRDb21wb3NlclZhbHVlKCk7XG4gICAgdmFyIHZhbGlkID0gdHJ1ZTtcblxuICAgIHRyeSB7XG4gICAgICAgIEpTT04ucGFyc2UoY29tcG9zZXJWYWx1ZSk7XG4gICAgfSBjYXRjaCAoZXgpIHtcbiAgICAgICAgaWYgKGV4IGluc3RhbmNlb2YgU3ludGF4RXJyb3IpIHtcbiAgICAgICAgICAgIHZhbGlkID0gZmFsc2U7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICB0aHJvdyBleDtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIGNvbXBvc2VySWQ6IGNvbnNvbGVTdG9yZS5nZXRDb21wb3NlcklkKCksXG4gICAgICAgIGNvbXBvc2VyVmFsdWU6IGNvbXBvc2VyVmFsdWUsXG4gICAgICAgIHZhbGlkOiB2YWxpZCxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbXBvc2VyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgQ29tcG9zZXIgPSByZXF1aXJlKCcuL2NvbXBvc2VyJyk7XG52YXIgQ29udmVyc2F0aW9uID0gcmVxdWlyZSgnLi9jb252ZXJzYXRpb24nKTtcblxudmFyIENvbnNvbGUgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImNvbnNvbGVcIj5cbiAgICAgICAgICAgICAgICA8Q29udmVyc2F0aW9uIC8+XG4gICAgICAgICAgICAgICAgPENvbXBvc2VyIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBDb25zb2xlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgJCA9IHJlcXVpcmUoJ2pxdWVyeScpO1xudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIEV4Y2hhbmdlID0gcmVxdWlyZSgnLi9leGNoYW5nZScpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG5cbnZhciBDb252ZXJzYXRpb24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyICRjb252ZXJzYXRpb24gPSAkKHRoaXMucmVmcy5jb252ZXJzYXRpb24uZ2V0RE9NTm9kZSgpKTtcblxuICAgICAgICBpZiAoJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSA+ICRjb252ZXJzYXRpb24uaGVpZ2h0KCkpIHtcbiAgICAgICAgICAgICRjb252ZXJzYXRpb24uc2Nyb2xsVG9wKCRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudERpZFVwZGF0ZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgJGNvbnZlcnNhdGlvbiA9ICQodGhpcy5yZWZzLmNvbnZlcnNhdGlvbi5nZXRET01Ob2RlKCkpO1xuXG4gICAgICAgICRjb252ZXJzYXRpb24uc3RvcCgpLmFuaW1hdGUoeyBzY3JvbGxUb3A6ICRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykgfSwgNTAwKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgcmVmPVwiY29udmVyc2F0aW9uXCIgY2xhc3NOYW1lPVwiY29udmVyc2F0aW9uXCI+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXhjaGFuZ2VzLm1hcChmdW5jdGlvbiAoZXhjaGFuZ2UsIGluZGV4KSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8RXhjaGFuZ2Uga2V5PXtpbmRleH0gZXhjaGFuZ2U9e2V4Y2hhbmdlfSAvPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4geyBleGNoYW5nZXM6IGNvbnNvbGVTdG9yZS5nZXRFeGNoYW5nZXMoKSB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbnZlcnNhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBFeGNoYW5nZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfZm9ybWF0VGltZTogZnVuY3Rpb24gKHRpbWUpIHtcbiAgICAgICAgdmFyIGQgPSBuZXcgRGF0ZSgpO1xuXG4gICAgICAgIGQuc2V0VGltZSh0aW1lKTtcblxuICAgICAgICByZXR1cm4gZC50b0xvY2FsZVN0cmluZygpO1xuICAgIH0sXG4gICAgX2Zvcm1hdE1lc3NhZ2U6IGZ1bmN0aW9uIChtZXNzYWdlKSB7XG4gICAgICAgIHJldHVybiBKU09OLnN0cmluZ2lmeShtZXNzYWdlLCBudWxsLCAnICAgICcpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBleGNoYW5nZSA9IHRoaXMucHJvcHMuZXhjaGFuZ2U7XG4gICAgICAgIHZhciBjbGFzc2VzID0gWydyZXNwb25zZSddO1xuICAgICAgICB2YXIgcmVzcG9uc2VUZXh0O1xuXG4gICAgICAgIGlmICghZXhjaGFuZ2UuY29tcGxldGVkKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1wZW5kaW5nJyk7XG4gICAgICAgICAgICByZXNwb25zZVRleHQgPSAnV2FpdGluZyBmb3IgcmVzcG9uc2UuLi4nO1xuICAgICAgICB9IGVsc2UgaWYgKGV4Y2hhbmdlLmVycm9yKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1lcnJvcicpO1xuICAgICAgICAgICAgcmVzcG9uc2VUZXh0ID0gZXhjaGFuZ2UuZXJyb3IubWVzc2FnZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGlmIChleGNoYW5nZS5yZXNwb25zZS5lcnJvcikge1xuICAgICAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncmVzcG9uc2UtLWVycm9yJyk7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9IHRoaXMuX2Zvcm1hdE1lc3NhZ2UoZXhjaGFuZ2UucmVzcG9uc2UpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXhjaGFuZ2VcIj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInJlcXVlc3RcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJ0aW1lXCI+e3RoaXMuX2Zvcm1hdFRpbWUoZXhjaGFuZ2UuaW5pdGlhdGVkKX08L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgPHByZT57dGhpcy5fZm9ybWF0TWVzc2FnZShleGNoYW5nZS5yZXF1ZXN0KX08L3ByZT5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT17Y2xhc3Nlcy5qb2luKCcgJyl9PlxuICAgICAgICAgICAgICAgICAgICB7ZXhjaGFuZ2UuY29tcGxldGVkICYmIDxkaXYgY2xhc3NOYW1lPVwidGltZVwiPnt0aGlzLl9mb3JtYXRUaW1lKGV4Y2hhbmdlLmNvbXBsZXRlZCl9PC9kaXY+fVxuICAgICAgICAgICAgICAgICAgICA8cHJlPntyZXNwb25zZVRleHR9PC9wcmU+XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBFeGNoYW5nZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgSG9tZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIHNldFRpbWVvdXQocGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMubG9hZFBsYXRmb3Jtcyk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiaG9tZVwiPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLnBsYXRmb3Jtcy5sZW5ndGggP1xuICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUucGxhdGZvcm1zLm1hcChmdW5jdGlvbiAocGxhdGZvcm0pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPGxpPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cGxhdGZvcm0ucGxhdGZvcm19ICh7cGxhdGZvcm0udXVpZH0pXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtwbGF0Zm9ybS5hZ2VudHMubWFwKGZ1bmN0aW9uIChhZ2VudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxsaT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHthZ2VudC5hZ2VudH0gKHthZ2VudC51dWlkfSlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7YWdlbnQubWV0aG9kcy5tYXAoZnVuY3Rpb24gKG1ldGhvZCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB2YXIgaHJlZiA9IFtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICcjcGxhdGZvcm1zJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICd1dWlkJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtLnV1aWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAnYWdlbnRzLnV1aWQnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQudXVpZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICdtZXRob2RzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZC5tZXRob2QsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIF0uam9pbignLicpO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8bGk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGEgaHJlZj17aHJlZn0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHttZXRob2QubWV0aG9kfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvYT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvbGk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3VsPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2xpPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2xpPlxuICAgICAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICAgICAgICA6XG4gICAgICAgICAgICAgICAgPHA+Tm8gcGxhdGZvcm1zIGZvdW5kLjwvcD5cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4ge1xuICAgICAgICBwbGF0Zm9ybXM6IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBsYXRmb3JtcygpLFxuICAgIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gSG9tZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG5cbnZhciBMb2dPdXRCdXR0b24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgX29uQ2xpY2s6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuY2xlYXJBdXRob3JpemF0aW9uKCk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxidXR0b24gY2xhc3NOYW1lPVwiYnV0dG9uXCIgb25DbGljaz17dGhpcy5fb25DbGlja30+TG9nIG91dDwvYnV0dG9uPlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IExvZ091dEJ1dHRvbjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgbG9naW5Gb3JtU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZScpO1xuXG52YXIgTG9naW5Gb3JtID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGxvZ2luRm9ybVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uU3RvcmVzQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGxvZ2luRm9ybVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uU3RvcmVzQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vblN0b3Jlc0NoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIF9vbklucHV0Q2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoe1xuICAgICAgICAgICAgdXNlcm5hbWU6IHRoaXMucmVmcy51c2VybmFtZS5nZXRET01Ob2RlKCkudmFsdWUsXG4gICAgICAgICAgICBwYXNzd29yZDogdGhpcy5yZWZzLnBhc3N3b3JkLmdldERPTU5vZGUoKS52YWx1ZSxcbiAgICAgICAgICAgIGVycm9yOiBudWxsLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIF9vblN1Ym1pdDogZnVuY3Rpb24gKGUpIHtcbiAgICAgICAgZS5wcmV2ZW50RGVmYXVsdCgpO1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5yZXF1ZXN0QXV0aG9yaXphdGlvbihcbiAgICAgICAgICAgIHRoaXMuc3RhdGUudXNlcm5hbWUsXG4gICAgICAgICAgICB0aGlzLnN0YXRlLnBhc3N3b3JkXG4gICAgICAgICk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxmb3JtIGNsYXNzTmFtZT1cImxvZ2luLWZvcm1cIiBvblN1Ym1pdD17dGhpcy5fb25TdWJtaXR9PlxuICAgICAgICAgICAgICAgIDxoMT5WT0xUVFJPTihUTSkgUGxhdGZvcm0gTWFuYWdlcjwvaDE+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIHJlZj1cInVzZXJuYW1lXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cInRleHRcIlxuICAgICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlcj1cIlVzZXJuYW1lXCJcbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3RoaXMuX29uSW5wdXRDaGFuZ2V9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwicGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwicGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlcj1cIlBhc3N3b3JkXCJcbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3RoaXMuX29uSW5wdXRDaGFuZ2V9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdHlwZT1cInN1Ym1pdFwiXG4gICAgICAgICAgICAgICAgICAgIHZhbHVlPVwiTG9nIGluXCJcbiAgICAgICAgICAgICAgICAgICAgZGlzYWJsZWQ9eyF0aGlzLnN0YXRlLnVzZXJuYW1lIHx8ICF0aGlzLnN0YXRlLnBhc3N3b3JkfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXJyb3IgPyAoXG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXJyb3JcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmVycm9yLm1lc3NhZ2V9ICh7dGhpcy5zdGF0ZS5lcnJvci5jb2RlfSlcbiAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgKSA6IG51bGwgfVxuICAgICAgICAgICAgPC9mb3JtPlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHsgZXJyb3I6IGxvZ2luRm9ybVN0b3JlLmdldExhc3RFcnJvcigpIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gTG9naW5Gb3JtO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgTG9nT3V0QnV0dG9uID0gcmVxdWlyZSgnLi9sb2ctb3V0LWJ1dHRvbicpO1xuXG52YXIgTmF2aWdhdGlvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwibmF2aWdhdGlvblwiPlxuICAgICAgICAgICAgICAgIDxoMT48YSBocmVmPVwiI2hvbWVcIj5WT0xUVFJPTihUTSkgUGxhdGZvcm0gTWFuYWdlcjwvYT48L2gxPlxuICAgICAgICAgICAgICAgIDxMb2dPdXRCdXR0b24gLz5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IE5hdmlnYXRpb247XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBDb25zb2xlID0gcmVxdWlyZSgnLi9jb25zb2xlJyk7XG52YXIgY29uc29sZUFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgY29uc29sZVN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL2NvbnNvbGUtc3RvcmUnKTtcbnZhciBIb21lID0gcmVxdWlyZSgnLi9ob21lJyk7XG52YXIgTG9naW5Gb3JtID0gcmVxdWlyZSgnLi9sb2dpbi1mb3JtJyk7XG52YXIgTmF2aWdhdGlvbiA9IHJlcXVpcmUoJy4vbmF2aWdhdGlvbicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcblxudmFyIFBsYXRmb3JtTWFuYWdlciA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICBfb25CdXR0b25DbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlQWN0aW9uQ3JlYXRvcnMudG9nZ2xlQ29uc29sZSgpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBjbGFzc2VzID0gWydwbGF0Zm9ybS1tYW5hZ2VyJ107XG5cbiAgICAgICAgaWYgKCF0aGlzLnN0YXRlLmNvbnNvbGVTaG93bikge1xuICAgICAgICAgICAgY2xhc3Nlcy5wdXNoKCdwbGF0Zm9ybS1tYW5hZ2VyLS1jb25zb2xlLWhpZGRlbicpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPXtjbGFzc2VzLmpvaW4oJyAnKX0+XG4gICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJtYWluXCI+XG4gICAgICAgICAgICAgICAgICAgIHshdGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8TG9naW5Gb3JtIC8+fVxuICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8TmF2aWdhdGlvbiAvPn1cbiAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUubG9nZ2VkSW4gJiYgPEhvbWUgLz59XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cInRvZ2dsZSBidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9eydDb25zb2xlICcgKyAodGhpcy5zdGF0ZS5jb25zb2xlU2hvd24gPyAnXFx1MjViYycgOiAnXFx1MjViMicpfVxuICAgICAgICAgICAgICAgICAgICBvbkNsaWNrPXt0aGlzLl9vbkJ1dHRvbkNsaWNrfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuY29uc29sZVNob3duICYmIDxDb25zb2xlIGNsYXNzTmFtZT1cImNvbnNvbGVcIiAvPn1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgICAgY29uc29sZVNob3duOiBjb25zb2xlU3RvcmUuZ2V0Q29uc29sZVNob3duKCksXG4gICAgICAgIGxvZ2dlZEluOiAhIXBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKSxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFBsYXRmb3JtTWFuYWdlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIGtleU1pcnJvciA9IHJlcXVpcmUoJ3JlYWN0L2xpYi9rZXlNaXJyb3InKTtcblxubW9kdWxlLmV4cG9ydHMgPSBrZXlNaXJyb3Ioe1xuICAgIFRPR0dMRV9DT05TT0xFOiBudWxsLFxuXG4gICAgVVBEQVRFX0NPTVBPU0VSX1ZBTFVFOiBudWxsLFxuXG4gICAgTUFLRV9SRVFVRVNUOiBudWxsLFxuICAgIEZBSUxfUkVRVUVTVDogbnVsbCxcbiAgICBSRUNFSVZFX1JFU1BPTlNFOiBudWxsLFxuXG4gICAgUkVDRUlWRV9BVVRIT1JJWkFUSU9OOiBudWxsLFxuICAgIFJFQ0VJVkVfVU5BVVRIT1JJWkVEOiBudWxsLFxuICAgIENMRUFSX0FVVEhPUklaQVRJT046IG51bGwsXG5cbiAgICBDSEFOR0VfUEFHRTogbnVsbCxcblxuICAgIFJFQ0VJVkVfUExBVEZPUk1TOiBudWxsLFxufSk7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBEaXNwYXRjaGVyID0gcmVxdWlyZSgnZmx1eCcpLkRpc3BhdGNoZXI7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG5cbnZhciBkaXNwYXRjaGVyID0gbmV3IERpc3BhdGNoZXIoKTtcblxuZGlzcGF0Y2hlci5kaXNwYXRjaCA9IGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBpZiAoYWN0aW9uLnR5cGUgaW4gQUNUSU9OX1RZUEVTKSB7XG4gICAgICAgIHJldHVybiBPYmplY3QuZ2V0UHJvdG90eXBlT2YodGhpcykuZGlzcGF0Y2guY2FsbCh0aGlzLCBhY3Rpb24pO1xuICAgIH1cblxuICAgIHRocm93ICdEaXNwYXRjaCBlcnJvcjogaW52YWxpZCBhY3Rpb24gdHlwZSAnICsgYWN0aW9uLnR5cGU7XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IGRpc3BhdGNoZXI7XG4iLCIndXNlIHN0cmljdCc7XG5cbmZ1bmN0aW9uIFJwY0Vycm9yKGVycm9yKSB7XG4gICAgdGhpcy5uYW1lID0gJ1JwY0Vycm9yJztcbiAgICB0aGlzLmNvZGUgPSBlcnJvci5jb2RlO1xuICAgIHRoaXMubWVzc2FnZSA9IGVycm9yLm1lc3NhZ2U7XG4gICAgdGhpcy5kYXRhID0gZXJyb3IuZGF0YTtcbn1cblJwY0Vycm9yLnByb3RvdHlwZSA9IE9iamVjdC5jcmVhdGUoRXJyb3IucHJvdG90eXBlKTtcblJwY0Vycm9yLnByb3RvdHlwZS5jb25zdHJ1Y3RvciA9IFJwY0Vycm9yO1xuXG5tb2R1bGUuZXhwb3J0cyA9IFJwY0Vycm9yO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgdXVpZCA9IHJlcXVpcmUoJ25vZGUtdXVpZCcpO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi8uLi9kaXNwYXRjaGVyJyk7XG52YXIgUnBjRXJyb3IgPSByZXF1aXJlKCcuL2Vycm9yJyk7XG52YXIgeGhyID0gcmVxdWlyZSgnLi4veGhyJyk7XG5cbmZ1bmN0aW9uIFJwY0V4Y2hhbmdlKG9wdHMpIHtcbiAgICBpZiAoIXRoaXMgaW5zdGFuY2VvZiBScGNFeGNoYW5nZSkge1xuICAgICAgICByZXR1cm4gbmV3IFJwY0V4Y2hhbmdlKG9wdHMpO1xuICAgIH1cblxuICAgIHZhciBleGNoYW5nZSA9IHRoaXM7XG5cbiAgICAvLyBUT0RPOiB2YWxpZGF0ZSBvcHRzXG4gICAgb3B0cy5qc29ucnBjID0gJzIuMCc7XG4gICAgb3B0cy5pZCA9IHV1aWQudjEoKTtcblxuICAgIGV4Y2hhbmdlLmluaXRpYXRlZCA9IERhdGUubm93KCk7XG4gICAgZXhjaGFuZ2UucmVxdWVzdCA9IG9wdHM7XG5cbiAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLk1BS0VfUkVRVUVTVCxcbiAgICAgICAgZXhjaGFuZ2U6IGV4Y2hhbmdlLFxuICAgICAgICByZXF1ZXN0OiBleGNoYW5nZS5yZXF1ZXN0LFxuICAgIH0pO1xuXG4gICAgZXhjaGFuZ2UucHJvbWlzZSA9IG5ldyB4aHIuUmVxdWVzdCh7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICB1cmw6ICcvanNvbnJwYycsXG4gICAgICAgIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIGRhdGE6IEpTT04uc3RyaW5naWZ5KGV4Y2hhbmdlLnJlcXVlc3QpLFxuICAgICAgICB0aW1lb3V0OiA2MDAwMCxcbiAgICB9KVxuICAgICAgICAuZmluYWxseShmdW5jdGlvbiAoKSB7XG4gICAgICAgICAgICBleGNoYW5nZS5jb21wbGV0ZWQgPSBEYXRlLm5vdygpO1xuICAgICAgICB9KVxuICAgICAgICAudGhlbihmdW5jdGlvbiAocmVzcG9uc2UpIHtcbiAgICAgICAgICAgIGV4Y2hhbmdlLnJlc3BvbnNlID0gcmVzcG9uc2U7XG5cbiAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1JFU1BPTlNFLFxuICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICByZXNwb25zZTogcmVzcG9uc2UsXG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgaWYgKHJlc3BvbnNlLmVycm9yKSB7XG4gICAgICAgICAgICAgICAgdGhyb3cgbmV3IFJwY0Vycm9yKHJlc3BvbnNlLmVycm9yKTtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlLnJlc3VsdDtcbiAgICAgICAgfSlcbiAgICAgICAgLmNhdGNoKHhoci5FcnJvciwgZnVuY3Rpb24gKGVycm9yKSB7XG4gICAgICAgICAgICBleGNoYW5nZS5lcnJvciA9IGVycm9yO1xuXG4gICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuRkFJTF9SRVFVRVNULFxuICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICBlcnJvcjogZXJyb3IsXG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgIH0pO1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFJwY0V4Y2hhbmdlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5tb2R1bGUuZXhwb3J0cyA9IHtcbiAgICBFcnJvcjogcmVxdWlyZSgnLi9lcnJvcicpLFxuICAgIEV4Y2hhbmdlOiByZXF1aXJlKCcuL2V4Y2hhbmdlJyksXG59O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgRXZlbnRFbWl0dGVyID0gcmVxdWlyZSgnZXZlbnRzJykuRXZlbnRFbWl0dGVyO1xuXG52YXIgQ0hBTkdFX0VWRU5UID0gJ2NoYW5nZSc7XG5cbmZ1bmN0aW9uIFN0b3JlKCkge1xuICAgIEV2ZW50RW1pdHRlci5jYWxsKHRoaXMpO1xufVxuU3RvcmUucHJvdG90eXBlID0gRXZlbnRFbWl0dGVyLnByb3RvdHlwZTtcblxuU3RvcmUucHJvdG90eXBlLmVtaXRDaGFuZ2UgPSBmdW5jdGlvbigpIHtcbiAgICB0aGlzLmVtaXQoQ0hBTkdFX0VWRU5UKTtcbn07XG5cblN0b3JlLnByb3RvdHlwZS5hZGRDaGFuZ2VMaXN0ZW5lciA9IGZ1bmN0aW9uIChjYWxsYmFjaykge1xuICAgIHRoaXMub24oQ0hBTkdFX0VWRU5ULCBjYWxsYmFjayk7XG59O1xuXG5TdG9yZS5wcm90b3R5cGUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIgPSBmdW5jdGlvbiAoY2FsbGJhY2spIHtcbiAgICB0aGlzLnJlbW92ZUxpc3RlbmVyKENIQU5HRV9FVkVOVCwgY2FsbGJhY2spO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBTdG9yZTtcbiIsIid1c2Ugc3RyaWN0JztcblxuZnVuY3Rpb24gWGhyRXJyb3IobWVzc2FnZSwgcmVzcG9uc2UpIHtcbiAgICB0aGlzLm5hbWUgPSAnWGhyRXJyb3InO1xuICAgIHRoaXMubWVzc2FnZSA9IG1lc3NhZ2U7XG4gICAgdGhpcy5yZXNwb25zZSA9IHJlc3BvbnNlO1xufVxuWGhyRXJyb3IucHJvdG90eXBlID0gT2JqZWN0LmNyZWF0ZShFcnJvci5wcm90b3R5cGUpO1xuWGhyRXJyb3IucHJvdG90eXBlLmNvbnN0cnVjdG9yID0gWGhyRXJyb3I7XG5cbm1vZHVsZS5leHBvcnRzID0gWGhyRXJyb3I7XG4iLCIndXNlIHN0cmljdCc7XG5cbm1vZHVsZS5leHBvcnRzID0ge1xuICAgIFJlcXVlc3Q6IHJlcXVpcmUoJy4vcmVxdWVzdCcpLFxuICAgIEVycm9yOiByZXF1aXJlKCcuL2Vycm9yJyksXG59O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgalF1ZXJ5ID0gcmVxdWlyZSgnanF1ZXJ5Jyk7XG52YXIgUHJvbWlzZSA9IHJlcXVpcmUoJ2JsdWViaXJkJyk7XG5cbnZhciBYaHJFcnJvciA9IHJlcXVpcmUoJy4vZXJyb3InKTtcblxuZnVuY3Rpb24gWGhyUmVxdWVzdChvcHRzKSB7XG4gICAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uIChyZXNvbHZlLCByZWplY3QpIHtcbiAgICAgICAgb3B0cy5zdWNjZXNzID0gcmVzb2x2ZTtcbiAgICAgICAgb3B0cy5lcnJvciA9IGZ1bmN0aW9uIChyZXNwb25zZSwgdHlwZSkge1xuICAgICAgICAgICAgc3dpdGNoICh0eXBlKSB7XG4gICAgICAgICAgICBjYXNlICdlcnJvcic6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignU2VydmVyIHJldHVybmVkICcgKyByZXNwb25zZS5zdGF0dXMgKyAnIHN0YXR1cycsIHJlc3BvbnNlKSk7XG4gICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICBjYXNlICd0aW1lb3V0JzpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdSZXF1ZXN0IHRpbWVkIG91dCcsIHJlc3BvbnNlKSk7XG4gICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICBkZWZhdWx0OlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1JlcXVlc3QgZmFpbGVkOiAnICsgdHlwZSwgcmVzcG9uc2UpKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfTtcblxuICAgICAgICBqUXVlcnkuYWpheChvcHRzKTtcbiAgICB9KTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBYaHJSZXF1ZXN0O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2NvbXBvc2VySWQgPSBEYXRlLm5vdygpO1xudmFyIF9jb21wb3NlclZhbHVlID0gJyc7XG52YXIgX2NvbnNvbGVTaG93biA9IGZhbHNlO1xudmFyIF9leGNoYW5nZXMgPSBbXTtcblxudmFyIGNvbnNvbGVTdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5jb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJJZCA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2NvbXBvc2VySWQ7XG59O1xuXG5jb25zb2xlU3RvcmUuZ2V0Q29tcG9zZXJWYWx1ZSA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2NvbXBvc2VyVmFsdWU7XG59O1xuXG5jb25zb2xlU3RvcmUuZ2V0Q29uc29sZVNob3duID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfY29uc29sZVNob3duO1xufTtcblxuY29uc29sZVN0b3JlLmdldEV4Y2hhbmdlcyA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2V4Y2hhbmdlcztcbn07XG5cbmZ1bmN0aW9uIF9yZXNldENvbXBvc2VyVmFsdWUodXBkYXRlTWV0aG9kKSB7XG4gICAgdmFyIGF1dGhvcml6YXRpb24gPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCk7XG4gICAgdmFyIHBhcnNlZDtcblxuICAgIHRyeSB7XG4gICAgICAgIHBhcnNlZCA9IEpTT04ucGFyc2UoX2NvbXBvc2VyVmFsdWUpO1xuXG4gICAgICAgIGlmICh1cGRhdGVNZXRob2QpIHtcbiAgICAgICAgICAgIHBhcnNlZC5tZXRob2QgPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlKCk7XG4gICAgICAgIH1cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIHBhcnNlZCA9IHsgbWV0aG9kOiBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlKCkgfTtcbiAgICB9XG5cbiAgICBpZiAoYXV0aG9yaXphdGlvbikge1xuICAgICAgICBwYXJzZWQuYXV0aG9yaXphdGlvbiA9IGF1dGhvcml6YXRpb247XG4gICAgfSBlbHNlIHtcbiAgICAgICAgZGVsZXRlIHBhcnNlZC5hdXRob3JpemF0aW9uO1xuICAgIH1cblxuICAgIF9jb21wb3NlclZhbHVlID0gSlNPTi5zdHJpbmdpZnkocGFyc2VkLCBudWxsLCAnICAgICcpO1xufVxuXG5fcmVzZXRDb21wb3NlclZhbHVlKCk7XG5cbmNvbnNvbGVTdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgZGlzcGF0Y2hlci53YWl0Rm9yKFtwbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuXSk7XG5cbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlRPR0dMRV9DT05TT0xFOlxuICAgICAgICAgICAgX2NvbnNvbGVTaG93biA9ICFfY29uc29sZVNob3duO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlVQREFURV9DT01QT1NFUl9WQUxVRTpcbiAgICAgICAgICAgIF9jb21wb3NlclZhbHVlID0gYWN0aW9uLnZhbHVlO1xuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgIF9yZXNldENvbXBvc2VyVmFsdWUoKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRTpcbiAgICAgICAgICAgIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgIF9yZXNldENvbXBvc2VyVmFsdWUodHJ1ZSk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuTUFLRV9SRVFVRVNUOlxuICAgICAgICAgICAgX2V4Y2hhbmdlcy5wdXNoKGFjdGlvbi5leGNoYW5nZSk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuRkFJTF9SRVFVRVNUOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1JFU1BPTlNFOlxuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGNvbnNvbGVTdG9yZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9sYXN0RXJyb3IgPSBudWxsO1xuXG52YXIgbG9naW5Gb3JtU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxubG9naW5Gb3JtU3RvcmUuZ2V0TGFzdEVycm9yID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfbGFzdEVycm9yO1xufTtcblxubG9naW5Gb3JtU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGRpc3BhdGNoZXIud2FpdEZvcihbcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbl0pO1xuXG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfbGFzdEVycm9yID0gbnVsbDtcbiAgICAgICAgICAgIGxvZ2luRm9ybVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICAgICAgX2xhc3RFcnJvciA9IGFjdGlvbi5lcnJvcjtcbiAgICAgICAgICAgIGxvZ2luRm9ybVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGxvZ2luRm9ybVN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9hdXRob3JpemF0aW9uID0gc2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbSgnYXV0aG9yaXphdGlvbicpO1xudmFyIF9wYWdlID0gbG9jYXRpb24uaGFzaC5zdWJzdHIoMSk7XG52YXIgX3BsYXRmb3JtcyA9IFtdO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbiA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2F1dGhvcml6YXRpb247XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfcGFnZTtcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBsYXRmb3JtcyA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX3BsYXRmb3Jtcztcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmRpc3BhdGNoVG9rZW4gPSBkaXNwYXRjaGVyLnJlZ2lzdGVyKGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9hdXRob3JpemF0aW9uID0gYWN0aW9uLmF1dGhvcml6YXRpb247XG4gICAgICAgICAgICBzZXNzaW9uU3RvcmFnZS5zZXRJdGVtKCdhdXRob3JpemF0aW9uJywgX2F1dGhvcml6YXRpb24pO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQ6XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfYXV0aG9yaXphdGlvbiA9IG51bGw7XG4gICAgICAgICAgICBzZXNzaW9uU3RvcmFnZS5yZW1vdmVJdGVtKCdhdXRob3JpemF0aW9uJyk7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRTpcbiAgICAgICAgICAgIF9wYWdlID0gYWN0aW9uLnBhZ2U7XG4gICAgICAgICAgICBsb2NhdGlvbi5oYXNoID0gJyMnICsgYWN0aW9uLnBhZ2U7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUzpcbiAgICAgICAgICAgIF9wbGF0Zm9ybXMgPSBhY3Rpb24ucGxhdGZvcm1zO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmU7XG4iXX0=
