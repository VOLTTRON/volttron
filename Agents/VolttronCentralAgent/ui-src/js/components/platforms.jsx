'use strict';

var React = require('react');

var AgentRow = require('./agent-row');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Platforms = React.createClass({
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var platforms;

        if (!this.state.platforms) {
            platforms = (
                <p>Loading platforms...</p>
            );
        } else if (!this.state.platforms.length) {
            platforms = (
                <p>No platforms found.</p>
            );
        } else {
            platforms = this.state.platforms.map(function (platform) {
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
                    <div className="platform" key={platform.uuid}>
                        <h3>{platform.name} ({platform.uuid})</h3>
                        {agents}
                    </div>
                );
            });
        }

        return (
            <div className="view">
                <h2>Platforms</h2>
                {platforms}
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformManagerStore.getPlatforms(),
    };
}

module.exports = Platforms;
