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
                    }).promise
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
            platforms = (
                React.createElement("ul", null, 
                    this.state.platforms.map(function (platform) {
                        return (
                            React.createElement("li", null, 
                                platform.name, " (", platform.uuid, ")", 
                                React.createElement("ul", null, 
                                    platform.agents.map(function (agent) {
                                        return (
                                            React.createElement("li", null, agent.name, " (", agent.uuid, ")")
                                        );
                                    })
                                )
                            )
                        );
                    })
                )
            );
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
    }
});

module.exports = platformManagerStore;


},{"../constants/action-types":13,"../dispatcher":14,"../lib/store":18}]},{},[1])
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hcHAuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL2NvbnNvbGUtYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb21wb3Nlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbnNvbGUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9jb252ZXJzYXRpb24uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9leGNoYW5nZS5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2hvbWUuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9sb2ctb3V0LWJ1dHRvbi5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2xvZ2luLWZvcm0uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9uYXZpZ2F0aW9uLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlci5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb25zdGFudHMvYWN0aW9uLXR5cGVzLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvZGlzcGF0Y2hlci9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2V4Y2hhbmdlLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9yZXF1ZXN0LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvc3RvcmVzL2NvbnNvbGUtc3RvcmUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbG9naW4tZm9ybS1zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlLmpzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBO0FDQUEsWUFBWSxDQUFDOztBQUViLElBQUksS0FBSyxHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUMsQ0FBQzs7QUFFN0IsSUFBSSxlQUFlLEdBQUcsT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUM7O0FBRS9ELEtBQUssQ0FBQyxNQUFNO0lBQ1Isb0JBQUMsZUFBZSxFQUFBLElBQUEsQ0FBRyxDQUFBO0lBQ25CLFFBQVEsQ0FBQyxjQUFjLENBQUMsS0FBSyxDQUFDO0NBQ2pDLENBQUM7Ozs7QUNU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Q0FBQyIsImZpbGUiOiJnZW5lcmF0ZWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlc0NvbnRlbnQiOlsiKGZ1bmN0aW9uIGUodCxuLHIpe2Z1bmN0aW9uIHMobyx1KXtpZighbltvXSl7aWYoIXRbb10pe3ZhciBhPXR5cGVvZiByZXF1aXJlPT1cImZ1bmN0aW9uXCImJnJlcXVpcmU7aWYoIXUmJmEpcmV0dXJuIGEobywhMCk7aWYoaSlyZXR1cm4gaShvLCEwKTt2YXIgZj1uZXcgRXJyb3IoXCJDYW5ub3QgZmluZCBtb2R1bGUgJ1wiK28rXCInXCIpO3Rocm93IGYuY29kZT1cIk1PRFVMRV9OT1RfRk9VTkRcIixmfXZhciBsPW5bb109e2V4cG9ydHM6e319O3Rbb11bMF0uY2FsbChsLmV4cG9ydHMsZnVuY3Rpb24oZSl7dmFyIG49dFtvXVsxXVtlXTtyZXR1cm4gcyhuP246ZSl9LGwsbC5leHBvcnRzLGUsdCxuLHIpfXJldHVybiBuW29dLmV4cG9ydHN9dmFyIGk9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtmb3IodmFyIG89MDtvPHIubGVuZ3RoO28rKylzKHJbb10pO3JldHVybiBzfSkiLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBQbGF0Zm9ybU1hbmFnZXIgPSByZXF1aXJlKCcuL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlcicpO1xuXG5SZWFjdC5yZW5kZXIoXG4gICAgPFBsYXRmb3JtTWFuYWdlciAvPixcbiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnYXBwJylcbik7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBScGNFeGNoYW5nZSA9IHJlcXVpcmUoJy4uL2xpYi9ycGMvZXhjaGFuZ2UnKTtcblxudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHtcbiAgICB0b2dnbGVDb25zb2xlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlRPR0dMRV9DT05TT0xFLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIHVwZGF0ZUNvbXBvc2VyVmFsdWU6IGZ1bmN0aW9uICh2YWx1ZSkge1xuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5VUERBVEVfQ09NUE9TRVJfVkFMVUUsXG4gICAgICAgICAgICB2YWx1ZTogdmFsdWUsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgbWFrZVJlcXVlc3Q6IGZ1bmN0aW9uIChvcHRzKSB7XG4gICAgICAgIG5ldyBScGNFeGNoYW5nZShvcHRzKS5wcm9taXNlLmNhdGNoKGZ1bmN0aW9uIGlnbm9yZSgpIHt9KTtcbiAgICB9XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IGNvbnNvbGVBY3Rpb25DcmVhdG9ycztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFByb21pc2UgPSByZXF1aXJlKCdibHVlYmlyZCcpO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIHJwYyA9IHJlcXVpcmUoJy4uL2xpYi9ycGMnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0ge1xuICAgIHJlcXVlc3RBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAodXNlcm5hbWUsIHBhc3N3b3JkKSB7XG4gICAgICAgIG5ldyBycGMuRXhjaGFuZ2Uoe1xuICAgICAgICAgICAgbWV0aG9kOiAnZ2V0QXV0aG9yaXphdGlvbicsXG4gICAgICAgICAgICBwYXJhbXM6IHtcbiAgICAgICAgICAgICAgICB1c2VybmFtZTogdXNlcm5hbWUsXG4gICAgICAgICAgICAgICAgcGFzc3dvcmQ6IHBhc3N3b3JkLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHJlc3VsdCkge1xuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9BVVRIT1JJWkFUSU9OLFxuICAgICAgICAgICAgICAgICAgICBhdXRob3JpemF0aW9uOiByZXN1bHQsXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgLmNhdGNoKHJwYy5FcnJvciwgZnVuY3Rpb24gKGVycm9yKSB7XG4gICAgICAgICAgICAgICAgaWYgKGVycm9yLmNvZGUgJiYgZXJyb3IuY29kZSA9PT0gNDAxKSB7XG4gICAgICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVELFxuICAgICAgICAgICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLFxuICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICB0aHJvdyBlcnJvcjtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9KTtcbiAgICB9LFxuICAgIGNsZWFyQXV0aG9yaXphdGlvbjogZnVuY3Rpb24gKCkge1xuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5DTEVBUl9BVVRIT1JJWkFUSU9OLFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIGdvVG9QYWdlOiBmdW5jdGlvbiAocGFnZSkge1xuICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRSxcbiAgICAgICAgICAgIHBhZ2U6IHBhZ2UsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgbG9hZFBsYXRmb3JtczogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcblxuICAgICAgICBuZXcgcnBjLkV4Y2hhbmdlKHtcbiAgICAgICAgICAgIG1ldGhvZDogJ2xpc3RQbGF0Zm9ybXMnLFxuICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgfSkucHJvbWlzZVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHBsYXRmb3Jtcykge1xuICAgICAgICAgICAgICAgIHJldHVybiBQcm9taXNlLmFsbChwbGF0Zm9ybXMubWFwKGZ1bmN0aW9uIChwbGF0Zm9ybSkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm4gbmV3IHJwYy5FeGNoYW5nZSh7XG4gICAgICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcubGlzdEFnZW50cycsXG4gICAgICAgICAgICAgICAgICAgICAgICBhdXRob3JpemF0aW9uOiBhdXRob3JpemF0aW9uLFxuICAgICAgICAgICAgICAgICAgICB9KS5wcm9taXNlXG4gICAgICAgICAgICAgICAgICAgICAgICAudGhlbihmdW5jdGlvbiAoYWdlbnRzKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm0uYWdlbnRzID0gYWdlbnRzO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBwbGF0Zm9ybTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIH0pKTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocGxhdGZvcm1zKSB7XG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUyxcbiAgICAgICAgICAgICAgICAgICAgcGxhdGZvcm1zOiBwbGF0Zm9ybXMsXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgLmNhdGNoKGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgICAgIGlmIChlcnJvci5jb2RlICYmIGVycm9yLmNvZGUgPT09IDQwMSkge1xuICAgICAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSk7XG4gICAgfSxcbn07XG5cbndpbmRvdy5vbmhhc2hjaGFuZ2UgPSBmdW5jdGlvbiAoKSB7XG4gICAgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMuZ29Ub1BhZ2UobG9jYXRpb24uaGFzaC5zdWJzdHIoMSkpO1xufTtcblxubW9kdWxlLmV4cG9ydHMgPSBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycztcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIGNvbnNvbGVBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9jb25zb2xlLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG5cbnZhciBDb21wb3NlciA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBjb25zb2xlU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnJlcGxhY2VTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICBfb25TZW5kQ2xpY2s6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLm1ha2VSZXF1ZXN0KEpTT04ucGFyc2UodGhpcy5zdGF0ZS5jb21wb3NlclZhbHVlKSk7XG4gICAgfSxcbiAgICBfb25UZXh0YXJlYUNoYW5nZTogZnVuY3Rpb24gKGUpIHtcbiAgICAgICAgY29uc29sZUFjdGlvbkNyZWF0b3JzLnVwZGF0ZUNvbXBvc2VyVmFsdWUoZS50YXJnZXQudmFsdWUpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImNvbXBvc2VyXCI+XG4gICAgICAgICAgICAgICAgPHRleHRhcmVhXG4gICAgICAgICAgICAgICAgICAgIGtleT17dGhpcy5zdGF0ZS5jb21wb3NlcklkfVxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25UZXh0YXJlYUNoYW5nZX1cbiAgICAgICAgICAgICAgICAgICAgZGVmYXVsdFZhbHVlPXt0aGlzLnN0YXRlLmNvbXBvc2VyVmFsdWV9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwic2VuZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT1cIlNlbmRcIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudmFsaWR9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uU2VuZENsaWNrfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICB2YXIgY29tcG9zZXJWYWx1ZSA9IGNvbnNvbGVTdG9yZS5nZXRDb21wb3NlclZhbHVlKCk7XG4gICAgdmFyIHZhbGlkID0gdHJ1ZTtcblxuICAgIHRyeSB7XG4gICAgICAgIEpTT04ucGFyc2UoY29tcG9zZXJWYWx1ZSk7XG4gICAgfSBjYXRjaCAoZXgpIHtcbiAgICAgICAgaWYgKGV4IGluc3RhbmNlb2YgU3ludGF4RXJyb3IpIHtcbiAgICAgICAgICAgIHZhbGlkID0gZmFsc2U7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICB0aHJvdyBleDtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIGNvbXBvc2VySWQ6IGNvbnNvbGVTdG9yZS5nZXRDb21wb3NlcklkKCksXG4gICAgICAgIGNvbXBvc2VyVmFsdWU6IGNvbXBvc2VyVmFsdWUsXG4gICAgICAgIHZhbGlkOiB2YWxpZCxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbXBvc2VyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgQ29tcG9zZXIgPSByZXF1aXJlKCcuL2NvbXBvc2VyJyk7XG52YXIgQ29udmVyc2F0aW9uID0gcmVxdWlyZSgnLi9jb252ZXJzYXRpb24nKTtcblxudmFyIENvbnNvbGUgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImNvbnNvbGVcIj5cbiAgICAgICAgICAgICAgICA8Q29udmVyc2F0aW9uIC8+XG4gICAgICAgICAgICAgICAgPENvbXBvc2VyIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBDb25zb2xlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgJCA9IHJlcXVpcmUoJ2pxdWVyeScpO1xudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIEV4Y2hhbmdlID0gcmVxdWlyZSgnLi9leGNoYW5nZScpO1xudmFyIGNvbnNvbGVTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9jb25zb2xlLXN0b3JlJyk7XG5cbnZhciBDb252ZXJzYXRpb24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyICRjb252ZXJzYXRpb24gPSAkKHRoaXMucmVmcy5jb252ZXJzYXRpb24uZ2V0RE9NTm9kZSgpKTtcblxuICAgICAgICBpZiAoJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSA+ICRjb252ZXJzYXRpb24uaGVpZ2h0KCkpIHtcbiAgICAgICAgICAgICRjb252ZXJzYXRpb24uc2Nyb2xsVG9wKCRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudERpZFVwZGF0ZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB2YXIgJGNvbnZlcnNhdGlvbiA9ICQodGhpcy5yZWZzLmNvbnZlcnNhdGlvbi5nZXRET01Ob2RlKCkpO1xuXG4gICAgICAgICRjb252ZXJzYXRpb24uc3RvcCgpLmFuaW1hdGUoeyBzY3JvbGxUb3A6ICRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykgfSwgNTAwKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgcmVmPVwiY29udmVyc2F0aW9uXCIgY2xhc3NOYW1lPVwiY29udmVyc2F0aW9uXCI+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXhjaGFuZ2VzLm1hcChmdW5jdGlvbiAoZXhjaGFuZ2UsIGluZGV4KSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8RXhjaGFuZ2Uga2V5PXtpbmRleH0gZXhjaGFuZ2U9e2V4Y2hhbmdlfSAvPlxuICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4geyBleGNoYW5nZXM6IGNvbnNvbGVTdG9yZS5nZXRFeGNoYW5nZXMoKSB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbnZlcnNhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBFeGNoYW5nZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfZm9ybWF0VGltZTogZnVuY3Rpb24gKHRpbWUpIHtcbiAgICAgICAgdmFyIGQgPSBuZXcgRGF0ZSgpO1xuXG4gICAgICAgIGQuc2V0VGltZSh0aW1lKTtcblxuICAgICAgICByZXR1cm4gZC50b0xvY2FsZVN0cmluZygpO1xuICAgIH0sXG4gICAgX2Zvcm1hdE1lc3NhZ2U6IGZ1bmN0aW9uIChtZXNzYWdlKSB7XG4gICAgICAgIHJldHVybiBKU09OLnN0cmluZ2lmeShtZXNzYWdlLCBudWxsLCAnICAgICcpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBleGNoYW5nZSA9IHRoaXMucHJvcHMuZXhjaGFuZ2U7XG4gICAgICAgIHZhciBjbGFzc2VzID0gWydyZXNwb25zZSddO1xuICAgICAgICB2YXIgcmVzcG9uc2VUZXh0O1xuXG4gICAgICAgIGlmICghZXhjaGFuZ2UuY29tcGxldGVkKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1wZW5kaW5nJyk7XG4gICAgICAgICAgICByZXNwb25zZVRleHQgPSAnV2FpdGluZyBmb3IgcmVzcG9uc2UuLi4nO1xuICAgICAgICB9IGVsc2UgaWYgKGV4Y2hhbmdlLmVycm9yKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3Jlc3BvbnNlLS1lcnJvcicpO1xuICAgICAgICAgICAgcmVzcG9uc2VUZXh0ID0gZXhjaGFuZ2UuZXJyb3IubWVzc2FnZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGlmIChleGNoYW5nZS5yZXNwb25zZS5lcnJvcikge1xuICAgICAgICAgICAgICAgIGNsYXNzZXMucHVzaCgncmVzcG9uc2UtLWVycm9yJyk7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9IHRoaXMuX2Zvcm1hdE1lc3NhZ2UoZXhjaGFuZ2UucmVzcG9uc2UpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXhjaGFuZ2VcIj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInJlcXVlc3RcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJ0aW1lXCI+e3RoaXMuX2Zvcm1hdFRpbWUoZXhjaGFuZ2UuaW5pdGlhdGVkKX08L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgPHByZT57dGhpcy5fZm9ybWF0TWVzc2FnZShleGNoYW5nZS5yZXF1ZXN0KX08L3ByZT5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT17Y2xhc3Nlcy5qb2luKCcgJyl9PlxuICAgICAgICAgICAgICAgICAgICB7ZXhjaGFuZ2UuY29tcGxldGVkICYmIDxkaXYgY2xhc3NOYW1lPVwidGltZVwiPnt0aGlzLl9mb3JtYXRUaW1lKGV4Y2hhbmdlLmNvbXBsZXRlZCl9PC9kaXY+fVxuICAgICAgICAgICAgICAgICAgICA8cHJlPntyZXNwb25zZVRleHR9PC9wcmU+XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBFeGNoYW5nZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzID0gcmVxdWlyZSgnLi4vYWN0aW9uLWNyZWF0b3JzL3BsYXRmb3JtLW1hbmFnZXItYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgSG9tZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBnZXRJbml0aWFsU3RhdGU6IGdldFN0YXRlRnJvbVN0b3JlcyxcbiAgICBjb21wb25lbnREaWRNb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5hZGRDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgICAgIHNldFRpbWVvdXQocGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMubG9hZFBsYXRmb3Jtcyk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIHBsYXRmb3JtcztcblxuICAgICAgICBpZiAoIXRoaXMuc3RhdGUucGxhdGZvcm1zKSB7XG4gICAgICAgICAgICBwbGF0Zm9ybXMgPSAoXG4gICAgICAgICAgICAgICAgPHA+TG9hZGluZyBwbGF0Zm9ybXMuLi48L3A+XG4gICAgICAgICAgICApO1xuICAgICAgICB9IGVsc2UgaWYgKCF0aGlzLnN0YXRlLnBsYXRmb3Jtcy5sZW5ndGgpIHtcbiAgICAgICAgICAgIHBsYXRmb3JtcyA9IChcbiAgICAgICAgICAgICAgICA8cD5ObyBwbGF0Zm9ybXMgZm91bmQuPC9wPlxuICAgICAgICAgICAgKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIHBsYXRmb3JtcyA9IChcbiAgICAgICAgICAgICAgICA8dWw+XG4gICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLnBsYXRmb3Jtcy5tYXAoZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxsaT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAge3BsYXRmb3JtLm5hbWV9ICh7cGxhdGZvcm0udXVpZH0pXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtwbGF0Zm9ybS5hZ2VudHMubWFwKGZ1bmN0aW9uIChhZ2VudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxsaT57YWdlbnQubmFtZX0gKHthZ2VudC51dWlkfSk8L2xpPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2xpPlxuICAgICAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJob21lXCI+XG4gICAgICAgICAgICAgICAge3BsYXRmb3Jtc31cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH0sXG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7XG4gICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGxhdGZvcm1zKCksXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBIb21lO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcblxudmFyIExvZ091dEJ1dHRvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfb25DbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5jbGVhckF1dGhvcml6YXRpb24oKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGJ1dHRvbiBjbGFzc05hbWU9XCJidXR0b25cIiBvbkNsaWNrPXt0aGlzLl9vbkNsaWNrfT5Mb2cgb3V0PC9idXR0b24+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTG9nT3V0QnV0dG9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBsb2dpbkZvcm1TdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9sb2dpbi1mb3JtLXN0b3JlJyk7XG5cbnZhciBMb2dpbkZvcm0gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25TdG9yZXNDaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25TdG9yZXNDaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uU3RvcmVzQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uSW5wdXRDaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZSh7XG4gICAgICAgICAgICB1c2VybmFtZTogdGhpcy5yZWZzLnVzZXJuYW1lLmdldERPTU5vZGUoKS52YWx1ZSxcbiAgICAgICAgICAgIHBhc3N3b3JkOiB0aGlzLnJlZnMucGFzc3dvcmQuZ2V0RE9NTm9kZSgpLnZhbHVlLFxuICAgICAgICAgICAgZXJyb3I6IG51bGwsXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgX29uU3VibWl0OiBmdW5jdGlvbiAoZSkge1xuICAgICAgICBlLnByZXZlbnREZWZhdWx0KCk7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLnJlcXVlc3RBdXRob3JpemF0aW9uKFxuICAgICAgICAgICAgdGhpcy5zdGF0ZS51c2VybmFtZSxcbiAgICAgICAgICAgIHRoaXMuc3RhdGUucGFzc3dvcmRcbiAgICAgICAgKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGZvcm0gY2xhc3NOYW1lPVwibG9naW4tZm9ybVwiIG9uU3VibWl0PXt0aGlzLl9vblN1Ym1pdH0+XG4gICAgICAgICAgICAgICAgPGgxPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9oMT5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwidXNlcm5hbWVcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwidGV4dFwiXG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiVXNlcm5hbWVcIlxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25JbnB1dENoYW5nZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICByZWY9XCJwYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJwYXNzd29yZFwiXG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiUGFzc3dvcmRcIlxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25JbnB1dENoYW5nZX1cbiAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dFxuICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwic3VibWl0XCJcbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9XCJMb2cgaW5cIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudXNlcm5hbWUgfHwgIXRoaXMuc3RhdGUucGFzc3dvcmR9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5lcnJvciA/IChcbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJlcnJvclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUuZXJyb3IubWVzc2FnZX0gKHt0aGlzLnN0YXRlLmVycm9yLmNvZGV9KVxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICApIDogbnVsbCB9XG4gICAgICAgICAgICA8L2Zvcm0+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4geyBlcnJvcjogbG9naW5Gb3JtU3RvcmUuZ2V0TGFzdEVycm9yKCkgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBMb2dpbkZvcm07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBMb2dPdXRCdXR0b24gPSByZXF1aXJlKCcuL2xvZy1vdXQtYnV0dG9uJyk7XG5cbnZhciBOYXZpZ2F0aW9uID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJuYXZpZ2F0aW9uXCI+XG4gICAgICAgICAgICAgICAgPGgxPjxhIGhyZWY9XCIjaG9tZVwiPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9hPjwvaDE+XG4gICAgICAgICAgICAgICAgPExvZ091dEJ1dHRvbiAvPlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTmF2aWdhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIENvbnNvbGUgPSByZXF1aXJlKCcuL2NvbnNvbGUnKTtcbnZhciBjb25zb2xlQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvY29uc29sZS1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBjb25zb2xlU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvY29uc29sZS1zdG9yZScpO1xudmFyIEhvbWUgPSByZXF1aXJlKCcuL2hvbWUnKTtcbnZhciBMb2dpbkZvcm0gPSByZXF1aXJlKCcuL2xvZ2luLWZvcm0nKTtcbnZhciBOYXZpZ2F0aW9uID0gcmVxdWlyZSgnLi9uYXZpZ2F0aW9uJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgUGxhdGZvcm1NYW5hZ2VyID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgY29uc29sZVN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICAgICAgY29uc29sZVN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIF9vbkJ1dHRvbkNsaWNrOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGNvbnNvbGVBY3Rpb25DcmVhdG9ycy50b2dnbGVDb25zb2xlKCk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGNsYXNzZXMgPSBbJ3BsYXRmb3JtLW1hbmFnZXInXTtcblxuICAgICAgICBpZiAoIXRoaXMuc3RhdGUuY29uc29sZVNob3duKSB7XG4gICAgICAgICAgICBjbGFzc2VzLnB1c2goJ3BsYXRmb3JtLW1hbmFnZXItLWNvbnNvbGUtaGlkZGVuJyk7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9e2NsYXNzZXMuam9pbignICcpfT5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIm1haW5cIj5cbiAgICAgICAgICAgICAgICAgICAgeyF0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxMb2dpbkZvcm0gLz59XG4gICAgICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmxvZ2dlZEluICYmIDxOYXZpZ2F0aW9uIC8+fVxuICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5sb2dnZWRJbiAmJiA8SG9tZSAvPn1cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwidG9nZ2xlIGJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT17J0NvbnNvbGUgJyArICh0aGlzLnN0YXRlLmNvbnNvbGVTaG93biA/ICdcXHUyNWJjJyA6ICdcXHUyNWIyJyl9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uQnV0dG9uQ2xpY2t9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5jb25zb2xlU2hvd24gJiYgPENvbnNvbGUgY2xhc3NOYW1lPVwiY29uc29sZVwiIC8+fVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4ge1xuICAgICAgICBjb25zb2xlU2hvd246IGNvbnNvbGVTdG9yZS5nZXRDb25zb2xlU2hvd24oKSxcbiAgICAgICAgbG9nZ2VkSW46ICEhcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpLFxuICAgIH07XG59XG5cbm1vZHVsZS5leHBvcnRzID0gUGxhdGZvcm1NYW5hZ2VyO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIga2V5TWlycm9yID0gcmVxdWlyZSgncmVhY3QvbGliL2tleU1pcnJvcicpO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGtleU1pcnJvcih7XG4gICAgVE9HR0xFX0NPTlNPTEU6IG51bGwsXG5cbiAgICBVUERBVEVfQ09NUE9TRVJfVkFMVUU6IG51bGwsXG5cbiAgICBNQUtFX1JFUVVFU1Q6IG51bGwsXG4gICAgRkFJTF9SRVFVRVNUOiBudWxsLFxuICAgIFJFQ0VJVkVfUkVTUE9OU0U6IG51bGwsXG5cbiAgICBSRUNFSVZFX0FVVEhPUklaQVRJT046IG51bGwsXG4gICAgUkVDRUlWRV9VTkFVVEhPUklaRUQ6IG51bGwsXG4gICAgQ0xFQVJfQVVUSE9SSVpBVElPTjogbnVsbCxcblxuICAgIENIQU5HRV9QQUdFOiBudWxsLFxuXG4gICAgUkVDRUlWRV9QTEFURk9STVM6IG51bGwsXG59KTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIERpc3BhdGNoZXIgPSByZXF1aXJlKCdmbHV4JykuRGlzcGF0Y2hlcjtcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcblxudmFyIGRpc3BhdGNoZXIgPSBuZXcgRGlzcGF0Y2hlcigpO1xuXG5kaXNwYXRjaGVyLmRpc3BhdGNoID0gZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGlmIChhY3Rpb24udHlwZSBpbiBBQ1RJT05fVFlQRVMpIHtcbiAgICAgICAgcmV0dXJuIE9iamVjdC5nZXRQcm90b3R5cGVPZih0aGlzKS5kaXNwYXRjaC5jYWxsKHRoaXMsIGFjdGlvbik7XG4gICAgfVxuXG4gICAgdGhyb3cgJ0Rpc3BhdGNoIGVycm9yOiBpbnZhbGlkIGFjdGlvbiB0eXBlICcgKyBhY3Rpb24udHlwZTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gZGlzcGF0Y2hlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxuZnVuY3Rpb24gUnBjRXJyb3IoZXJyb3IpIHtcbiAgICB0aGlzLm5hbWUgPSAnUnBjRXJyb3InO1xuICAgIHRoaXMuY29kZSA9IGVycm9yLmNvZGU7XG4gICAgdGhpcy5tZXNzYWdlID0gZXJyb3IubWVzc2FnZTtcbiAgICB0aGlzLmRhdGEgPSBlcnJvci5kYXRhO1xufVxuUnBjRXJyb3IucHJvdG90eXBlID0gT2JqZWN0LmNyZWF0ZShFcnJvci5wcm90b3R5cGUpO1xuUnBjRXJyb3IucHJvdG90eXBlLmNvbnN0cnVjdG9yID0gUnBjRXJyb3I7XG5cbm1vZHVsZS5leHBvcnRzID0gUnBjRXJyb3I7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciB1dWlkID0gcmVxdWlyZSgnbm9kZS11dWlkJyk7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi8uLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uLy4uL2Rpc3BhdGNoZXInKTtcbnZhciBScGNFcnJvciA9IHJlcXVpcmUoJy4vZXJyb3InKTtcbnZhciB4aHIgPSByZXF1aXJlKCcuLi94aHInKTtcblxuZnVuY3Rpb24gUnBjRXhjaGFuZ2Uob3B0cykge1xuICAgIGlmICghdGhpcyBpbnN0YW5jZW9mIFJwY0V4Y2hhbmdlKSB7XG4gICAgICAgIHJldHVybiBuZXcgUnBjRXhjaGFuZ2Uob3B0cyk7XG4gICAgfVxuXG4gICAgdmFyIGV4Y2hhbmdlID0gdGhpcztcblxuICAgIC8vIFRPRE86IHZhbGlkYXRlIG9wdHNcbiAgICBvcHRzLmpzb25ycGMgPSAnMi4wJztcbiAgICBvcHRzLmlkID0gdXVpZC52MSgpO1xuXG4gICAgZXhjaGFuZ2UuaW5pdGlhdGVkID0gRGF0ZS5ub3coKTtcbiAgICBleGNoYW5nZS5yZXF1ZXN0ID0gb3B0cztcblxuICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuTUFLRV9SRVFVRVNULFxuICAgICAgICBleGNoYW5nZTogZXhjaGFuZ2UsXG4gICAgICAgIHJlcXVlc3Q6IGV4Y2hhbmdlLnJlcXVlc3QsXG4gICAgfSk7XG5cbiAgICBleGNoYW5nZS5wcm9taXNlID0gbmV3IHhoci5SZXF1ZXN0KHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIHVybDogJy9qc29ucnBjJyxcbiAgICAgICAgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgZGF0YTogSlNPTi5zdHJpbmdpZnkoZXhjaGFuZ2UucmVxdWVzdCksXG4gICAgICAgIHRpbWVvdXQ6IDYwMDAwLFxuICAgIH0pXG4gICAgICAgIC5maW5hbGx5KGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgIGV4Y2hhbmdlLmNvbXBsZXRlZCA9IERhdGUubm93KCk7XG4gICAgICAgIH0pXG4gICAgICAgIC50aGVuKGZ1bmN0aW9uIChyZXNwb25zZSkge1xuICAgICAgICAgICAgZXhjaGFuZ2UucmVzcG9uc2UgPSByZXNwb25zZTtcblxuICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUkVTUE9OU0UsXG4gICAgICAgICAgICAgICAgZXhjaGFuZ2U6IGV4Y2hhbmdlLFxuICAgICAgICAgICAgICAgIHJlc3BvbnNlOiByZXNwb25zZSxcbiAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICBpZiAocmVzcG9uc2UuZXJyb3IpIHtcbiAgICAgICAgICAgICAgICB0aHJvdyBuZXcgUnBjRXJyb3IocmVzcG9uc2UuZXJyb3IpO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICByZXR1cm4gcmVzcG9uc2UucmVzdWx0O1xuICAgICAgICB9KVxuICAgICAgICAuY2F0Y2goeGhyLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgIGV4Y2hhbmdlLmVycm9yID0gZXJyb3I7XG5cbiAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5GQUlMX1JFUVVFU1QsXG4gICAgICAgICAgICAgICAgZXhjaGFuZ2U6IGV4Y2hhbmdlLFxuICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICB0aHJvdyBlcnJvcjtcbiAgICAgICAgfSk7XG59XG5cbm1vZHVsZS5leHBvcnRzID0gUnBjRXhjaGFuZ2U7XG4iLCIndXNlIHN0cmljdCc7XG5cbm1vZHVsZS5leHBvcnRzID0ge1xuICAgIEVycm9yOiByZXF1aXJlKCcuL2Vycm9yJyksXG4gICAgRXhjaGFuZ2U6IHJlcXVpcmUoJy4vZXhjaGFuZ2UnKSxcbn07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBFdmVudEVtaXR0ZXIgPSByZXF1aXJlKCdldmVudHMnKS5FdmVudEVtaXR0ZXI7XG5cbnZhciBDSEFOR0VfRVZFTlQgPSAnY2hhbmdlJztcblxuZnVuY3Rpb24gU3RvcmUoKSB7XG4gICAgRXZlbnRFbWl0dGVyLmNhbGwodGhpcyk7XG59XG5TdG9yZS5wcm90b3R5cGUgPSBFdmVudEVtaXR0ZXIucHJvdG90eXBlO1xuXG5TdG9yZS5wcm90b3R5cGUuZW1pdENoYW5nZSA9IGZ1bmN0aW9uKCkge1xuICAgIHRoaXMuZW1pdChDSEFOR0VfRVZFTlQpO1xufTtcblxuU3RvcmUucHJvdG90eXBlLmFkZENoYW5nZUxpc3RlbmVyID0gZnVuY3Rpb24gKGNhbGxiYWNrKSB7XG4gICAgdGhpcy5vbihDSEFOR0VfRVZFTlQsIGNhbGxiYWNrKTtcbn07XG5cblN0b3JlLnByb3RvdHlwZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lciA9IGZ1bmN0aW9uIChjYWxsYmFjaykge1xuICAgIHRoaXMucmVtb3ZlTGlzdGVuZXIoQ0hBTkdFX0VWRU5ULCBjYWxsYmFjayk7XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IFN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5mdW5jdGlvbiBYaHJFcnJvcihtZXNzYWdlLCByZXNwb25zZSkge1xuICAgIHRoaXMubmFtZSA9ICdYaHJFcnJvcic7XG4gICAgdGhpcy5tZXNzYWdlID0gbWVzc2FnZTtcbiAgICB0aGlzLnJlc3BvbnNlID0gcmVzcG9uc2U7XG59XG5YaHJFcnJvci5wcm90b3R5cGUgPSBPYmplY3QuY3JlYXRlKEVycm9yLnByb3RvdHlwZSk7XG5YaHJFcnJvci5wcm90b3R5cGUuY29uc3RydWN0b3IgPSBYaHJFcnJvcjtcblxubW9kdWxlLmV4cG9ydHMgPSBYaHJFcnJvcjtcbiIsIid1c2Ugc3RyaWN0JztcblxubW9kdWxlLmV4cG9ydHMgPSB7XG4gICAgUmVxdWVzdDogcmVxdWlyZSgnLi9yZXF1ZXN0JyksXG4gICAgRXJyb3I6IHJlcXVpcmUoJy4vZXJyb3InKSxcbn07XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBqUXVlcnkgPSByZXF1aXJlKCdqcXVlcnknKTtcbnZhciBQcm9taXNlID0gcmVxdWlyZSgnYmx1ZWJpcmQnKTtcblxudmFyIFhockVycm9yID0gcmVxdWlyZSgnLi9lcnJvcicpO1xuXG5mdW5jdGlvbiBYaHJSZXF1ZXN0KG9wdHMpIHtcbiAgICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24gKHJlc29sdmUsIHJlamVjdCkge1xuICAgICAgICBvcHRzLnN1Y2Nlc3MgPSByZXNvbHZlO1xuICAgICAgICBvcHRzLmVycm9yID0gZnVuY3Rpb24gKHJlc3BvbnNlLCB0eXBlKSB7XG4gICAgICAgICAgICBzd2l0Y2ggKHR5cGUpIHtcbiAgICAgICAgICAgIGNhc2UgJ2Vycm9yJzpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdTZXJ2ZXIgcmV0dXJuZWQgJyArIHJlc3BvbnNlLnN0YXR1cyArICcgc3RhdHVzJywgcmVzcG9uc2UpKTtcbiAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIGNhc2UgJ3RpbWVvdXQnOlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1JlcXVlc3QgdGltZWQgb3V0JywgcmVzcG9uc2UpKTtcbiAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignUmVxdWVzdCBmYWlsZWQ6ICcgKyB0eXBlLCByZXNwb25zZSkpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9O1xuXG4gICAgICAgIGpRdWVyeS5hamF4KG9wdHMpO1xuICAgIH0pO1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFhoclJlcXVlc3Q7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4vcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIFN0b3JlID0gcmVxdWlyZSgnLi4vbGliL3N0b3JlJyk7XG5cbnZhciBfY29tcG9zZXJJZCA9IERhdGUubm93KCk7XG52YXIgX2NvbXBvc2VyVmFsdWUgPSAnJztcbnZhciBfY29uc29sZVNob3duID0gZmFsc2U7XG52YXIgX2V4Y2hhbmdlcyA9IFtdO1xuXG52YXIgY29uc29sZVN0b3JlID0gbmV3IFN0b3JlKCk7XG5cbmNvbnNvbGVTdG9yZS5nZXRDb21wb3NlcklkID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfY29tcG9zZXJJZDtcbn07XG5cbmNvbnNvbGVTdG9yZS5nZXRDb21wb3NlclZhbHVlID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfY29tcG9zZXJWYWx1ZTtcbn07XG5cbmNvbnNvbGVTdG9yZS5nZXRDb25zb2xlU2hvd24gPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9jb25zb2xlU2hvd247XG59O1xuXG5jb25zb2xlU3RvcmUuZ2V0RXhjaGFuZ2VzID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfZXhjaGFuZ2VzO1xufTtcblxuZnVuY3Rpb24gX3Jlc2V0Q29tcG9zZXJWYWx1ZSh1cGRhdGVNZXRob2QpIHtcbiAgICB2YXIgYXV0aG9yaXphdGlvbiA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldEF1dGhvcml6YXRpb24oKTtcbiAgICB2YXIgcGFyc2VkO1xuXG4gICAgdHJ5IHtcbiAgICAgICAgcGFyc2VkID0gSlNPTi5wYXJzZShfY29tcG9zZXJWYWx1ZSk7XG5cbiAgICAgICAgaWYgKHVwZGF0ZU1ldGhvZCkge1xuICAgICAgICAgICAgcGFyc2VkLm1ldGhvZCA9IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UoKTtcbiAgICAgICAgfVxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgcGFyc2VkID0geyBtZXRob2Q6IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UoKSB9O1xuICAgIH1cblxuICAgIGlmIChhdXRob3JpemF0aW9uKSB7XG4gICAgICAgIHBhcnNlZC5hdXRob3JpemF0aW9uID0gYXV0aG9yaXphdGlvbjtcbiAgICB9IGVsc2Uge1xuICAgICAgICBkZWxldGUgcGFyc2VkLmF1dGhvcml6YXRpb247XG4gICAgfVxuXG4gICAgX2NvbXBvc2VyVmFsdWUgPSBKU09OLnN0cmluZ2lmeShwYXJzZWQsIG51bGwsICcgICAgJyk7XG59XG5cbl9yZXNldENvbXBvc2VyVmFsdWUoKTtcblxuY29uc29sZVN0b3JlLmRpc3BhdGNoVG9rZW4gPSBkaXNwYXRjaGVyLnJlZ2lzdGVyKGZ1bmN0aW9uIChhY3Rpb24pIHtcbiAgICBkaXNwYXRjaGVyLndhaXRGb3IoW3BsYXRmb3JtTWFuYWdlclN0b3JlLmRpc3BhdGNoVG9rZW5dKTtcblxuICAgIHN3aXRjaCAoYWN0aW9uLnR5cGUpIHtcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuVE9HR0xFX0NPTlNPTEU6XG4gICAgICAgICAgICBfY29uc29sZVNob3duID0gIV9jb25zb2xlU2hvd247XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuVVBEQVRFX0NPTVBPU0VSX1ZBTFVFOlxuICAgICAgICAgICAgX2NvbXBvc2VyVmFsdWUgPSBhY3Rpb24udmFsdWU7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9BVVRIT1JJWkFUSU9OOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRDpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgIF9yZXNldENvbXBvc2VyVmFsdWUoKTtcbiAgICAgICAgICAgIGNvbnNvbGVTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRTpcbiAgICAgICAgICAgIF9jb21wb3NlcklkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgIF9yZXNldENvbXBvc2VyVmFsdWUodHJ1ZSk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuTUFLRV9SRVFVRVNUOlxuICAgICAgICAgICAgX2V4Y2hhbmdlcy5wdXNoKGFjdGlvbi5leGNoYW5nZSk7XG4gICAgICAgICAgICBjb25zb2xlU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuRkFJTF9SRVFVRVNUOlxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1JFU1BPTlNFOlxuICAgICAgICAgICAgY29uc29sZVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGNvbnNvbGVTdG9yZTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9sYXN0RXJyb3IgPSBudWxsO1xuXG52YXIgbG9naW5Gb3JtU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxubG9naW5Gb3JtU3RvcmUuZ2V0TGFzdEVycm9yID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfbGFzdEVycm9yO1xufTtcblxubG9naW5Gb3JtU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGRpc3BhdGNoZXIud2FpdEZvcihbcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbl0pO1xuXG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfbGFzdEVycm9yID0gbnVsbDtcbiAgICAgICAgICAgIGxvZ2luRm9ybVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfVU5BVVRIT1JJWkVEOlxuICAgICAgICAgICAgX2xhc3RFcnJvciA9IGFjdGlvbi5lcnJvcjtcbiAgICAgICAgICAgIGxvZ2luRm9ybVN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IGxvZ2luRm9ybVN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgU3RvcmUgPSByZXF1aXJlKCcuLi9saWIvc3RvcmUnKTtcblxudmFyIF9hdXRob3JpemF0aW9uID0gc2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbSgnYXV0aG9yaXphdGlvbicpO1xudmFyIF9wYWdlID0gbG9jYXRpb24uaGFzaC5zdWJzdHIoMSk7XG52YXIgX3BsYXRmb3JtcyA9IG51bGw7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfYXV0aG9yaXphdGlvbjtcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9wYWdlO1xufTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGxhdGZvcm1zID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfcGxhdGZvcm1zO1xufTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZGlzcGF0Y2hUb2tlbiA9IGRpc3BhdGNoZXIucmVnaXN0ZXIoZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIHN3aXRjaCAoYWN0aW9uLnR5cGUpIHtcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9BVVRIT1JJWkFUSU9OOlxuICAgICAgICAgICAgX2F1dGhvcml6YXRpb24gPSBhY3Rpb24uYXV0aG9yaXphdGlvbjtcbiAgICAgICAgICAgIHNlc3Npb25TdG9yYWdlLnNldEl0ZW0oJ2F1dGhvcml6YXRpb24nLCBfYXV0aG9yaXphdGlvbik7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1VOQVVUSE9SSVpFRDpcbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuQ0xFQVJfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9hdXRob3JpemF0aW9uID0gbnVsbDtcbiAgICAgICAgICAgIHNlc3Npb25TdG9yYWdlLnJlbW92ZUl0ZW0oJ2F1dGhvcml6YXRpb24nKTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFOlxuICAgICAgICAgICAgX3BhZ2UgPSBhY3Rpb24ucGFnZTtcbiAgICAgICAgICAgIGxvY2F0aW9uLmhhc2ggPSAnIycgKyBhY3Rpb24ucGFnZTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfUExBVEZPUk1TOlxuICAgICAgICAgICAgX3BsYXRmb3JtcyA9IGFjdGlvbi5wbGF0Zm9ybXM7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBwbGF0Zm9ybU1hbmFnZXJTdG9yZTtcbiJdfQ==
