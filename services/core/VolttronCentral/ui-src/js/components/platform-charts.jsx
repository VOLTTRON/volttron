'use strict';

var React = require('react');
var Router = require('react-router');
var PlatformChart = require('./platform-chart');

// var chartStore = require('../stores/platform-chart-store');

var PlatformCharts = React.createClass({
    // getInitialState: getStateFromStores,
    componentDidMount: function () {
        // chartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        // chartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        // this.setState(getStateFromStores());
    },
    render: function () {
        // var charts  = [];

        var platformChart = <PlatformChart/>

        return (
                <div>
                    <div className="view">
                        <h2>Points</h2>
                        {platformChart}
                    </div>
                </div>
        );
    },
});



module.exports = PlatformCharts;
