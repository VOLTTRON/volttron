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
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');
var xhr = require('../lib/xhr');

var messengerActionCreators = {
    makeRequest: function (method, params) {
        var exchange = {
            requestSent: Date.now(),
            request: {
                method: method,
                params: params,
            },
        };

        dispatcher.dispatch({
            type: ACTION_TYPES.CREATE_EXCHANGE,
            exchange: exchange,
        });

        new rpc.Request({
            method: method,
            params: params,
            authorization: platformManagerStore.getAuthorization(),
        })
            .then(function (response) {
                exchange.responseReceived = Date.now();
                exchange.response = response;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            })
            .catch(rpc.Error, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            })
            .catch(xhr.Error, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            });
    }
};

module.exports = messengerActionCreators;


},{"../constants/action-types":13,"../dispatcher":14,"../lib/rpc":16,"../lib/xhr":20,"../stores/platform-manager-store":24}],3:[function(require,module,exports){
'use strict';

var Promise = require('bluebird');

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    requestAuthorization: function (username, password) {
        new rpc.Request({
            method: 'getAuthorization',
            params: {
                username: username,
                password: password,
            },
        })
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_AUTHORIZATION,
                    authorization: result,
                });
            })
            .catch(rpc.Error, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
                    error: error,
                });
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

        new rpc.Request({
            method: 'listPlatforms',
            authorization: authorization,
        })
            .then(function (platforms) {
                return Promise.all(platforms.map(function (platform) {
                    return new rpc.Request({
                        method: 'platforms.uuid.' + platform.uuid + '.listAgents',
                        authorization: authorization,
                    })
                        .then(function (agents) {
                            return Promise.all(agents.map(function (agent) {
                                return new rpc.Request({
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
            });
    },
};

module.exports = platformManagerActionCreators;


},{"../constants/action-types":13,"../dispatcher":14,"../lib/rpc":16,"../stores/platform-manager-store":24,"bluebird":undefined}],4:[function(require,module,exports){
'use strict';

var React = require('react');

var messengerActionCreators = require('../action-creators/messenger-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Composer = React.createClass({displayName: "Composer",
    getInitialState: function () {
        return {
            id: Date.now(),
            request: {
                method: platformManagerStore.getPage(),
            },
            valid: true,
        };
    },
    shouldComponentUpdate: function (newProps, newState) {
        return (this.state.id !== newState.id || this.state.valid !== newState.valid);
    },
    _onSendClick: function () {
        messengerActionCreators.makeRequest(this.state.request.method, this.state.request.params);

        this.setState({
            id: Date.now(),
            request: this.state.request,
        });
    },
    _onTextareaChange: function (e) {
        var parsed;

        try {
            parsed = JSON.parse(e.target.value);
        } catch (ex) {
            if (ex instanceof SyntaxError) {
                this.setState({ valid: false });
                return;
            } else {
                throw ex;
            }
        }

        this.setState({
            request: {
                method: parsed.method,
                params: parsed.params,
            },
            valid: true,
        });
    },
    render: function () {
        return (
            React.createElement("div", {className: "composer"}, 
                React.createElement("textarea", {
                    key: this.state.id, 
                    onChange: this._onTextareaChange, 
                    defaultValue: JSON.stringify(this.state.request, null, '    ')}
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

module.exports = Composer;


},{"../action-creators/messenger-action-creators":2,"../stores/platform-manager-store":24,"react":undefined}],5:[function(require,module,exports){
'use strict';

var $ = require('jquery');
var React = require('react');

var Exchange = require('./exchange');
var messengerStore = require('../stores/messenger-store');

var Conversation = React.createClass({displayName: "Conversation",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }

        messengerStore.addChangeListener(this._onChange);
    },
    componentDidUpdate: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    componentWillUnmount: function () {
        messengerStore.removeChangeListener(this._onChange);
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
    return { exchanges: messengerStore.getExchanges() };
}

module.exports = Conversation;


},{"../stores/messenger-store":23,"./exchange":6,"jquery":undefined,"react":undefined}],6:[function(require,module,exports){
'use strict';
var React = require('react');

var rpc = require('../lib/rpc');

var Exchange = React.createClass({displayName: "Exchange",
    _formatTime: function (time) {
        var d = new Date();

        d.setTime(time);

        return d.toLocaleString();
    },
    _formatMessage: function (message) {
        message = message.toJSON ? message.toJSON() : message;

        if (typeof message === 'string') {
            return message;
        }

        return JSON.stringify(message, null, '    ');
    },
    render: function () {
        var exchange = this.props.exchange;
        var responseClass = 'response';
        var responseTime, responseText;

        if (!exchange.response) {
            responseClass += ' response--pending';
            responseText = 'Waiting for response...';
        } else {
            if (exchange.response.constructor === rpc.RequestError || exchange.response.constructor == rpc.ResponseError) {
                responseClass += ' response--error';
            }

            if (exchange.responseReceived) {
                responseTime = React.createElement("div", {className: "time"}, this._formatTime(exchange.responseReceived));
            }

            responseText = this._formatMessage(exchange.response);
        }

        return (
            React.createElement("div", {className: "exchange"}, 
                React.createElement("div", {className: "request"}, 
                    React.createElement("div", {className: "time"}, this._formatTime(exchange.requestSent)), 
                    React.createElement("pre", null, this._formatMessage(exchange.request))
                ), 
                React.createElement("div", {className: responseClass}, 
                    responseTime, 
                    React.createElement("pre", null, responseText)
                )
            )
        );
    }
});

module.exports = Exchange;


},{"../lib/rpc":16,"react":undefined}],7:[function(require,module,exports){
'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Home = React.createClass({displayName: "Home",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
        platformManagerActionCreators.loadPlatforms();
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/platform-manager-store":24,"react":undefined}],8:[function(require,module,exports){
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


},{"../action-creators/platform-manager-action-creators":3,"react":undefined}],9:[function(require,module,exports){
'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var loginFormStore = require('../stores/login-form-store');

var LoginForm = React.createClass({displayName: "LoginForm",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        loginFormStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        loginFormStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    _onSubmit: function (e) {
        e.preventDefault();
        platformManagerActionCreators.requestAuthorization(
            this.refs.username.getDOMNode().value,
            this.refs.password.getDOMNode().value
        );
    },
    render: function () {
        return (
            React.createElement("form", {className: "login-form", onSubmit: this._onSubmit}, 
                React.createElement("h1", null, "VOLTTRON(TM) Platform Manager"), 
                React.createElement("input", {ref: "username", placeholder: "Username", type: "text"}), 
                React.createElement("input", {ref: "password", placeholder: "Password", type: "password"}), 
                React.createElement("input", {className: "button", type: "submit", value: "Log in"}), 
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/login-form-store":22,"react":undefined}],10:[function(require,module,exports){
'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');

var Messenger = React.createClass({displayName: "Messenger",
    render: function () {
        return (
            React.createElement("div", {className: "messenger"}, 
                React.createElement(Conversation, null), 
                React.createElement(Composer, null)
            )
        );
    }
});

module.exports = Messenger;


},{"./composer":4,"./conversation":5,"react":undefined}],11:[function(require,module,exports){
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


},{"./log-out-button":8,"react":undefined}],12:[function(require,module,exports){
'use strict';

var React = require('react');

var Home = require('./home');
var LoginForm = require('./login-form');
var Navigation = require('./navigation');
var Messenger = require('./messenger');

var platformManagerStore = require('../stores/platform-manager-store');

var PlatformManager = React.createClass({displayName: "PlatformManager",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        if (!this.state.loggedIn) {
            return (
                React.createElement(LoginForm, null)
            );
        }

        return (
            React.createElement("div", null, 
                React.createElement(Navigation, null), 
                this.state.page === 'home' ? React.createElement(Home, null) : React.createElement(Messenger, null)
            )
        );
    }
});

function getStateFromStores() {
    return {
        loggedIn: !!platformManagerStore.getAuthorization(),
        page: platformManagerStore.getPage(),
    };
}

module.exports = PlatformManager;


},{"../stores/platform-manager-store":24,"./home":7,"./login-form":9,"./messenger":10,"./navigation":11,"react":undefined}],13:[function(require,module,exports){
'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
    RECEIVE_AUTHORIZATION: null,
    RECEIVE_UNAUTHORIZED: null,
    CLEAR_AUTHORIZATION: null,

    CHANGE_PAGE: null,

    RECEIVE_PLATFORMS: null,

    CREATE_EXCHANGE: null,
    UPDATE_EXCHANGE: null,
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

module.exports = {
    Request: require('./request'),
    Error: require('./error'),
};


},{"./error":15,"./request":17}],17:[function(require,module,exports){
'use strict';

var uuid = require('node-uuid');

var RpcError = require('./error');
var XhrRequest = require('../xhr/request');

function RpcRequest(opts) {
    if (!this instanceof RpcRequest) {
        return new RpcRequest(opts);
    }

    // TODO: validate opts

    opts = opts || {};

    var request = {
        jsonrpc: '2.0',
        method: opts.method || null,
        id: uuid.v1(),
    };

    if ('params' in opts) {
        request.params = opts.params;
    }

    if ('authorization' in opts) {
        request.authorization = opts.authorization;
    }

    return new XhrRequest({
        method: 'POST',
        url: '/jsonrpc',
        contentType: 'application/json',
        data: JSON.stringify(request),
        timeout: 60000
    }).then(function (response) {
        if (response.error) {
            throw new RpcError(response.error);
        }

        return response.result;
    });
}

module.exports = RpcRequest;


},{"../xhr/request":21,"./error":15,"node-uuid":undefined}],18:[function(require,module,exports){
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

function XhrError(message) {
    this.name = 'XhrError';
    this.message = message;
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
                reject(new XhrError('Server returned ' + response.status + ' status'));
                break;
            case 'timeout':
                reject(new XhrError('Request timed out'));
                break;
            default:
                reject(new XhrError('Request failed: ' + type));
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


},{"../constants/action-types":13,"../dispatcher":14,"../lib/store":18,"./platform-manager-store":24}],23:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');
var Store = require('../lib/store');

var _exchanges = [];

var messengerStore = new Store();

messengerStore.getExchanges = function () {
    return _exchanges;
};

messengerStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([platformManagerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECIEVE_AUTHORIZATION:
            _exchanges = [];
            messengerStore.emitChange();
            break;

        case ACTION_TYPES.CREATE_EXCHANGE:
            _exchanges.push(action.exchange);
            messengerStore.emitChange();
            break;

        case ACTION_TYPES.UPDATE_EXCHANGE:
            messengerStore.emitChange();
            break;
    }
});

module.exports = messengerStore;


},{"../constants/action-types":13,"../dispatcher":14,"../lib/store":18,"./platform-manager-store":24}],24:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

if (!location.hash) {
    history.replaceState(null, null, '#home');
}

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

window.onhashchange = function () {
    _page = location.hash.substr(1);
    platformManagerStore.emitChange();
};

platformManagerStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _authorization = action.authorization;
            sessionStorage.setItem('authorization', _authorization);
            platformManagerStore.emitChange();
            break;

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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIm5vZGVfbW9kdWxlcy9icm93c2VyaWZ5L25vZGVfbW9kdWxlcy9icm93c2VyLXBhY2svX3ByZWx1ZGUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hcHAuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvYWN0aW9uLWNyZWF0b3JzL21lc3Nlbmdlci1hY3Rpb24tY3JlYXRvcnMuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL2NvbXBvc2VyLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvY29udmVyc2F0aW9uLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvZXhjaGFuZ2UuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9ob21lLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbG9nLW91dC1idXR0b24uanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29tcG9uZW50cy9sb2dpbi1mb3JtLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbWVzc2VuZ2VyLmpzeCIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2NvbXBvbmVudHMvbmF2aWdhdGlvbi5qc3giLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9jb21wb25lbnRzL3BsYXRmb3JtLW1hbmFnZXIuanN4IiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvY29uc3RhbnRzL2FjdGlvbi10eXBlcy5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2Rpc3BhdGNoZXIvaW5kZXguanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIvcnBjL2Vycm9yLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3JwYy9pbmRleC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9ycGMvcmVxdWVzdC5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi9zdG9yZS5qcyIsIi9Vc2Vycy9rYW5nNjE4L2dpdC1yZXBvcy92b2x0dHJvbi9BZ2VudHMvUGxhdGZvcm1NYW5hZ2VyQWdlbnQvdWktc3JjL2pzL2xpYi94aHIvZXJyb3IuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9saWIveGhyL2luZGV4LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvbGliL3hoci9yZXF1ZXN0LmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvc3RvcmVzL2xvZ2luLWZvcm0tc3RvcmUuanMiLCIvVXNlcnMva2FuZzYxOC9naXQtcmVwb3Mvdm9sdHRyb24vQWdlbnRzL1BsYXRmb3JtTWFuYWdlckFnZW50L3VpLXNyYy9qcy9zdG9yZXMvbWVzc2VuZ2VyLXN0b3JlLmpzIiwiL1VzZXJzL2thbmc2MTgvZ2l0LXJlcG9zL3ZvbHR0cm9uL0FnZW50cy9QbGF0Zm9ybU1hbmFnZXJBZ2VudC91aS1zcmMvanMvc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUuanMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUE7QUNBQSxZQUFZLENBQUM7O0FBRWIsSUFBSSxLQUFLLEdBQUcsT0FBTyxDQUFDLE9BQU8sQ0FBQyxDQUFDOztBQUU3QixJQUFJLGVBQWUsR0FBRyxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQzs7QUFFL0QsS0FBSyxDQUFDLE1BQU07SUFDUixvQkFBQyxlQUFlLEVBQUEsSUFBQSxDQUFHLENBQUE7SUFDbkIsUUFBUSxDQUFDLGNBQWMsQ0FBQyxLQUFLLENBQUM7Q0FDakMsQ0FBQzs7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LENBQUM7O0FBRUYsb0JBQW9CLENBQUMsYUFBYSxHQUFHLFVBQVUsQ0FBQyxRQUFRLENBQUMsVUFBVSxNQUFNLEVBQUU7SUFDdkUsUUFBUSxNQUFNLENBQUMsSUFBSTtRQUNmLEtBQUssWUFBWSxDQUFDLHFCQUFxQjtZQUNuQyxjQUFjLEdBQUcsTUFBTSxDQUFDLGFBQWEsQ0FBQztZQUN0QyxjQUFjLENBQUMsT0FBTyxDQUFDLGVBQWUsRUFBRSxjQUFjLENBQUMsQ0FBQztZQUN4RCxvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztBQUM5QyxZQUFZLE1BQU07O1FBRVYsS0FBSyxZQUFZLENBQUMsbUJBQW1CO1lBQ2pDLGNBQWMsR0FBRyxJQUFJLENBQUM7WUFDdEIsY0FBYyxDQUFDLFVBQVUsQ0FBQyxlQUFlLENBQUMsQ0FBQztZQUMzQyxvQkFBb0IsQ0FBQyxVQUFVLEVBQUUsQ0FBQztBQUM5QyxZQUFZLE1BQU07O1FBRVYsS0FBSyxZQUFZLENBQUMsV0FBVztZQUN6QixLQUFLLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQztZQUNwQixRQUFRLENBQUMsSUFBSSxHQUFHLEdBQUcsR0FBRyxNQUFNLENBQUMsSUFBSSxDQUFDO1lBQ2xDLG9CQUFvQixDQUFDLFVBQVUsRUFBRSxDQUFDO0FBQzlDLFlBQVksTUFBTTs7UUFFVixLQUFLLFlBQVksQ0FBQyxpQkFBaUI7WUFDL0IsVUFBVSxHQUFHLE1BQU0sQ0FBQyxTQUFTLENBQUM7WUFDOUIsb0JBQW9CLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDbEMsTUFBTTtLQUNiO0FBQ0wsQ0FBQyxDQUFDLENBQUM7O0FBRUgsTUFBTSxDQUFDLE9BQU8sR0FBRyxvQkFBb0IsQ0FBQyIsImZpbGUiOiJnZW5lcmF0ZWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlc0NvbnRlbnQiOlsiKGZ1bmN0aW9uIGUodCxuLHIpe2Z1bmN0aW9uIHMobyx1KXtpZighbltvXSl7aWYoIXRbb10pe3ZhciBhPXR5cGVvZiByZXF1aXJlPT1cImZ1bmN0aW9uXCImJnJlcXVpcmU7aWYoIXUmJmEpcmV0dXJuIGEobywhMCk7aWYoaSlyZXR1cm4gaShvLCEwKTt2YXIgZj1uZXcgRXJyb3IoXCJDYW5ub3QgZmluZCBtb2R1bGUgJ1wiK28rXCInXCIpO3Rocm93IGYuY29kZT1cIk1PRFVMRV9OT1RfRk9VTkRcIixmfXZhciBsPW5bb109e2V4cG9ydHM6e319O3Rbb11bMF0uY2FsbChsLmV4cG9ydHMsZnVuY3Rpb24oZSl7dmFyIG49dFtvXVsxXVtlXTtyZXR1cm4gcyhuP246ZSl9LGwsbC5leHBvcnRzLGUsdCxuLHIpfXJldHVybiBuW29dLmV4cG9ydHN9dmFyIGk9dHlwZW9mIHJlcXVpcmU9PVwiZnVuY3Rpb25cIiYmcmVxdWlyZTtmb3IodmFyIG89MDtvPHIubGVuZ3RoO28rKylzKHJbb10pO3JldHVybiBzfSkiLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBQbGF0Zm9ybU1hbmFnZXIgPSByZXF1aXJlKCcuL2NvbXBvbmVudHMvcGxhdGZvcm0tbWFuYWdlcicpO1xuXG5SZWFjdC5yZW5kZXIoXG4gICAgPFBsYXRmb3JtTWFuYWdlciAvPixcbiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnYXBwJylcbik7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9wbGF0Zm9ybS1tYW5hZ2VyLXN0b3JlJyk7XG52YXIgcnBjID0gcmVxdWlyZSgnLi4vbGliL3JwYycpO1xudmFyIHhociA9IHJlcXVpcmUoJy4uL2xpYi94aHInKTtcblxudmFyIG1lc3NlbmdlckFjdGlvbkNyZWF0b3JzID0ge1xuICAgIG1ha2VSZXF1ZXN0OiBmdW5jdGlvbiAobWV0aG9kLCBwYXJhbXMpIHtcbiAgICAgICAgdmFyIGV4Y2hhbmdlID0ge1xuICAgICAgICAgICAgcmVxdWVzdFNlbnQ6IERhdGUubm93KCksXG4gICAgICAgICAgICByZXF1ZXN0OiB7XG4gICAgICAgICAgICAgICAgbWV0aG9kOiBtZXRob2QsXG4gICAgICAgICAgICAgICAgcGFyYW1zOiBwYXJhbXMsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9O1xuXG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNSRUFURV9FWENIQU5HRSxcbiAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgfSk7XG5cbiAgICAgICAgbmV3IHJwYy5SZXF1ZXN0KHtcbiAgICAgICAgICAgIG1ldGhvZDogbWV0aG9kLFxuICAgICAgICAgICAgcGFyYW1zOiBwYXJhbXMsXG4gICAgICAgICAgICBhdXRob3JpemF0aW9uOiBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCksXG4gICAgICAgIH0pXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocmVzcG9uc2UpIHtcbiAgICAgICAgICAgICAgICBleGNoYW5nZS5yZXNwb25zZVJlY2VpdmVkID0gRGF0ZS5ub3coKTtcbiAgICAgICAgICAgICAgICBleGNoYW5nZS5yZXNwb25zZSA9IHJlc3BvbnNlO1xuXG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5VUERBVEVfRVhDSEFOR0UsXG4gICAgICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAuY2F0Y2gocnBjLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBleGNoYW5nZS5yZXNwb25zZSA9IGVycm9yO1xuXG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5VUERBVEVfRVhDSEFOR0UsXG4gICAgICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAuY2F0Y2goeGhyLkVycm9yLCBmdW5jdGlvbiAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBleGNoYW5nZS5yZXNwb25zZSA9IGVycm9yO1xuXG4gICAgICAgICAgICAgICAgZGlzcGF0Y2hlci5kaXNwYXRjaCh7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6IEFDVElPTl9UWVBFUy5VUERBVEVfRVhDSEFOR0UsXG4gICAgICAgICAgICAgICAgICAgIGV4Y2hhbmdlOiBleGNoYW5nZSxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pO1xuICAgIH1cbn07XG5cbm1vZHVsZS5leHBvcnRzID0gbWVzc2VuZ2VyQWN0aW9uQ3JlYXRvcnM7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBQcm9taXNlID0gcmVxdWlyZSgnYmx1ZWJpcmQnKTtcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcbnZhciBkaXNwYXRjaGVyID0gcmVxdWlyZSgnLi4vZGlzcGF0Y2hlcicpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBycGMgPSByZXF1aXJlKCcuLi9saWIvcnBjJyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHtcbiAgICByZXF1ZXN0QXV0aG9yaXphdGlvbjogZnVuY3Rpb24gKHVzZXJuYW1lLCBwYXNzd29yZCkge1xuICAgICAgICBuZXcgcnBjLlJlcXVlc3Qoe1xuICAgICAgICAgICAgbWV0aG9kOiAnZ2V0QXV0aG9yaXphdGlvbicsXG4gICAgICAgICAgICBwYXJhbXM6IHtcbiAgICAgICAgICAgICAgICB1c2VybmFtZTogdXNlcm5hbWUsXG4gICAgICAgICAgICAgICAgcGFzc3dvcmQ6IHBhc3N3b3JkLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChyZXN1bHQpIHtcbiAgICAgICAgICAgICAgICBkaXNwYXRjaGVyLmRpc3BhdGNoKHtcbiAgICAgICAgICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTixcbiAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogcmVzdWx0LFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIC5jYXRjaChycGMuRXJyb3IsIGZ1bmN0aW9uIChlcnJvcikge1xuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQsXG4gICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvcixcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pO1xuICAgIH0sXG4gICAgY2xlYXJBdXRob3JpemF0aW9uOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT04sXG4gICAgICAgIH0pO1xuICAgIH0sXG4gICAgZ29Ub1BhZ2U6IGZ1bmN0aW9uIChwYWdlKSB7XG4gICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgdHlwZTogQUNUSU9OX1RZUEVTLkNIQU5HRV9QQUdFLFxuICAgICAgICAgICAgcGFnZTogcGFnZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICBsb2FkUGxhdGZvcm1zOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciBhdXRob3JpemF0aW9uID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbigpO1xuXG4gICAgICAgIG5ldyBycGMuUmVxdWVzdCh7XG4gICAgICAgICAgICBtZXRob2Q6ICdsaXN0UGxhdGZvcm1zJyxcbiAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgIH0pXG4gICAgICAgICAgICAudGhlbihmdW5jdGlvbiAocGxhdGZvcm1zKSB7XG4gICAgICAgICAgICAgICAgcmV0dXJuIFByb21pc2UuYWxsKHBsYXRmb3Jtcy5tYXAoZnVuY3Rpb24gKHBsYXRmb3JtKSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiBuZXcgcnBjLlJlcXVlc3Qoe1xuICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAncGxhdGZvcm1zLnV1aWQuJyArIHBsYXRmb3JtLnV1aWQgKyAnLmxpc3RBZ2VudHMnLFxuICAgICAgICAgICAgICAgICAgICAgICAgYXV0aG9yaXphdGlvbjogYXV0aG9yaXphdGlvbixcbiAgICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICAgICAgICAgIC50aGVuKGZ1bmN0aW9uIChhZ2VudHMpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gUHJvbWlzZS5hbGwoYWdlbnRzLm1hcChmdW5jdGlvbiAoYWdlbnQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIG5ldyBycGMuUmVxdWVzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdwbGF0Zm9ybXMudXVpZC4nICsgcGxhdGZvcm0udXVpZCArICcuYWdlbnRzLnV1aWQuJyArIGFnZW50LnV1aWQgKyAnLmxpc3RNZXRob2RzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGF1dGhvcml6YXRpb246IGF1dGhvcml6YXRpb24sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAudGhlbihmdW5jdGlvbiAobWV0aG9kcykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFnZW50Lm1ldGhvZHMgPSBtZXRob2RzO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBhZ2VudDtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KSk7XG4gICAgICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKGFnZW50cykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtLmFnZW50cyA9IGFnZW50cztcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gcGxhdGZvcm07XG4gICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICB9KSk7XG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgLnRoZW4oZnVuY3Rpb24gKHBsYXRmb3Jtcykge1xuICAgICAgICAgICAgICAgIGRpc3BhdGNoZXIuZGlzcGF0Y2goe1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiBBQ1RJT05fVFlQRVMuUkVDRUlWRV9QTEFURk9STVMsXG4gICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1zLFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgfSxcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnM7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBtZXNzZW5nZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9tZXNzZW5nZXItYWN0aW9uLWNyZWF0b3JzJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgQ29tcG9zZXIgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBpZDogRGF0ZS5ub3coKSxcbiAgICAgICAgICAgIHJlcXVlc3Q6IHtcbiAgICAgICAgICAgICAgICBtZXRob2Q6IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UoKSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB2YWxpZDogdHJ1ZSxcbiAgICAgICAgfTtcbiAgICB9LFxuICAgIHNob3VsZENvbXBvbmVudFVwZGF0ZTogZnVuY3Rpb24gKG5ld1Byb3BzLCBuZXdTdGF0ZSkge1xuICAgICAgICByZXR1cm4gKHRoaXMuc3RhdGUuaWQgIT09IG5ld1N0YXRlLmlkIHx8IHRoaXMuc3RhdGUudmFsaWQgIT09IG5ld1N0YXRlLnZhbGlkKTtcbiAgICB9LFxuICAgIF9vblNlbmRDbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBtZXNzZW5nZXJBY3Rpb25DcmVhdG9ycy5tYWtlUmVxdWVzdCh0aGlzLnN0YXRlLnJlcXVlc3QubWV0aG9kLCB0aGlzLnN0YXRlLnJlcXVlc3QucGFyYW1zKTtcblxuICAgICAgICB0aGlzLnNldFN0YXRlKHtcbiAgICAgICAgICAgIGlkOiBEYXRlLm5vdygpLFxuICAgICAgICAgICAgcmVxdWVzdDogdGhpcy5zdGF0ZS5yZXF1ZXN0LFxuICAgICAgICB9KTtcbiAgICB9LFxuICAgIF9vblRleHRhcmVhQ2hhbmdlOiBmdW5jdGlvbiAoZSkge1xuICAgICAgICB2YXIgcGFyc2VkO1xuXG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBwYXJzZWQgPSBKU09OLnBhcnNlKGUudGFyZ2V0LnZhbHVlKTtcbiAgICAgICAgfSBjYXRjaCAoZXgpIHtcbiAgICAgICAgICAgIGlmIChleCBpbnN0YW5jZW9mIFN5bnRheEVycm9yKSB7XG4gICAgICAgICAgICAgICAgdGhpcy5zZXRTdGF0ZSh7IHZhbGlkOiBmYWxzZSB9KTtcbiAgICAgICAgICAgICAgICByZXR1cm47XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIHRocm93IGV4O1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgdGhpcy5zZXRTdGF0ZSh7XG4gICAgICAgICAgICByZXF1ZXN0OiB7XG4gICAgICAgICAgICAgICAgbWV0aG9kOiBwYXJzZWQubWV0aG9kLFxuICAgICAgICAgICAgICAgIHBhcmFtczogcGFyc2VkLnBhcmFtcyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB2YWxpZDogdHJ1ZSxcbiAgICAgICAgfSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiY29tcG9zZXJcIj5cbiAgICAgICAgICAgICAgICA8dGV4dGFyZWFcbiAgICAgICAgICAgICAgICAgICAga2V5PXt0aGlzLnN0YXRlLmlkfVxuICAgICAgICAgICAgICAgICAgICBvbkNoYW5nZT17dGhpcy5fb25UZXh0YXJlYUNoYW5nZX1cbiAgICAgICAgICAgICAgICAgICAgZGVmYXVsdFZhbHVlPXtKU09OLnN0cmluZ2lmeSh0aGlzLnN0YXRlLnJlcXVlc3QsIG51bGwsICcgICAgJyl9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8aW5wdXRcbiAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwiYnV0dG9uXCJcbiAgICAgICAgICAgICAgICAgICAgcmVmPVwic2VuZFwiXG4gICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICB2YWx1ZT1cIlNlbmRcIlxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17IXRoaXMuc3RhdGUudmFsaWR9XG4gICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e3RoaXMuX29uU2VuZENsaWNrfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9LFxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gQ29tcG9zZXI7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciAkID0gcmVxdWlyZSgnanF1ZXJ5Jyk7XG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgRXhjaGFuZ2UgPSByZXF1aXJlKCcuL2V4Y2hhbmdlJyk7XG52YXIgbWVzc2VuZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvbWVzc2VuZ2VyLXN0b3JlJyk7XG5cbnZhciBDb252ZXJzYXRpb24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyICRjb252ZXJzYXRpb24gPSAkKHRoaXMucmVmcy5jb252ZXJzYXRpb24uZ2V0RE9NTm9kZSgpKTtcblxuICAgICAgICBpZiAoJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSA+ICRjb252ZXJzYXRpb24uaGVpZ2h0KCkpIHtcbiAgICAgICAgICAgICRjb252ZXJzYXRpb24uc2Nyb2xsVG9wKCRjb252ZXJzYXRpb24ucHJvcCgnc2Nyb2xsSGVpZ2h0JykpO1xuICAgICAgICB9XG5cbiAgICAgICAgbWVzc2VuZ2VyU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50RGlkVXBkYXRlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHZhciAkY29udmVyc2F0aW9uID0gJCh0aGlzLnJlZnMuY29udmVyc2F0aW9uLmdldERPTU5vZGUoKSk7XG5cbiAgICAgICAgJGNvbnZlcnNhdGlvbi5zdG9wKCkuYW5pbWF0ZSh7IHNjcm9sbFRvcDogJGNvbnZlcnNhdGlvbi5wcm9wKCdzY3JvbGxIZWlnaHQnKSB9LCA1MDApO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbWVzc2VuZ2VyU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IHJlZj1cImNvbnZlcnNhdGlvblwiIGNsYXNzTmFtZT1cImNvbnZlcnNhdGlvblwiPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmV4Y2hhbmdlcy5tYXAoZnVuY3Rpb24gKGV4Y2hhbmdlLCBpbmRleCkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgPEV4Y2hhbmdlIGtleT17aW5kZXh9IGV4Y2hhbmdlPXtleGNoYW5nZX0gLz5cbiAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5mdW5jdGlvbiBnZXRTdGF0ZUZyb21TdG9yZXMoKSB7XG4gICAgcmV0dXJuIHsgZXhjaGFuZ2VzOiBtZXNzZW5nZXJTdG9yZS5nZXRFeGNoYW5nZXMoKSB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IENvbnZlcnNhdGlvbjtcbiIsIid1c2Ugc3RyaWN0JztcbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBycGMgPSByZXF1aXJlKCcuLi9saWIvcnBjJyk7XG5cbnZhciBFeGNoYW5nZSA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfZm9ybWF0VGltZTogZnVuY3Rpb24gKHRpbWUpIHtcbiAgICAgICAgdmFyIGQgPSBuZXcgRGF0ZSgpO1xuXG4gICAgICAgIGQuc2V0VGltZSh0aW1lKTtcblxuICAgICAgICByZXR1cm4gZC50b0xvY2FsZVN0cmluZygpO1xuICAgIH0sXG4gICAgX2Zvcm1hdE1lc3NhZ2U6IGZ1bmN0aW9uIChtZXNzYWdlKSB7XG4gICAgICAgIG1lc3NhZ2UgPSBtZXNzYWdlLnRvSlNPTiA/IG1lc3NhZ2UudG9KU09OKCkgOiBtZXNzYWdlO1xuXG4gICAgICAgIGlmICh0eXBlb2YgbWVzc2FnZSA9PT0gJ3N0cmluZycpIHtcbiAgICAgICAgICAgIHJldHVybiBtZXNzYWdlO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIEpTT04uc3RyaW5naWZ5KG1lc3NhZ2UsIG51bGwsICcgICAgJyk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdmFyIGV4Y2hhbmdlID0gdGhpcy5wcm9wcy5leGNoYW5nZTtcbiAgICAgICAgdmFyIHJlc3BvbnNlQ2xhc3MgPSAncmVzcG9uc2UnO1xuICAgICAgICB2YXIgcmVzcG9uc2VUaW1lLCByZXNwb25zZVRleHQ7XG5cbiAgICAgICAgaWYgKCFleGNoYW5nZS5yZXNwb25zZSkge1xuICAgICAgICAgICAgcmVzcG9uc2VDbGFzcyArPSAnIHJlc3BvbnNlLS1wZW5kaW5nJztcbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9ICdXYWl0aW5nIGZvciByZXNwb25zZS4uLic7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBpZiAoZXhjaGFuZ2UucmVzcG9uc2UuY29uc3RydWN0b3IgPT09IHJwYy5SZXF1ZXN0RXJyb3IgfHwgZXhjaGFuZ2UucmVzcG9uc2UuY29uc3RydWN0b3IgPT0gcnBjLlJlc3BvbnNlRXJyb3IpIHtcbiAgICAgICAgICAgICAgICByZXNwb25zZUNsYXNzICs9ICcgcmVzcG9uc2UtLWVycm9yJztcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGV4Y2hhbmdlLnJlc3BvbnNlUmVjZWl2ZWQpIHtcbiAgICAgICAgICAgICAgICByZXNwb25zZVRpbWUgPSA8ZGl2IGNsYXNzTmFtZT1cInRpbWVcIj57dGhpcy5fZm9ybWF0VGltZShleGNoYW5nZS5yZXNwb25zZVJlY2VpdmVkKX08L2Rpdj47XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIHJlc3BvbnNlVGV4dCA9IHRoaXMuX2Zvcm1hdE1lc3NhZ2UoZXhjaGFuZ2UucmVzcG9uc2UpO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZXhjaGFuZ2VcIj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInJlcXVlc3RcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJ0aW1lXCI+e3RoaXMuX2Zvcm1hdFRpbWUoZXhjaGFuZ2UucmVxdWVzdFNlbnQpfTwvZGl2PlxuICAgICAgICAgICAgICAgICAgICA8cHJlPnt0aGlzLl9mb3JtYXRNZXNzYWdlKGV4Y2hhbmdlLnJlcXVlc3QpfTwvcHJlPlxuICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPXtyZXNwb25zZUNsYXNzfT5cbiAgICAgICAgICAgICAgICAgICAge3Jlc3BvbnNlVGltZX1cbiAgICAgICAgICAgICAgICAgICAgPHByZT57cmVzcG9uc2VUZXh0fTwvcHJlPlxuICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gRXhjaGFuZ2U7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBSZWFjdCA9IHJlcXVpcmUoJ3JlYWN0Jyk7XG5cbnZhciBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycyA9IHJlcXVpcmUoJy4uL2FjdGlvbi1jcmVhdG9ycy9wbGF0Zm9ybS1tYW5hZ2VyLWFjdGlvbi1jcmVhdG9ycycpO1xudmFyIHBsYXRmb3JtTWFuYWdlclN0b3JlID0gcmVxdWlyZSgnLi4vc3RvcmVzL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcblxudmFyIEhvbWUgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5sb2FkUGxhdGZvcm1zKCk7XG4gICAgfSxcbiAgICBjb21wb25lbnRXaWxsVW5tb3VudDogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lcih0aGlzLl9vbkNoYW5nZSk7XG4gICAgfSxcbiAgICBfb25DaGFuZ2U6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgdGhpcy5zZXRTdGF0ZShnZXRTdGF0ZUZyb21TdG9yZXMoKSk7XG4gICAgfSxcbiAgICByZW5kZXI6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiaG9tZVwiPlxuICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAge3RoaXMuc3RhdGUucGxhdGZvcm1zLm1hcChmdW5jdGlvbiAocGxhdGZvcm0pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPGxpPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cGxhdGZvcm0ucGxhdGZvcm19ICh7cGxhdGZvcm0udXVpZH0pXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtwbGF0Zm9ybS5hZ2VudHMubWFwKGZ1bmN0aW9uIChhZ2VudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxsaT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHthZ2VudC5hZ2VudH0gKHthZ2VudC51dWlkfSlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7YWdlbnQubWV0aG9kcy5tYXAoZnVuY3Rpb24gKG1ldGhvZCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB2YXIgaHJlZiA9IFtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICcjcGxhdGZvcm1zJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICd1dWlkJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBsYXRmb3JtLnV1aWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAnYWdlbnRzLnV1aWQnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYWdlbnQudXVpZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICdtZXRob2RzJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZC5tZXRob2QsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIF0uam9pbignLicpO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8bGk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGEgaHJlZj17aHJlZn0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHttZXRob2QubWV0aG9kfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvYT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvbGk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3VsPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2xpPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2xpPlxuICAgICAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgICAgfSl9XG4gICAgICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH0sXG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7XG4gICAgICAgIHBsYXRmb3JtczogcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0UGxhdGZvcm1zKCksXG4gICAgfTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBIb21lO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcblxudmFyIExvZ091dEJ1dHRvbiA9IFJlYWN0LmNyZWF0ZUNsYXNzKHtcbiAgICBfb25DbGljazogZnVuY3Rpb24gKCkge1xuICAgICAgICBwbGF0Zm9ybU1hbmFnZXJBY3Rpb25DcmVhdG9ycy5jbGVhckF1dGhvcml6YXRpb24oKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGJ1dHRvbiBjbGFzc05hbWU9XCJidXR0b25cIiBvbkNsaWNrPXt0aGlzLl9vbkNsaWNrfT5Mb2cgb3V0PC9idXR0b24+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gTG9nT3V0QnV0dG9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyQWN0aW9uQ3JlYXRvcnMgPSByZXF1aXJlKCcuLi9hY3Rpb24tY3JlYXRvcnMvcGxhdGZvcm0tbWFuYWdlci1hY3Rpb24tY3JlYXRvcnMnKTtcbnZhciBsb2dpbkZvcm1TdG9yZSA9IHJlcXVpcmUoJy4uL3N0b3Jlcy9sb2dpbi1mb3JtLXN0b3JlJyk7XG5cbnZhciBMb2dpbkZvcm0gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgZ2V0SW5pdGlhbFN0YXRlOiBnZXRTdGF0ZUZyb21TdG9yZXMsXG4gICAgY29tcG9uZW50RGlkTW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUuYWRkQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgY29tcG9uZW50V2lsbFVubW91bnQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgbG9naW5Gb3JtU3RvcmUucmVtb3ZlQ2hhbmdlTGlzdGVuZXIodGhpcy5fb25DaGFuZ2UpO1xuICAgIH0sXG4gICAgX29uQ2hhbmdlOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHRoaXMuc2V0U3RhdGUoZ2V0U3RhdGVGcm9tU3RvcmVzKCkpO1xuICAgIH0sXG4gICAgX29uU3VibWl0OiBmdW5jdGlvbiAoZSkge1xuICAgICAgICBlLnByZXZlbnREZWZhdWx0KCk7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlckFjdGlvbkNyZWF0b3JzLnJlcXVlc3RBdXRob3JpemF0aW9uKFxuICAgICAgICAgICAgdGhpcy5yZWZzLnVzZXJuYW1lLmdldERPTU5vZGUoKS52YWx1ZSxcbiAgICAgICAgICAgIHRoaXMucmVmcy5wYXNzd29yZC5nZXRET01Ob2RlKCkudmFsdWVcbiAgICAgICAgKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPGZvcm0gY2xhc3NOYW1lPVwibG9naW4tZm9ybVwiIG9uU3VibWl0PXt0aGlzLl9vblN1Ym1pdH0+XG4gICAgICAgICAgICAgICAgPGgxPlZPTFRUUk9OKFRNKSBQbGF0Zm9ybSBNYW5hZ2VyPC9oMT5cbiAgICAgICAgICAgICAgICA8aW5wdXQgcmVmPVwidXNlcm5hbWVcIiBwbGFjZWhvbGRlcj1cIlVzZXJuYW1lXCIgdHlwZT1cInRleHRcIiAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dCByZWY9XCJwYXNzd29yZFwiIHBsYWNlaG9sZGVyPVwiUGFzc3dvcmRcIiB0eXBlPVwicGFzc3dvcmRcIiAvPlxuICAgICAgICAgICAgICAgIDxpbnB1dCBjbGFzc05hbWU9XCJidXR0b25cIiB0eXBlPVwic3VibWl0XCIgdmFsdWU9XCJMb2cgaW5cIiAvPlxuICAgICAgICAgICAgICAgIHt0aGlzLnN0YXRlLmVycm9yID8gKFxuICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImVycm9yXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICB7dGhpcy5zdGF0ZS5lcnJvci5tZXNzYWdlfSAoe3RoaXMuc3RhdGUuZXJyb3IuY29kZX0pXG4gICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICkgOiBudWxsIH1cbiAgICAgICAgICAgIDwvZm9ybT5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxuZnVuY3Rpb24gZ2V0U3RhdGVGcm9tU3RvcmVzKCkge1xuICAgIHJldHVybiB7IGVycm9yOiBsb2dpbkZvcm1TdG9yZS5nZXRMYXN0RXJyb3IoKSB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IExvZ2luRm9ybTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIENvbXBvc2VyID0gcmVxdWlyZSgnLi9jb21wb3NlcicpO1xudmFyIENvbnZlcnNhdGlvbiA9IHJlcXVpcmUoJy4vY29udmVyc2F0aW9uJyk7XG5cbnZhciBNZXNzZW5nZXIgPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIm1lc3NlbmdlclwiPlxuICAgICAgICAgICAgICAgIDxDb252ZXJzYXRpb24gLz5cbiAgICAgICAgICAgICAgICA8Q29tcG9zZXIgLz5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICApO1xuICAgIH1cbn0pO1xuXG5tb2R1bGUuZXhwb3J0cyA9IE1lc3NlbmdlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxudmFyIExvZ091dEJ1dHRvbiA9IHJlcXVpcmUoJy4vbG9nLW91dC1idXR0b24nKTtcblxudmFyIE5hdmlnYXRpb24gPSBSZWFjdC5jcmVhdGVDbGFzcyh7XG4gICAgcmVuZGVyOiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIm5hdmlnYXRpb25cIj5cbiAgICAgICAgICAgICAgICA8aDE+PGEgaHJlZj1cIiNob21lXCI+Vk9MVFRST04oVE0pIFBsYXRmb3JtIE1hbmFnZXI8L2E+PC9oMT5cbiAgICAgICAgICAgICAgICA8TG9nT3V0QnV0dG9uIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgKTtcbiAgICB9XG59KTtcblxubW9kdWxlLmV4cG9ydHMgPSBOYXZpZ2F0aW9uO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgUmVhY3QgPSByZXF1aXJlKCdyZWFjdCcpO1xuXG52YXIgSG9tZSA9IHJlcXVpcmUoJy4vaG9tZScpO1xudmFyIExvZ2luRm9ybSA9IHJlcXVpcmUoJy4vbG9naW4tZm9ybScpO1xudmFyIE5hdmlnYXRpb24gPSByZXF1aXJlKCcuL25hdmlnYXRpb24nKTtcbnZhciBNZXNzZW5nZXIgPSByZXF1aXJlKCcuL21lc3NlbmdlcicpO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuLi9zdG9yZXMvcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xuXG52YXIgUGxhdGZvcm1NYW5hZ2VyID0gUmVhY3QuY3JlYXRlQ2xhc3Moe1xuICAgIGdldEluaXRpYWxTdGF0ZTogZ2V0U3RhdGVGcm9tU3RvcmVzLFxuICAgIGNvbXBvbmVudERpZE1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmFkZENoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIGNvbXBvbmVudFdpbGxVbm1vdW50OiBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLnJlbW92ZUNoYW5nZUxpc3RlbmVyKHRoaXMuX29uQ2hhbmdlKTtcbiAgICB9LFxuICAgIF9vbkNoYW5nZTogZnVuY3Rpb24gKCkge1xuICAgICAgICB0aGlzLnNldFN0YXRlKGdldFN0YXRlRnJvbVN0b3JlcygpKTtcbiAgICB9LFxuICAgIHJlbmRlcjogZnVuY3Rpb24gKCkge1xuICAgICAgICBpZiAoIXRoaXMuc3RhdGUubG9nZ2VkSW4pIHtcbiAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgPExvZ2luRm9ybSAvPlxuICAgICAgICAgICAgKTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8ZGl2PlxuICAgICAgICAgICAgICAgIDxOYXZpZ2F0aW9uIC8+XG4gICAgICAgICAgICAgICAge3RoaXMuc3RhdGUucGFnZSA9PT0gJ2hvbWUnID8gPEhvbWUgLz4gOiA8TWVzc2VuZ2VyIC8+fVxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICk7XG4gICAgfVxufSk7XG5cbmZ1bmN0aW9uIGdldFN0YXRlRnJvbVN0b3JlcygpIHtcbiAgICByZXR1cm4ge1xuICAgICAgICBsb2dnZWRJbjogISFwbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRBdXRob3JpemF0aW9uKCksXG4gICAgICAgIHBhZ2U6IHBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBhZ2UoKSxcbiAgICB9O1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFBsYXRmb3JtTWFuYWdlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIGtleU1pcnJvciA9IHJlcXVpcmUoJ3JlYWN0L2xpYi9rZXlNaXJyb3InKTtcblxubW9kdWxlLmV4cG9ydHMgPSBrZXlNaXJyb3Ioe1xuICAgIFJFQ0VJVkVfQVVUSE9SSVpBVElPTjogbnVsbCxcbiAgICBSRUNFSVZFX1VOQVVUSE9SSVpFRDogbnVsbCxcbiAgICBDTEVBUl9BVVRIT1JJWkFUSU9OOiBudWxsLFxuXG4gICAgQ0hBTkdFX1BBR0U6IG51bGwsXG5cbiAgICBSRUNFSVZFX1BMQVRGT1JNUzogbnVsbCxcblxuICAgIENSRUFURV9FWENIQU5HRTogbnVsbCxcbiAgICBVUERBVEVfRVhDSEFOR0U6IG51bGwsXG59KTtcbiIsIid1c2Ugc3RyaWN0JztcblxudmFyIERpc3BhdGNoZXIgPSByZXF1aXJlKCdmbHV4JykuRGlzcGF0Y2hlcjtcblxudmFyIEFDVElPTl9UWVBFUyA9IHJlcXVpcmUoJy4uL2NvbnN0YW50cy9hY3Rpb24tdHlwZXMnKTtcblxudmFyIGRpc3BhdGNoZXIgPSBuZXcgRGlzcGF0Y2hlcigpO1xuXG5kaXNwYXRjaGVyLmRpc3BhdGNoID0gZnVuY3Rpb24gKGFjdGlvbikge1xuICAgIGlmIChhY3Rpb24udHlwZSBpbiBBQ1RJT05fVFlQRVMpIHtcbiAgICAgICAgcmV0dXJuIE9iamVjdC5nZXRQcm90b3R5cGVPZih0aGlzKS5kaXNwYXRjaC5jYWxsKHRoaXMsIGFjdGlvbik7XG4gICAgfVxuXG4gICAgdGhyb3cgJ0Rpc3BhdGNoIGVycm9yOiBpbnZhbGlkIGFjdGlvbiB0eXBlICcgKyBhY3Rpb24udHlwZTtcbn07XG5cbm1vZHVsZS5leHBvcnRzID0gZGlzcGF0Y2hlcjtcbiIsIid1c2Ugc3RyaWN0JztcblxuZnVuY3Rpb24gUnBjRXJyb3IoZXJyb3IpIHtcbiAgICB0aGlzLm5hbWUgPSAnUnBjRXJyb3InO1xuICAgIHRoaXMuY29kZSA9IGVycm9yLmNvZGU7XG4gICAgdGhpcy5tZXNzYWdlID0gZXJyb3IubWVzc2FnZTtcbiAgICB0aGlzLmRhdGEgPSBlcnJvci5kYXRhO1xufVxuUnBjRXJyb3IucHJvdG90eXBlID0gT2JqZWN0LmNyZWF0ZShFcnJvci5wcm90b3R5cGUpO1xuUnBjRXJyb3IucHJvdG90eXBlLmNvbnN0cnVjdG9yID0gUnBjRXJyb3I7XG5cbm1vZHVsZS5leHBvcnRzID0gUnBjRXJyb3I7XG4iLCIndXNlIHN0cmljdCc7XG5cbm1vZHVsZS5leHBvcnRzID0ge1xuICAgIFJlcXVlc3Q6IHJlcXVpcmUoJy4vcmVxdWVzdCcpLFxuICAgIEVycm9yOiByZXF1aXJlKCcuL2Vycm9yJyksXG59O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgdXVpZCA9IHJlcXVpcmUoJ25vZGUtdXVpZCcpO1xuXG52YXIgUnBjRXJyb3IgPSByZXF1aXJlKCcuL2Vycm9yJyk7XG52YXIgWGhyUmVxdWVzdCA9IHJlcXVpcmUoJy4uL3hoci9yZXF1ZXN0Jyk7XG5cbmZ1bmN0aW9uIFJwY1JlcXVlc3Qob3B0cykge1xuICAgIGlmICghdGhpcyBpbnN0YW5jZW9mIFJwY1JlcXVlc3QpIHtcbiAgICAgICAgcmV0dXJuIG5ldyBScGNSZXF1ZXN0KG9wdHMpO1xuICAgIH1cblxuICAgIC8vIFRPRE86IHZhbGlkYXRlIG9wdHNcblxuICAgIG9wdHMgPSBvcHRzIHx8IHt9O1xuXG4gICAgdmFyIHJlcXVlc3QgPSB7XG4gICAgICAgIGpzb25ycGM6ICcyLjAnLFxuICAgICAgICBtZXRob2Q6IG9wdHMubWV0aG9kIHx8IG51bGwsXG4gICAgICAgIGlkOiB1dWlkLnYxKCksXG4gICAgfTtcblxuICAgIGlmICgncGFyYW1zJyBpbiBvcHRzKSB7XG4gICAgICAgIHJlcXVlc3QucGFyYW1zID0gb3B0cy5wYXJhbXM7XG4gICAgfVxuXG4gICAgaWYgKCdhdXRob3JpemF0aW9uJyBpbiBvcHRzKSB7XG4gICAgICAgIHJlcXVlc3QuYXV0aG9yaXphdGlvbiA9IG9wdHMuYXV0aG9yaXphdGlvbjtcbiAgICB9XG5cbiAgICByZXR1cm4gbmV3IFhoclJlcXVlc3Qoe1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgdXJsOiAnL2pzb25ycGMnLFxuICAgICAgICBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBkYXRhOiBKU09OLnN0cmluZ2lmeShyZXF1ZXN0KSxcbiAgICAgICAgdGltZW91dDogNjAwMDBcbiAgICB9KS50aGVuKGZ1bmN0aW9uIChyZXNwb25zZSkge1xuICAgICAgICBpZiAocmVzcG9uc2UuZXJyb3IpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBScGNFcnJvcihyZXNwb25zZS5lcnJvcik7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gcmVzcG9uc2UucmVzdWx0O1xuICAgIH0pO1xufVxuXG5tb2R1bGUuZXhwb3J0cyA9IFJwY1JlcXVlc3Q7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBFdmVudEVtaXR0ZXIgPSByZXF1aXJlKCdldmVudHMnKS5FdmVudEVtaXR0ZXI7XG5cbnZhciBDSEFOR0VfRVZFTlQgPSAnY2hhbmdlJztcblxuZnVuY3Rpb24gU3RvcmUoKSB7XG4gICAgRXZlbnRFbWl0dGVyLmNhbGwodGhpcyk7XG59XG5TdG9yZS5wcm90b3R5cGUgPSBFdmVudEVtaXR0ZXIucHJvdG90eXBlO1xuXG5TdG9yZS5wcm90b3R5cGUuZW1pdENoYW5nZSA9IGZ1bmN0aW9uKCkge1xuICAgIHRoaXMuZW1pdChDSEFOR0VfRVZFTlQpO1xufTtcblxuU3RvcmUucHJvdG90eXBlLmFkZENoYW5nZUxpc3RlbmVyID0gZnVuY3Rpb24gKGNhbGxiYWNrKSB7XG4gICAgdGhpcy5vbihDSEFOR0VfRVZFTlQsIGNhbGxiYWNrKTtcbn07XG5cblN0b3JlLnByb3RvdHlwZS5yZW1vdmVDaGFuZ2VMaXN0ZW5lciA9IGZ1bmN0aW9uIChjYWxsYmFjaykge1xuICAgIHRoaXMucmVtb3ZlTGlzdGVuZXIoQ0hBTkdFX0VWRU5ULCBjYWxsYmFjayk7XG59O1xuXG5tb2R1bGUuZXhwb3J0cyA9IFN0b3JlO1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG5mdW5jdGlvbiBYaHJFcnJvcihtZXNzYWdlKSB7XG4gICAgdGhpcy5uYW1lID0gJ1hockVycm9yJztcbiAgICB0aGlzLm1lc3NhZ2UgPSBtZXNzYWdlO1xufVxuWGhyRXJyb3IucHJvdG90eXBlID0gT2JqZWN0LmNyZWF0ZShFcnJvci5wcm90b3R5cGUpO1xuWGhyRXJyb3IucHJvdG90eXBlLmNvbnN0cnVjdG9yID0gWGhyRXJyb3I7XG5cbm1vZHVsZS5leHBvcnRzID0gWGhyRXJyb3I7XG4iLCIndXNlIHN0cmljdCc7XG5cbm1vZHVsZS5leHBvcnRzID0ge1xuICAgIFJlcXVlc3Q6IHJlcXVpcmUoJy4vcmVxdWVzdCcpLFxuICAgIEVycm9yOiByZXF1aXJlKCcuL2Vycm9yJyksXG59O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgalF1ZXJ5ID0gcmVxdWlyZSgnanF1ZXJ5Jyk7XG52YXIgUHJvbWlzZSA9IHJlcXVpcmUoJ2JsdWViaXJkJyk7XG5cbnZhciBYaHJFcnJvciA9IHJlcXVpcmUoJy4vZXJyb3InKTtcblxuZnVuY3Rpb24gWGhyUmVxdWVzdChvcHRzKSB7XG4gICAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uIChyZXNvbHZlLCByZWplY3QpIHtcbiAgICAgICAgb3B0cy5zdWNjZXNzID0gcmVzb2x2ZTtcbiAgICAgICAgb3B0cy5lcnJvciA9IGZ1bmN0aW9uIChyZXNwb25zZSwgdHlwZSkge1xuICAgICAgICAgICAgc3dpdGNoICh0eXBlKSB7XG4gICAgICAgICAgICBjYXNlICdlcnJvcic6XG4gICAgICAgICAgICAgICAgcmVqZWN0KG5ldyBYaHJFcnJvcignU2VydmVyIHJldHVybmVkICcgKyByZXNwb25zZS5zdGF0dXMgKyAnIHN0YXR1cycpKTtcbiAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIGNhc2UgJ3RpbWVvdXQnOlxuICAgICAgICAgICAgICAgIHJlamVjdChuZXcgWGhyRXJyb3IoJ1JlcXVlc3QgdGltZWQgb3V0JykpO1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICAgICAgICByZWplY3QobmV3IFhockVycm9yKCdSZXF1ZXN0IGZhaWxlZDogJyArIHR5cGUpKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfTtcblxuICAgICAgICBqUXVlcnkuYWpheChvcHRzKTtcbiAgICB9KTtcbn1cblxubW9kdWxlLmV4cG9ydHMgPSBYaHJSZXF1ZXN0O1xuIiwiJ3VzZSBzdHJpY3QnO1xuXG52YXIgQUNUSU9OX1RZUEVTID0gcmVxdWlyZSgnLi4vY29uc3RhbnRzL2FjdGlvbi10eXBlcycpO1xudmFyIGRpc3BhdGNoZXIgPSByZXF1aXJlKCcuLi9kaXNwYXRjaGVyJyk7XG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSByZXF1aXJlKCcuL3BsYXRmb3JtLW1hbmFnZXItc3RvcmUnKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG52YXIgX2xhc3RFcnJvciA9IG51bGw7XG5cbnZhciBsb2dpbkZvcm1TdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5sb2dpbkZvcm1TdG9yZS5nZXRMYXN0RXJyb3IgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9sYXN0RXJyb3I7XG59O1xuXG5sb2dpbkZvcm1TdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgZGlzcGF0Y2hlci53YWl0Rm9yKFtwbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuXSk7XG5cbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0VJVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9sYXN0RXJyb3IgPSBudWxsO1xuICAgICAgICAgICAgbG9naW5Gb3JtU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuUkVDRUlWRV9VTkFVVEhPUklaRUQ6XG4gICAgICAgICAgICBfbGFzdEVycm9yID0gYWN0aW9uLmVycm9yO1xuICAgICAgICAgICAgbG9naW5Gb3JtU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gbG9naW5Gb3JtU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBwbGF0Zm9ybU1hbmFnZXJTdG9yZSA9IHJlcXVpcmUoJy4vcGxhdGZvcm0tbWFuYWdlci1zdG9yZScpO1xudmFyIFN0b3JlID0gcmVxdWlyZSgnLi4vbGliL3N0b3JlJyk7XG5cbnZhciBfZXhjaGFuZ2VzID0gW107XG5cbnZhciBtZXNzZW5nZXJTdG9yZSA9IG5ldyBTdG9yZSgpO1xuXG5tZXNzZW5nZXJTdG9yZS5nZXRFeGNoYW5nZXMgPSBmdW5jdGlvbiAoKSB7XG4gICAgcmV0dXJuIF9leGNoYW5nZXM7XG59O1xuXG5tZXNzZW5nZXJTdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgZGlzcGF0Y2hlci53YWl0Rm9yKFtwbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuXSk7XG5cbiAgICBzd2l0Y2ggKGFjdGlvbi50eXBlKSB7XG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLlJFQ0lFVkVfQVVUSE9SSVpBVElPTjpcbiAgICAgICAgICAgIF9leGNoYW5nZXMgPSBbXTtcbiAgICAgICAgICAgIG1lc3NlbmdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNSRUFURV9FWENIQU5HRTpcbiAgICAgICAgICAgIF9leGNoYW5nZXMucHVzaChhY3Rpb24uZXhjaGFuZ2UpO1xuICAgICAgICAgICAgbWVzc2VuZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG5cbiAgICAgICAgY2FzZSBBQ1RJT05fVFlQRVMuVVBEQVRFX0VYQ0hBTkdFOlxuICAgICAgICAgICAgbWVzc2VuZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gbWVzc2VuZ2VyU3RvcmU7XG4iLCIndXNlIHN0cmljdCc7XG5cbnZhciBBQ1RJT05fVFlQRVMgPSByZXF1aXJlKCcuLi9jb25zdGFudHMvYWN0aW9uLXR5cGVzJyk7XG52YXIgZGlzcGF0Y2hlciA9IHJlcXVpcmUoJy4uL2Rpc3BhdGNoZXInKTtcbnZhciBTdG9yZSA9IHJlcXVpcmUoJy4uL2xpYi9zdG9yZScpO1xuXG5pZiAoIWxvY2F0aW9uLmhhc2gpIHtcbiAgICBoaXN0b3J5LnJlcGxhY2VTdGF0ZShudWxsLCBudWxsLCAnI2hvbWUnKTtcbn1cblxudmFyIF9hdXRob3JpemF0aW9uID0gc2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbSgnYXV0aG9yaXphdGlvbicpO1xudmFyIF9wYWdlID0gbG9jYXRpb24uaGFzaC5zdWJzdHIoMSk7XG52YXIgX3BsYXRmb3JtcyA9IFtdO1xuXG52YXIgcGxhdGZvcm1NYW5hZ2VyU3RvcmUgPSBuZXcgU3RvcmUoKTtcblxucGxhdGZvcm1NYW5hZ2VyU3RvcmUuZ2V0QXV0aG9yaXphdGlvbiA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX2F1dGhvcml6YXRpb247XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5nZXRQYWdlID0gZnVuY3Rpb24gKCkge1xuICAgIHJldHVybiBfcGFnZTtcbn07XG5cbnBsYXRmb3JtTWFuYWdlclN0b3JlLmdldFBsYXRmb3JtcyA9IGZ1bmN0aW9uICgpIHtcbiAgICByZXR1cm4gX3BsYXRmb3Jtcztcbn07XG5cbndpbmRvdy5vbmhhc2hjaGFuZ2UgPSBmdW5jdGlvbiAoKSB7XG4gICAgX3BhZ2UgPSBsb2NhdGlvbi5oYXNoLnN1YnN0cigxKTtcbiAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG59O1xuXG5wbGF0Zm9ybU1hbmFnZXJTdG9yZS5kaXNwYXRjaFRva2VuID0gZGlzcGF0Y2hlci5yZWdpc3RlcihmdW5jdGlvbiAoYWN0aW9uKSB7XG4gICAgc3dpdGNoIChhY3Rpb24udHlwZSkge1xuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfYXV0aG9yaXphdGlvbiA9IGFjdGlvbi5hdXRob3JpemF0aW9uO1xuICAgICAgICAgICAgc2Vzc2lvblN0b3JhZ2Uuc2V0SXRlbSgnYXV0aG9yaXphdGlvbicsIF9hdXRob3JpemF0aW9uKTtcbiAgICAgICAgICAgIHBsYXRmb3JtTWFuYWdlclN0b3JlLmVtaXRDaGFuZ2UoKTtcbiAgICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgQUNUSU9OX1RZUEVTLkNMRUFSX0FVVEhPUklaQVRJT046XG4gICAgICAgICAgICBfYXV0aG9yaXphdGlvbiA9IG51bGw7XG4gICAgICAgICAgICBzZXNzaW9uU3RvcmFnZS5yZW1vdmVJdGVtKCdhdXRob3JpemF0aW9uJyk7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5DSEFOR0VfUEFHRTpcbiAgICAgICAgICAgIF9wYWdlID0gYWN0aW9uLnBhZ2U7XG4gICAgICAgICAgICBsb2NhdGlvbi5oYXNoID0gJyMnICsgYWN0aW9uLnBhZ2U7XG4gICAgICAgICAgICBwbGF0Zm9ybU1hbmFnZXJTdG9yZS5lbWl0Q2hhbmdlKCk7XG4gICAgICAgICAgICBicmVhaztcblxuICAgICAgICBjYXNlIEFDVElPTl9UWVBFUy5SRUNFSVZFX1BMQVRGT1JNUzpcbiAgICAgICAgICAgIF9wbGF0Zm9ybXMgPSBhY3Rpb24ucGxhdGZvcm1zO1xuICAgICAgICAgICAgcGxhdGZvcm1NYW5hZ2VyU3RvcmUuZW1pdENoYW5nZSgpO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgfVxufSk7XG5cbm1vZHVsZS5leHBvcnRzID0gcGxhdGZvcm1NYW5hZ2VyU3RvcmU7XG4iXX0=
