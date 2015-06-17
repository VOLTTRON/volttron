'use strict';

var d3 = require('d3');
var React = require('react');

var PercentChart = React.createClass({
    componentDidMount: function () {
        this._updateSize();
        window.addEventListener('resize', this._onResize);
    },
    componentWillUpdate: function () {
        this._updateSize();
    },
    componentWillUnmount: function () {
        window.removeEventListener('resize', this._onResize);
    },
    _onResize: function () {
        this.forceUpdate();
    },
    _updateSize: function () {
        var computedStyles = window.getComputedStyle(React.findDOMNode(this.refs.svg));
        this._width = parseInt(computedStyles.width, 10);
        this._height = parseInt(computedStyles.height, 10);
    },
    render: function () {
        var path;

        if (this._width && this._height) {
            var x = d3.scale.linear()
                .range([0, this._width - 2])
                .domain(d3.extent(this.props.points, function (d) { return d[0]; }));
            var y = d3.scale.linear()
                .range([this._height - 2, 0])
                .domain([0, 100]);

            var line = d3.svg.line()
                .x(function (d) { return x(d[0]) + 1; })
                .y(function (d) { return y(d[1]) + 1; });

            path = (
                <path d={line(this.props.points)} />
            );
        }

        return (
            <svg ref="svg">
                {path}
            </svg>
        );
    },
});

module.exports = PercentChart;
