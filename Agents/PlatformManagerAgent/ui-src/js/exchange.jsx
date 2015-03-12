'use strict';
var React = require('react');

var Exchange = React.createClass({
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

            responseTime = <div className="time">{this._formatTime(exchange.responseReceived)}</div>;
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
            <div className="exchange">
                <div className="request">
                    <div className="time">{this._formatTime(exchange.requestSent)}</div>
                    <pre>{this._formatMessage(exchange.request)}</pre>
                </div>
                <div className={responseClass}>
                    {responseTime}
                    <pre>{responseText}</pre>
                </div>
            </div>
        );
    }
});

module.exports = Exchange;
