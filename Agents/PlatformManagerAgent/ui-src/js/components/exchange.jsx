'use strict';
var React = require('react');

var rpc = require('../lib/rpc');

var Exchange = React.createClass({
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
                responseTime = <div className="time">{this._formatTime(exchange.responseReceived)}</div>;
            }

            responseText = this._formatMessage(exchange.response);
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
