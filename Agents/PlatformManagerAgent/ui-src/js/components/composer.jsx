'use strict';

var React = require('react');

var consoleActionCreators = require('../action-creators/console-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Composer = React.createClass({
    getInitialState: function () {
        return {
            id: Date.now(),
            request: {
                method: platformManagerStore.getPage(),
                authorization: platformManagerStore.getAuthorization(),
            },
            valid: true,
        };
    },
    shouldComponentUpdate: function (newProps, newState) {
        return (this.state.id !== newState.id || this.state.valid !== newState.valid);
    },
    _onSendClick: function () {
        consoleActionCreators.makeRequest(this.state.request);

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
                authorization: parsed.authorization,
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
