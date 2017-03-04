'use strict';

var React = require('react');
var Router = require('react-router');
var platformChartStore = require('../stores/platform-chart-store');

var PlatformChart = require('./platform-chart');

var Dashboard = React.createClass({
    getInitialState: function () {
        var state = getStateFromStores();

        return state;
    },
    componentDidMount: function () {
        platformChartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformChartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _reloadPage: function () {
        location.reload(true);
    },
    render: function () {
        
        var pinnedCharts = this.state.platformCharts; 

        var platformCharts = [];

        pinnedCharts.forEach(function (pinnedChart) {
            if (pinnedChart.series.length > 0)
            {
                var platformChart = <PlatformChart key={pinnedChart.chartKey} chart={pinnedChart} chartKey={pinnedChart.chartKey} hideControls={true}/>
                platformCharts.push(platformChart);
            }
        });        

        if (pinnedCharts.length === 0) {
            platformCharts = (
                <p className="empty-help">
                    Pin a chart to have it appear on the dashboard
                </p>
            );
        }

        return (
            <div className="view">
                <h2>Dashboard</h2>
                {platformCharts}
                
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platformCharts: platformChartStore.getPinnedCharts()
    };
}

module.exports = Dashboard;
