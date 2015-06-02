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
            platforms = this.state.platforms.map(function (platform) {
                return (
                    <div className="platform" key={platform.uuid}>
                        <Router.Link to="platform" params={{uuid: platform.uuid}}>
                            {platform.name}
                        </Router.Link>
                        &nbsp;({platform.uuid})
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
        platforms: platformsStore.getPlatforms(),
    };
}

module.exports = Platforms;
