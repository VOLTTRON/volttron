'use strict';

var d3 = require('d3');
var React = require('react');

var LineChart = React.createClass({
    getInitialState: function () {
        var initialState = {
            points: this.props.points,
            xDates: false,
        };

        if (this.props.points.length &&
            typeof this.props.points[0][0] === 'string' &&
            Date.parse(this.props.points[0][0])) {
            initialState.points = this.props.points.map(function (value) {
                return[Date.parse(value[0]), value[1]];
            });
            initialState.xDates = true;
        }

        return initialState;
    },
    componentDidMount: function () {
        this._updateSize();
        window.addEventListener('resize', this._onResize);
    },
    componentWillReceiveProps: function (newProps) {
        var newState = {
            points: newProps.points,
            xDates: false,
        };

        if (newProps.points.length &&
            typeof newProps.points[0][0] === 'string' &&
            Date.parse(newProps.points[0][0])) {
            newState.points = newProps.points.map(function (value) {
                return[Date.parse(value[0]), value[1]];
            });
            newState.xDates = true;
        }

        this.setState(newState);
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
        var xAxis, yAxis, path;

        if (this._width && this._height && this.state.points.length) {
            var xRange = d3.extent(this.state.points, function (d) { return d[0]; });
            var yMin = (this.props.chart.min === 0 || this.props.chart.min) ?
                this.props.chart.min : d3.min(this.state.points, function (d) { return d[1]; });
            var yMax = (this.props.chart.max === 0 || this.props.chart.max) ?
                this.props.chart.max : d3.max(this.state.points, function (d) { return d[1]; });

            var x = d3.scale.linear()
                .range([0, this._width - 2])
                .domain(xRange);
            var y = d3.scale.linear()
                .range([this._height - 2, 0])
                .domain([yMin, yMax]);

            var line = d3.svg.line()
                .x(function (d) { return x(d[0]) + 1; })
                .y(function (d) { return y(d[1]) + 1; });

            xAxis = (
                <path className="axis" d={line([[xRange[0], yMin], [xRange[0], yMax]])} />
            );

            yAxis = (
                <path className="axis" d={line([[xRange[0], yMin], [xRange[1], yMin]])} />
            );

            path = (
                <path className="line" d={line(this.state.points)} />
            );
        }

        return (
            <svg className="chart__svg chart__svg--line" ref="svg">
                {xAxis}
                {yAxis}
                {path}
            </svg>
        );
    },
});

module.exports = LineChart;
