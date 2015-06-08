'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platforms = React.createClass({
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
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
            platforms = this.state.platforms
                .sort(function (a, b) {
                    if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                    if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                    return 0;
                })
                .map(function (platform) {
                    var status = [platform.uuid];

                    if (platform.agents) {
                        var running = 0;
                        var stopped = 0;

                        platform.agents.forEach(function (agent) {
                            if (agent.process_id !== null) {
                                if (agent.return_code === null) {
                                    running++;
                                } else {
                                    stopped++;
                                }
                            }
                        });

                        status.push('Agents: ' + running + ' running, ' + stopped + ' stopped, ' + platform.agents.length + ' installed');
                    }

                    return (
                        <Router.Link
                            key={platform.uuid}
                            to="platform"
                            params={{uuid: platform.uuid}}
                            className="view__item"
                        >
                            <h3>{platform.name}</h3>
                            <code>{status.join(' | ')}</code>
                        </Router.Link>
                    );
                });
        }

        return (
            <div className="view view--list">
                <h2>Platforms</h2>
                {platforms}
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformsStore.getPlatforms(),
    };
}

module.exports = Platforms;
