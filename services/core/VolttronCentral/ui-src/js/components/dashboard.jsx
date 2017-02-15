'use strict';

var React = require('react');
var Router = require('react-router');
var platformChartStore = require('../stores/platform-chart-store');

var PlatformChart = require('./platform-chart');

var reloadPageInterval = 1800000;

var Dashboard = React.createClass({
    getInitialState: function () {
        var state = getStateFromStores();

        this._reloadPageTimeout = setTimeout(this._reloadPage, reloadPageInterval);

        return state;
    },
    componentDidMount: function () {
        platformChartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        clearTimeout(this._reloadPageTimeout);
        platformChartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _reloadPage: function () {
        //Reload page to clear leaked memory
        location.reload(true);
    },
    render: function () {
        
        var pinnedCharts = this.state.platformCharts; 

        var platformCharts = [];

        pinnedCharts.forEach(function (pinnedChart) {
            if (pinnedChart.data.length > 0)
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
