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
        var agent = this.props.agent, status, action, remove, notAllowed;

        if (agent.actionPending === undefined) {
            status = 'Retrieving status...';
        } else if (agent.actionPending) {
            if (agent.process_id === null || agent.return_code !== null) {
                status = 'Starting...';
                action = (
                    <input className="button button--agent-action" type="button" value="Start" disabled />
                );
            } else {
                status = 'Stopping...';
                action = (
                    <input className="button button--agent-action" type="button" value="Stop" disabled />
                );
            }
        } else {

            if (agent.process_id === null) {
                status = 'Never started';
                
                if (agent.permissions.can_start)
                {
                    action = (
                        <input className="button button--agent-action" type="button" value="Start" onClick={this._onStart} />
                    );
                }
                else
                {
                    action = (
                        <input className="button button--agent-action" type="button" value="Start" onClick={this._onStart} disabled/>
                    );
                } 
            } else if (agent.return_code === null) {
                status = 'Running (PID ' + agent.process_id + ')';
                
                if (agent.permissions.can_stop)
                {
                    action = (
                        <input className="button button--agent-action" type="button" value="Stop" onClick={this._onStop} />
                    );
                }
                else
                {
                    action = (
                        <input className="button button--agent-action" type="button" value="Stop" onClick={this._onStop} disabled/>
                    );
                }                 
            } else {
                status = 'Stopped (returned ' + agent.return_code + ')';
                
                if (agent.permissions.can_restart)
                {
                    action = (
                        <input className="button button--agent-action" type="button" value="Start" onClick={this._onStart} />
                    );
                }
                else
                {
                    action = (
                        <input className="button button--agent-action" type="button" value="Start" onClick={this._onStart} disabled/>
                    );
                } 
            }
        }

        if (agent.permissions.can_remove)
        {
            remove = ( <input className="button button--agent-action" type="button" value="Remove" onClick={this._onRemove} /> );
        }
        else
        {
            remove = ( <input className="button button--agent-action" type="button" value="Remove" onClick={this._onRemove} disabled/> );
        } 

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
