'use strict';

var React = require('react');

var platformActionCreators = require('../action-creators/platform-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');

var RemoveAgentForm = require('./remove-agent-form');

var AgentRow = React.createClass({
    _onStop: function () {
        platformActionCreators.stopAgent(this.props.platform, this.props.agent);
    },
    _onStart: function () {
        platformActionCreators.startAgent(this.props.platform, this.props.agent);
    },
    _onRemove: function () {
        modalActionCreators.openModal(<RemoveAgentForm platform={this.props.platform} agent={this.props.agent} />);
    },
    render: function () {
        var agent = this.props.agent, status, action, remove;

        if (agent.actionPending === undefined) {
            status = 'Retrieving status...';
        } else if (agent.actionPending) {
            if (agent.process_id === null || agent.return_code !== null) {
                status = 'Starting...';
                action = (
                    <input className="button" type="button" value="Start" disabled />
                );
            } else {
                status = 'Stopping...';
                action = (
                    <input className="button" type="button" value="Stop" disabled />
                );
            }
        } else {
            if (agent.process_id === null) {
                status = 'Never started';
                action = (
                    <input className="button" type="button" value="Start" onClick={this._onStart} />
                );
            } else if (agent.return_code === null) {
                status = 'Running (PID ' + agent.process_id + ')';
                action = (
                    <input className="button" type="button" value="Stop" onClick={this._onStop} />
                );
            } else {
                status = 'Stopped (returned ' + agent.return_code + ')';
                action = (
                    <input className="button" type="button" value="Start" onClick={this._onStart} />
                );
            }
        }

        remove = ( <input className="button" type="button" value="Remove" onClick={this._onRemove} /> );

        return (
            <tr>
                <td>{agent.name}</td>
                <td>{agent.uuid}</td>
                <td>{status}</td>
                <td>{action} {remove}</td>
            </tr>
        );
    },
});

module.exports = AgentRow;
