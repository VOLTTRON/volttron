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
            platforms = (
                <ul>
                    {this.state.platforms.map(function (platform) {
                        return (
                            <li>
                                {platform.name} ({platform.uuid})
                                <ul>
                                    {platform.agents.map(function (agent) {
                                        return (
                                            <li>{agent.name} ({agent.uuid})</li>
                                        );
                                    })}
                                </ul>
                            </li>
                        );
                    })}
                </ul>
            );
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
