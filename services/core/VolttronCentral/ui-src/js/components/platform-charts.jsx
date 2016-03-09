'use strict';

var React = require('react');
var Router = require('react-router');
var PlatformChart = require('./platform-chart');

var chartStore = require('../stores/platform-chart-store');

var PlatformCharts = React.createClass({
    getInitialState: function () {
        var state = {
            chartData: getChartsFromStores()
        };

        return state;
    },
    componentWillMount: function () {
        
    },
    componentDidMount: function () {
        chartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        chartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        var platformCharts = getChartsFromStores();

        this.setState({chartData: platformCharts});
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

        return (
                <div>
                    <div className="view">
                        <h2>Points</h2>
                        {platformCharts}
                    </div>
                </div>
        );
    },
});

function getChartsFromStores() {

    return chartStore.getData();
}

module.exports = PlatformCharts;
