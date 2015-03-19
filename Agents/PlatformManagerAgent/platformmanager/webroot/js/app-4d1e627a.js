(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');

var PlatformManager = require('./components/platform-manager');

React.render(
    React.createElement(PlatformManager, null),
    document.getElementById('app')
);


},{"./components/platform-manager":11,"react":undefined}],2:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var messengerActionCreators = {
    makeRequest: function (request) {
        var exchange = {
            requestSent: Date.now(),
            request: request,
        };

        dispatcher.dispatch({
            type: ACTION_TYPES.CREATE_EXCHANGE,
            exchange: exchange,
        });

        request.call()
            .then(function (response) {
                exchange.responseReceived = Date.now();
                exchange.response = response;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            })
            .catch(rpc.ResponseError, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            })
            .catch(rpc.RequestError, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            });
    }
};

module.exports = messengerActionCreators;


},{"../constants/action-types":12,"../dispatcher":13,"../lib/rpc":14}],3:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    requestAuthorization: function (username, password) {
        var request = new rpc.Request({
            method: 'getAuthorization',
            params: {
                username: username,
                password: password,
            },
        });

        request.call()
            .then(function (response) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS,
                    authorization: response.result,
                });
            })
            .catch(rpc.ResponseError, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REQUEST_AUTHORIZATION_FAIL,
                    error: error.response.error,
                });
            });
    },
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
};

module.exports = platformManagerActionCreators;


},{"../constants/action-types":12,"../dispatcher":13,"../lib/rpc":14}],4:[function(require,module,exports){
'use strict';

var React = require('react');

var composerStore = require('../stores/composer-store.js');
var messengerActionCreators = require('../action-creators/messenger-action-creators');
var Request = require('../lib/rpc').Request;

var Composer = React.createClass({displayName: "Composer",
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        composerStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        composerStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    shouldComponentUpdate: function (newProps, newState) {
        return (this.state.id !== newState.id || this.state.valid !== newState.valid);
    },
    _handleSendClick: function () {
        messengerActionCreators.makeRequest(this.state.request);
    },
    _handleTextareaChange: function (e) {
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

        this.setState({ request: new Request(parsed), valid: true });
    },
    render: function () {
        return (
            React.createElement("div", {className: "composer"}, 
                React.createElement("textarea", {
                    key: this.state.id, 
                    onChange: this._handleTextareaChange, 
                    defaultValue: JSON.stringify(this.state.request, null, '    ')}
                ), 
                React.createElement("input", {
                    className: "button", 
                    ref: "send", 
                    type: "button", 
                    value: "Send", 
                    disabled: !this.state.valid, 
                    onClick: this._handleSendClick}
                )
            )
        );
    },
});

function getStateFromStores() {
    var request = composerStore.getRequest();

    return {
        id: request.toJSON().id,
        request: request,
        valid: true,
    };
}

module.exports = Composer;


},{"../action-creators/messenger-action-creators":2,"../lib/rpc":14,"../stores/composer-store.js":19,"react":undefined}],5:[function(require,module,exports){
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


},{"../stores/messenger-store":21,"./exchange":6,"jquery":undefined,"react":undefined}],6:[function(require,module,exports){
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


},{"../lib/rpc":14,"react":undefined}],7:[function(require,module,exports){
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


},{"../action-creators/platform-manager-action-creators":3,"react":undefined}],8:[function(require,module,exports){
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
                React.createElement("h1", null, "PlatformManager"), 
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


},{"../action-creators/platform-manager-action-creators":3,"../stores/login-form-store":20,"react":undefined}],9:[function(require,module,exports){
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


},{"./composer":4,"./conversation":5,"react":undefined}],10:[function(require,module,exports){
'use strict';

var React = require('react');

var LogOutButton = require('./log-out-button');

var Navigation = React.createClass({displayName: "Navigation",
    render: function () {
        return (
            React.createElement("div", {className: "navigation"}, 
                React.createElement("h1", null, "PlatformManager"), 
                React.createElement(LogOutButton, null)
            )
        );
    }
});

module.exports = Navigation;


},{"./log-out-button":7,"react":undefined}],11:[function(require,module,exports){
'use strict';

var React = require('react');

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
                React.createElement(Messenger, null)
            )
        );
    }
});

function getStateFromStores() {
    return { loggedIn: (platformManagerStore.getAuthorization() !== null ) };
}

module.exports = PlatformManager;


},{"../stores/platform-manager-store":22,"./login-form":8,"./messenger":9,"./navigation":10,"react":undefined}],12:[function(require,module,exports){
'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
    REQUEST_AUTHORIZATION: null,
    REQUEST_AUTHORIZATION_SUCCESS: null,
    REQUEST_AUTHORIZATION_FAIL: null,

    CLEAR_AUTHORIZATION: null,

    CREATE_EXCHANGE: null,
    UPDATE_EXCHANGE: null,
});


},{"react/lib/keyMirror":undefined}],13:[function(require,module,exports){
'use strict';

var Dispatcher = require('flux').Dispatcher;

module.exports = new Dispatcher();


},{"flux":undefined}],14:[function(require,module,exports){
'use strict';

var Request = require ('./request');
var RequestError = require ('./request-error');
var ResponseError = require ('./response-error');

module.exports = {
    Request: Request,
    RequestError: RequestError,
    ResponseError: ResponseError,
};


},{"./request":16,"./request-error":15,"./response-error":17}],15:[function(require,module,exports){
'use strict';

function RequestError(message) {
    this.name = 'RequestError';
    this.message = message;
}
RequestError.prototype = Object.create(Error.prototype);
RequestError.prototype.constructor = RequestError;

RequestError.prototype.toJSON = function () {
    return this.message;
};

module.exports = RequestError;


},{}],16:[function(require,module,exports){
'use strict';

var jQuery = require('jquery');
var Promise = require('bluebird');
var uuid = require('node-uuid');

var RequestError = require ('./request-error');
var ResponseError = require ('./response-error');

function Request(opts) {
    if (!this instanceof Request) {
        return new Request(opts);
    }

    opts = opts || {};

    this._request = {
        jsonrpc: '2.0',
        method: opts.method || null,
        params: opts.params || null,
        authorization: opts.authorization || null,
        id: uuid.v1(),
    };
}

Request.prototype.method = function (method) {
    if (method === undefined) {
        return this._request.method;
    }

    this._request.method = method;
};

Request.prototype.params = function (params) {
    if (params === undefined) {
        return clone(this._request.params);
    }

    this._request.params = params;
};

Request.prototype.authorization = function (authorization) {
    if (authorization === undefined) {
        return this._request.authorization;
    }

    this._request.authorization = authorization;
};

Request.prototype.toJSON = function () {
    var obj = clone(this._request);

    if (obj.params === null) {
        delete obj.params;
    }

    if (obj.authorization === null) {
        delete obj.authorization;
    }

    return obj;
};

Request.prototype.call = function () {
    var self = this;

    return new Promise(function (resolve, reject) {
        var request = self.toJSON();

        jQuery.ajax({
            method: 'POST',
            url: '/jsonrpc',
            contentType: 'application/json',
            data: JSON.stringify(request),
            timeout: 60000,
            success: function (response) {
                response = ordered(response);

                if (response.error) {
                    reject(new ResponseError(response));
                }

                resolve(response);
            },
            error: function (response, type) {
                switch (type) {
                case 'error':
                    reject(new RequestError('Server returned ' + response.status + ' status'));
                    break;
                case 'timeout':
                    reject(new RequestError('Request timed out'));
                    break;
                default:
                    reject(new RequestError('Request failed: ' + type));
                }
            }
        });
    });
};

function clone(obj) {
    // stringify + parse for deep clone
    return JSON.parse(JSON.stringify(obj));
}

function ordered(response) {
    var orderedResponse = { jsonrpc: '2.0' };

    if (response.error) {
        orderedResponse.error = {
            code: response.error.code,
            message: response.error.message,
        };

        if (response.error.data) {
            orderedResponse.error.data = response.error.data;
        }
    } else {
        orderedResponse.result = response.result;
    }

    orderedResponse.id = response.id;

    return orderedResponse;
}

module.exports = Request;


},{"./request-error":15,"./response-error":17,"bluebird":undefined,"jquery":undefined,"node-uuid":undefined}],17:[function(require,module,exports){
'use strict';

function ResponseError(response) {
    this.name = 'RequestError';
    this.message = response.error.message;
    this.response = response;
}
ResponseError.prototype = Object.create(Error.prototype);
ResponseError.prototype.constructor = ResponseError;

ResponseError.prototype.toJSON = function () {
    return this.response;
};

module.exports = ResponseError;


},{}],18:[function(require,module,exports){
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

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var messengerStore = require('./messenger-store');
var platformManagerStore = require('../stores/platform-manager-store');
var Request = require('../lib/rpc/request');
var Store = require('../lib/store');

var _request;

function _initRequest(method, params) {
    _request = new Request({
        method: method,
        params: params,
        authorization: platformManagerStore.getAuthorization()
    });
}

_initRequest();

var composerStore = new Store();

composerStore.getRequest = function () {
    return _request;
};

composerStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([messengerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
            _initRequest();
            composerStore.emitChange();
            break;

        case ACTION_TYPES.CREATE_EXCHANGE:
            _initRequest(action.exchange.request.method(), action.exchange.request.params());
            composerStore.emitChange();
            break;
    }
});

module.exports = composerStore;


},{"../constants/action-types":12,"../dispatcher":13,"../lib/rpc/request":16,"../lib/store":18,"../stores/platform-manager-store":22,"./messenger-store":21}],20:[function(require,module,exports){
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
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
            _lastError = null;
            loginFormStore.emitChange();
            break;

        case ACTION_TYPES.REQUEST_AUTHORIZATION_FAIL:
            _lastError = action.error;
            loginFormStore.emitChange();
            break;
    }
});

module.exports = loginFormStore;


},{"../constants/action-types":12,"../dispatcher":13,"../lib/store":18,"./platform-manager-store":22}],21:[function(require,module,exports){
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
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
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


},{"../constants/action-types":12,"../dispatcher":13,"../lib/store":18,"./platform-manager-store":22}],22:[function(require,module,exports){
'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _authorization = sessionStorage.getItem('authorization');

var platformManagerStore = new Store();

platformManagerStore.getAuthorization = function () {
    return _authorization;
};

platformManagerStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
            _authorization = action.authorization;
            sessionStorage.setItem('authorization', _authorization);
            platformManagerStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _authorization = null;
            sessionStorage.removeItem('authorization');
            platformManagerStore.emitChange();
            break;
    }
});

module.exports = platformManagerStore;


},{"../constants/action-types":12,"../dispatcher":13,"../lib/store":18}]},{},[1]);
