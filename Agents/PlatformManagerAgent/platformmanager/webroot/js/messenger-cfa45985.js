(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');
var MessengerModel = require('./messenger-model');

var model = new MessengerModel();

var App = React.createClass({displayName: "App",
    render: function () {
        return (
            React.createElement("div", {className: "messenger"}, 
                React.createElement(Conversation, {exchanges: this.props.model.exchanges}), 
                React.createElement(Composer, {sendRequestFn: this.props.model.sendRequest.bind(this.props.model)})
            )
        );
    }
});

model.addSubscriber(render);

function render() {
    React.render(
        React.createElement(App, {model: model}),
        document.getElementById('messenger')
    );
}

render();


},{"./composer":2,"./conversation":3,"./messenger-model":5,"react":undefined}],2:[function(require,module,exports){
'use strict';

var React = require('react');
var uuid = require('node-uuid');

var Composer = React.createClass({displayName: "Composer",
    getInitialState: function () {
        return Composer.getDefaultState();
    },
    shouldComponentUpdate: function (newProps, newState) {
        return (this.state.id !== newState.id || this.state.valid !== newState.valid);
    },
    statics: {
        getDefaultState: function () {
            var id = uuid.v1();

            return {
                id: id,
                request: {
                    jsonrpc: '2.0',
                    method: 'getAuthorization',
                    params: { username: 'dorothy', password: 'toto123' },
                    id: id,
                },
                valid: true,
            };
        },
    },
    _handleSendClick: function () {
        this.props.sendRequestFn(this.state.request);

        this.setState(Composer.getDefaultState());
    },
    _handleTextareaChange: function (e) {
        var request;

        try {
            request = JSON.parse(e.target.value);
        } catch (ex) {
            if (ex instanceof SyntaxError) {
                this.setState({ request: null, valid: false });
                return;
            } else {
                throw ex;
            }
        }

        this.setState({ request: request, valid: true });
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

module.exports = Composer;


},{"node-uuid":undefined,"react":undefined}],3:[function(require,module,exports){
'use strict';

var $ = require('jquery');
var React = require('react');

var Exchange = require('./exchange');

var Conversation = React.createClass({displayName: "Conversation",
    componentDidMount: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }
    },
    componentDidUpdate: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    render: function () {
        return (
            React.createElement("div", {ref: "conversation", className: "conversation"}, 
                this.props.exchanges.map(function (exchange, index) {
                    return (
                        React.createElement(Exchange, {key: index, exchange: exchange})
                    );
                })
            )
        );
    }
});

module.exports = Conversation;


},{"./exchange":4,"jquery":undefined,"react":undefined}],4:[function(require,module,exports){
'use strict';
var React = require('react');

var Exchange = React.createClass({displayName: "Exchange",
    _formatTime: function (time) {
        var d = new Date();

        d.setTime(time);

        return d.toLocaleString();
    },
    _formatMessage: function (message) {
        var ordered = {};

        ['jsonrpc', 'method', 'params', 'authorization', 'error', 'result', 'id'].forEach(function (key) {
            if (key in message) {
                if (key === 'error') {
                    ordered.error = {};

                    ['code', 'message', 'data'].forEach(function (errorKey) {
                        if (errorKey in message.error) {
                            ordered.error[errorKey] = message.error[errorKey];
                        }
                    });
                } else {
                    ordered[key] = message[key];
                }
            }
        });

        return JSON.stringify(ordered, null, '    ');
    },
    render: function () {
        var exchange = this.props.exchange;
        var responseClass = 'response';
        var responseTime, responseText;

        switch (typeof exchange.response) {
        case 'object':
            if ('error' in exchange.response) {
                responseClass += ' response--error';
            }

            responseTime = React.createElement("div", {className: "time"}, this._formatTime(exchange.responseReceived));
            responseText = this._formatMessage(exchange.response);
            break;
        case 'string':
            responseClass += ' response--error';
            responseText = exchange.response;
            break;
        case 'undefined':
            responseClass += ' response--pending';
            responseText = 'Waiting for response...';
            break;
        default:
            responseClass += ' response--error';
            responseText = 'Unrecognized response type: ' + typeof exchange.response;
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


},{"react":undefined}],5:[function(require,module,exports){
'use strict';

var $ = require('jquery');

var MessengerModel = function () {
    if (!this instanceof MessengerModel) {
        return new MessengerModel();
    }

    this.exchanges = [];
    this.subscribers = [];
};

MessengerModel.prototype.addSubscriber = function (subscriber) {
    if (this.subscribers.indexOf(subscriber) < 0) {
        this.subscribers.push(subscriber);
    }
};

MessengerModel.prototype.notifySubscribers = function () {
    this.subscribers.forEach(function (subscriber) {
        subscriber();
    });
};

MessengerModel.prototype.sendRequest = function (request) {
    var exchange = {
        requestSent: Date.now(),
        request: request,
    };

    this.exchanges.push(exchange);
    this.notifySubscribers();

    var model = this;

    $.ajax({
        method: 'POST',
        url: '/jsonrpc',
        data: JSON.stringify(request),
        contentType: 'application/json',
        timeout: 60000,
        success: function (response) {
            exchange.responseReceived = Date.now();
            exchange.response = response;
            model.notifySubscribers();
        },
        error: function (response, type) {
            switch (type) {
            case 'error':
                exchange.response = 'Server returned ' + response.status + ' status';
                break;
            case 'timeout':
                exchange.response = 'Request timed out';
                break;
            default:
                exchange.response = 'Request failed: ' + type;
            }

            model.notifySubscribers();
        }
    });
};

module.exports = MessengerModel;


},{"jquery":undefined}]},{},[1]);
