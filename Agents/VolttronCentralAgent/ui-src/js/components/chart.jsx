'use strict';

var React = require('react');

var topicDataStore = require('../stores/topic-data-store');
var platformActionCreators = require('../action-creators/platform-action-creators');
var LineChart = require('./line-chart');

var chartTypes = {
    'line': LineChart,
};

var Chart = React.createClass({
    getInitialState: function () {
        return getStateFromStores(this.props.platform, this.props.chart);
    },
    componentDidMount: function () {
        topicDataStore.addChangeListener(this._onStoreChange);

        if (!this._getTopicDataTimeout) {
            this._getTopicDataTimeout = setTimeout(this._getTopicData, 0);
        }
    },
    componentWillUnmount: function () {
        topicDataStore.removeChangeListener(this._onStoreChange);
        clearTimeout(this._getTopicDataTimeout);
    },
    _initTopicData: function () {

    },
    _onStoreChange: function () {
        this.setState(getStateFromStores(this.props.platform, this.props.chart));
    },
    _getTopicData: function () {
        platformActionCreators.getTopicData(
            this.props.platform,
            this.props.chart.topic
        );

        if (this.props.chart.refreshInterval) {
            this._getTopicDataTimeout = setTimeout(this._getTopicData, this.props.chart.refreshInterval);
        }
    },
    render: function () {
        var ChartClass = chartTypes[this.props.chart.type];

        return (
            <ChartClass
                className="chart"
                chart={this.props.chart}
                data={this.state.data || []}
            />
        );
    },
});

function getStateFromStores(platform, chart) {
    return { data: topicDataStore.getTopicData(platform, chart.topic) };
}

module.exports = Chart;
