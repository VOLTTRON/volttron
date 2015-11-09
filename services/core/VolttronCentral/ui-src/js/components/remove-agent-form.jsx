'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');

var RemoveAgentForm = React.createClass({
    getInitialState: function () {
        var state = {};

        for (var prop in this.props.agent) {
            state[prop] = this.props.agent[prop];
        }

        return state;
    },
    _onPropChange: function (e) {
        var state = {};

        this.setState(state);
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        platformActionCreators.removeAgent(/*this.props.platform, this.props.chart, this.state*/);
    },
    render: function () {
        var agentInfo = {
            method: 'platforms.uuid.' + this.props.platform.uuid + '.remove_agent',
            params: [this.props.agent.uuid],
            authorization: 'someAuthorizationToken',
        };

        var agentInfoString = '{method: ' + agentInfo.method + ', params: [' + agentInfo.params + '] , authorization: ' + 
            agentInfo.authorization + '}';

        

        return (
            <form className="remove-agent-form" onSubmit={this._onSubmit}>
                <div >{agentInfoString}</div>
                <div className="form__actions">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                    >
                        Cancel
                    </button>
                    <button
                        className="button"
                        disabled={!this.state.topic || !this.state.type}
                    >
                        Save
                    </button>
                </div>
            </form>
        );
    },
});

module.exports = RemoveAgentForm;
