'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var Chart = require('./chart');

var Dashboard = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var charts;

        if (!this.state.platforms) {
            charts = (
                <p>Loading charts...</p>
            );
        } else {
            charts = [];

            this.state.platforms.forEach(function (platform) {
                if (!platform.charts) { return; }

                platform.charts
                    .filter(function (chart) { return chart.pinned; })
                    .forEach(function (chart) {
                        var key = [
                            platform.uuid,
                            chart.topic,
                            chart.type,
                        ].join('::');

                        charts.push(
                            <div key={key} className="view__item chart chart--dashboard">
                                <h3 className="chart__title">
                                    <Router.Link
                                        to="platform"
                                        params={{uuid: platform.uuid}}
                                    >
                                        {platform.name}
                                    </Router.Link>
                                    : {chart.topic}
                                </h3>
                                <Chart
                                    platform={platform}
                                    chart={chart}
                                />
                            </div>
                        );
                    });
            });

            if (!charts.length) {
                charts = (
                    <p className="empty-help">
                        Pin a platform chart to have it appear on the dashboard
                    </p>
                );
            }
        }

        return (
            <div className="view view--tiled">
                <h2>Dashboard</h2>
                <div className="view__items">
                    {charts}
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

module.exports = Dashboard;
