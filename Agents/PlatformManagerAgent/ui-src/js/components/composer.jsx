'use strict';

var React = require('react');
var uuid = require('node-uuid');

var Composer = React.createClass({
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
            <div className="composer">
                <textarea
                    key={this.state.id}
                    onChange={this._handleTextareaChange}
                    defaultValue={JSON.stringify(this.state.request, null, '    ')}
                />
                <input
                    ref="send"
                    type="button"
                    value="Send"
                    disabled={!this.state.valid}
                    onClick={this._handleSendClick}
                />
            </div>
        );
    },
});

module.exports = Composer;
