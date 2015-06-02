'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Platform = React.createClass({
    mixins: [Router.State],
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores.call(this));
    },
    _onFileChange: function (e) {
        var file = e.target.files[0];

        if (file) {
            var reader = new FileReader();
            var platform = this.state.platform;

            reader.onload = function () {
                platformManagerActionCreators.installAgent(
                    platform,
                    {
                        name: file.name,
                        data: reader.result,
                    }
                );
            };

            reader.readAsDataURL(file);
        }

    },
    render: function () {
        if (!this.state.platform) {
            return (
                <p>Platform not found.</p>
            );
        }

        var platform = this.state.platform;
        var agents;

        if (!platform.agents) {
            agents = (
                <p>Loading agents...</p>
            );
        } else if (!platform.agents.length) {
            agents = (
                <p>No agents installed.</p>
            );
        } else {
            agents = (
                <table>
                    <thead>
                        <tr>
                            <th>Agent</th>
                            <th>UUID</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {platform.agents.map(function (agent) {
                            return (
                                <AgentRow
                                    key={agent.uuid}
                                    platform={platform}
                                    agent={agent} />
                            );
                        })}
                    </tbody>
                </table>
            );
        }

        return (
            <div className="view" key={platform.uuid}>
                <h2>{platform.name} ({platform.uuid})</h2>
                <h3>Agents</h3>
                {agents}
                <h3>Install agent</h3>
                <input type="file" onChange={this._onFileChange} />
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platform: platformManagerStore.getPlatform(this.getParams().uuid),
    };
}

module.exports = Platform;
