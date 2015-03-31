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
        return (
            <div className="home">
                {this.state.platforms.length ?
                <ul>
                    {this.state.platforms.map(function (platform) {
                        return (
                            <li>
                                {platform.platform} ({platform.uuid})
                                <ul>
                                    {platform.agents.map(function (agent) {
                                        return (
                                            <li>{agent.agent} ({agent.uuid})</li>
                                        );
                                    })}
                                </ul>
                            </li>
                        );
                    })}
                </ul>
                :
                <p>No platforms found.</p>
                }
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
