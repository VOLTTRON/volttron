'use strict';

var React = require('react');

var Exchange = React.createClass({
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
            <div className="exchange">
                <div className="request">
                    <div className="time">{this._formatTime(exchange.initiated)}</div>
                    <pre>{this._formatMessage(exchange.request)}</pre>
                </div>
                <div className={classes.join(' ')}>
                    {exchange.completed && <div className="time">{this._formatTime(exchange.completed)}</div>}
                    <pre>{responseText}</pre>
                </div>
            </div>
        );
    }
});

module.exports = Exchange;
