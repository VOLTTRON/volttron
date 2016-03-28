'use strict';

var React = require('react');
var Router = require('react-router');

var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsStore = require('../stores/platforms-store');
var RegisterPlatformForm = require('../components/register-platform-form');
var StatusForm = require('../components/status-indicator');
var DeregisterPlatformConfirmation = require('../components/deregister-platform-confirmation');

var Platforms = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onGoodStatusClick: function () {
        statusIndicatorActionCreators.openStatusIndicator("success", "nothing happened");
    },
    _onBadStatusClick: function () {
        statusIndicatorActionCreators.openStatusIndicator("error", "nothing happened");
    },
    _onRegisterClick: function () {
        modalActionCreators.openModal(<RegisterPlatformForm />);
    },
    _onDeregisterClick: function (platform) {
        modalActionCreators.openModal(<DeregisterPlatformConfirmation platform={platform} />);
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
                        <div
                            key={platform.uuid}
                            className="view__item view__item--list"
                        >
                            <h3>
                                <Router.Link
                                    to="platform"
                                    params={{uuid: platform.uuid}}
                                >
                                    {platform.name}
                                </Router.Link>
                            </h3>
                            <button
                                className="deregister-platform"
                                onClick={this._onDeregisterClick.bind(this, platform)}
                                title="Deregister platform"
                            >
                                &times;
                            </button>
                            <code>{status.join(' | ')}</code>
                        </div>
                    );
                }, this);
        }

        return (
            <div className="view">
                <div className="absolute_anchor">
                    <h2>Platforms</h2>
                    <div className="view__actions">
                        <button className="button" onClick={this._onGoodStatusClick}>
                            Show Good Status
                        </button>
                        &nbsp;
                        <button className="button" onClick={this._onBadStatusClick}>
                            Show Bad Status
                        </button>
                        &nbsp;
                        <button className="button" onClick={this._onRegisterClick}>
                            Register platform
                        </button>
                    </div>
                    {platforms}
                </div>
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
