'use strict';

var React = require('react');
var PlatformChart = require('./platform-chart');
var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var NewChartForm = require('./new-chart-form');
var chartStore = require('../stores/platform-chart-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var PlatformCharts = React.createClass({
    getInitialState: function () {

        var state = {
            chartData: chartStore.getData()
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
    _onAddChartClick: function () {

        platformActionCreators.loadChartTopics();
        modalActionCreators.openModal(<NewChartForm/>);
    },
    render: function () {

        var chartData = this.state.chartData; 

        var platformCharts = [];

        for (var key in chartData)
        {
            if (chartData[key].data.length > 0)
            {
                var platformChart = (<PlatformChart key={key} 
                                        chart={chartData[key]} 
                                        chartKey={key} 
                                        hideControls={false}/>);
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
                        <button
                            className="button"
                            onClick={this._onAddChartClick}
                        >
                            Add Chart
                        </button>
                    </div>
                    <h2>Charts</h2>
                    {platformCharts}
                </div>
            </div>
        );
    },
});

module.exports = PlatformCharts;
