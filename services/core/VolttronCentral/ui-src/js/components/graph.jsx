'use strict';

var React = require('react');
var Router = require('react-router');
// var d3 = require('d3');
var nv = require('react-nvd3');


var graphStore = require('../stores/graph-store');

var Graph = React.createClass({
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        
    },
    componentDidMount: function () {
        graphStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        graphStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var graphs  = [];        

        nv.addGraph(function() {
            var chart = nv.models.lineWithFocusChart();
            chart.brushExtent([50,70]);
            chart.xAxis.tickFormat(d3.format(',f')).axisLabel("Stream - 3,128,.1");
            chart.x2Axis.tickFormat(d3.format(',f'));
            chart.yAxis.tickFormat(d3.format(',.2f'));
            chart.y2Axis.tickFormat(d3.format(',.2f'));
            chart.useInteractiveGuideline(true);
            d3.select('#chart svg')
                .datum(testData())
                .call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        });

        return (
                <div className="view">
                    <div id="chart" class='with-3d-shadow with-transitions'>
                        <svg></svg>
                    </div>

                </div>
        );
    },
});

function getStateFromStores() {
    return {
        graphs: graphStore.getGraphs(),
    };
}

function testData() {
    return stream_layers(3,128,.1).map(function(data, i) {
        return {
            key: 'Stream' + i,
            area: i === 1,
            values: data
        };
    });
}

function stream_layers(n, m, o) {
    if (arguments.length < 3) o = 0;
    function bump(a) {
    var x = 1 / (.1 + Math.random()),
        y = 2 * Math.random() - .5,
        z = 10 / (.1 + Math.random());
    for (var i = 0; i < m; i++) {
      var w = (i / m - y) * z;
      a[i] += x * Math.exp(-w * w);
    }
    }
    return d3.range(n).map(function() {
      var a = [], i;
      for (i = 0; i < m; i++) a[i] = o + o * Math.random();
      for (i = 0; i < 5; i++) bump(a);
      return a.map(stream_index);
    });
    }

    /* Another layer generator using gamma distributions. */
    function stream_waves(n, m) {
    return d3.range(n).map(function(i) {
    return d3.range(m).map(function(j) {
        var x = 20 * j / m - i / 3;
        return 2 * x * Math.exp(-.5 * x);
      }).map(stream_index);
    });
    }

    function stream_index(d, i) {
    return {x: i, y: Math.max(0, d)};
}

module.exports = Graph;
