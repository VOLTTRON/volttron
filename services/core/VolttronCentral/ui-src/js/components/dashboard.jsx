'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var Chart = require('./chart');
var EditChartForm = require('./edit-chart-form');
var modalActionCreators = require('../action-creators/modal-action-creators');

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
    _onEditChartClick: function (platform, chart) {
        modalActionCreators.openModal(<EditChartForm platform={platform} chart={chart} />);
    },
    render: function () {
        var charts;

        if (!this.state.platforms) {
            charts = (
                <p>Loading charts...</p>
            );
        } else {
            charts = [];

            this.state.platforms
                .sort(function (a, b) {
                    return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
                })
                .forEach(function (platform) {
                    if (!platform.charts) { return; }

                    platform.charts
                        .filter(function (chart) { return chart.pin; })
                        .forEach(function (chart) {
                            var key = [
                                platform.uuid,
                                chart.topic,
                                chart.type,
                            ].join('::');

                            charts.push(
                                <div key={key} className="view__item view__item--tile chart">
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
                                    <div className="chart__actions">
                                        <a
                                            className="chart__edit"
                                            onClick={this._onEditChartClick.bind(this, platform, chart)}
                                        >
                                            Edit
                                        </a>
                                    </div>
                                </div>
                            );
                        }, this);
                }, this);

            if (!charts.length) {
                charts = (
                    <p className="empty-help">
                        Pin a platform chart to have it appear on the dashboard
                    </p>
                );
            }
        }

        return (
            <div className="view">
                <h2>Dashboard</h2>
                {charts}
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
