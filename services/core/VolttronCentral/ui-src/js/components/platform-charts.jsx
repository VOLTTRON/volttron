'use strict';

var React = require('react');
var PlatformChart = require('./platform-chart');
var chartStore = require('../stores/platform-chart-store');

var PlatformCharts = React.createClass({
    getInitialState: function () {

        var state = {
            chartData: chartStore.getData(),
            modalContent: null
        };

        return state;
    },
    componentDidMount: function () {
        chartStore.addChangeListener(this._onChartStoreChange);
    },
    componentWillUnmount: function () {
        chartStore.removeChangeListener(this._onChartStoreChange);
    },
    _onChartStoreChange: function () {
        this.setState({chartData: chartStore.getData()});
    },
    render: function () {

        var chartData = this.state.chartData; 

        var platformCharts = [];

        for (var key in chartData)
        {
            if (chartData[key].data.length > 0)
            {
                var platformChart = <PlatformChart key={key} chart={chartData[key]} chartKey={key} hideControls={false}/>
                platformCharts.push(platformChart);
            }
        }

        if (platformCharts.length === 0)
        {
            var noCharts = <p className="empty-help">No charts have been loaded.</p>
            platformCharts.push(noCharts);
        }

        return (
            <div className="view">
                <div className="absolute_anchor">
                    <div className="view__actions">
                    </div>
                    <h2>Charts</h2>
                    {platformCharts}
                </div>
            </div>
        );
    },
});

module.exports = PlatformCharts;
