'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Home = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
        setTimeout(platformManagerActionCreators.loadPlatforms);
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
                                </tr>
                            </thead>
                            <tbody>
                                {platform.agents.map(function (agent) {
                                    return (
                                        <tr key={agent.uuid}>
                                            <td>{agent.name}</td>
                                            <td>{agent.uuid}</td>
                                            <td>{agent.lastStatus || 'Retrieving status...'}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    );
                }

                return (
                    <div className="platform" key={platform.uuid}>
                        <h2>{platform.name} ({platform.uuid})</h2>
                        {agents}
                    </div>
                );
            });
        }

        return (
            <div className="home">
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

module.exports = Home;
