'use strict';

var React = require('react');

var messengerActionCreators = require('../action-creators/messenger-action-creators');

var Composer = React.createClass({
    getInitialState: function () {
        return {
            id: Date.now(),
            request: {
                method: null,
                params: null,
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
            <div className="composer">
                <textarea
                    key={this.state.id}
                    onChange={this._onTextareaChange}
                    defaultValue={JSON.stringify(this.state.request, null, '    ')}
                />
                <input
                    className="button"
                    ref="send"
                    type="button"
                    value="Send"
                    disabled={!this.state.valid}
                    onClick={this._onSendClick}
                />
            </div>
        );
    },
});

module.exports = Composer;
