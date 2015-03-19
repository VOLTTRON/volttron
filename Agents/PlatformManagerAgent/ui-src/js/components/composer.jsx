'use strict';

var React = require('react');

var composerStore = require('../stores/composer-store.js');
var messengerActionCreators = require('../action-creators/messenger-action-creators');
var Request = require('../lib/rpc').Request;

var Composer = React.createClass({
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
            <div className="composer">
                <textarea
                    key={this.state.id}
                    onChange={this._handleTextareaChange}
                    defaultValue={JSON.stringify(this.state.request, null, '    ')}
                />
                <input
                    className="button"
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

function getStateFromStores() {
    var request = composerStore.getRequest();

    return {
        id: request.toJSON().id,
        request: request,
        valid: true,
    };
}

module.exports = Composer;
