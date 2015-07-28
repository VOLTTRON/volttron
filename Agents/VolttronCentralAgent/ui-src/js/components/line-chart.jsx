'use strict';

var d3 = require('d3');
var moment = require('moment');
var React = require('react');

var LineChart = React.createClass({
    getInitialState: function () {
        var initialState = {
            data: this.props.data,
            xDates: false,
        };

        if (this.props.data.length &&
            typeof this.props.data[0][0] === 'string' &&
            Date.parse(this.props.data[0][0] + 'Z')) {
            initialState.data = this.props.data.map(function (value) {
                return[Date.parse(value[0] + 'Z'), value[1]];
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
            data: newProps.data,
            xDates: false,
        };

        if (newProps.data.length &&
            typeof newProps.data[0][0] === 'string' &&
            Date.parse(newProps.data[0][0] + 'Z')) {
            newState.data = newProps.data.map(function (value) {
                return[Date.parse(value[0] + 'Z'), value[1]];
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
        var contents = [];

        if (this._width && this._height) {
            contents.push(
                <path
                    key="xAxis"
                    className="axis"
                    strokeLinecap="square"
                    d={'M3,' + (this._height - 19) + 'L' + (this._width - 3) + ',' + (this._height - 19)}
                />
            );

            contents.push(
                <path
                    key="yAxis"
                    className="axis"
                    strokeLinecap="square"
                    d={'M3,17L3,' + (this._height - 19)}
                />
            );

            if (!this.state.data.length) {
                contents.push(
                    <text
                        key="noData"
                        className="no-data-text"
                        x={this._width / 2}
                        y={this._height / 2}
                        textAnchor="middle"
                    >
                        No data available
                    </text>
                );
            } else {
                var xRange = d3.extent(this.state.data, function (d) { return d[0]; });
                var yMin = (this.props.chart.min === 0 || this.props.chart.min) ?
                    this.props.chart.min : d3.min(this.state.data, function (d) { return d[1]; });
                var yMax = (this.props.chart.max === 0 || this.props.chart.max) ?
                    this.props.chart.max : d3.max(this.state.data, function (d) { return d[1]; });

                var x = d3.scale.linear()
                    .range([4, this._width - 4])
                    .domain(xRange);
                var y = d3.scale.linear()
                    .range([this._height - 20, 18])
                    .domain([yMin, yMax]);

                var line = d3.svg.line()
                    .x(function (d) { return x(d[0]); })
                    .y(function (d) { return y(d[1]); });

                contents.push(
                    <text
                        key="xMinLabel"
                        className="label"
                        x="2"
                        y={this._height - 4}
                    >
                        {this.state.xDates ? moment(xRange[0]).fromNow() : xRange[0]}
                    </text>
                );

                contents.push(
                    <text
                        key="xMaxLabel"
                        className="label"
                        x={this._width - 2}
                        y={this._height - 4}
                        textAnchor="end"
                    >
                        {this.state.xDates ? moment(xRange[1]).fromNow() : xRange[1]}
                    </text>
                );

                contents.push(
                    <text
                        key="yMaxLabel"
                        className="label" x="2" y="10">
                        {yMax}
                    </text>
                );

                contents.push(
                    <path
                        key="line"
                        className="line"
                        strokeLinecap="round"
                        d={line(this.state.data)}
                    />
                );

                this.state.data.forEach(function (d, index) {
                    var text;

                    if (this.state.xDates) {
                        text = d[1]  + ' @ ' + moment(d[0]).format('MMM D, YYYY h:mm:ss A');
                    } else {
                        text = d.join(', ');
                    }

                    contents.push(
                        <g key={'point' + index} className="dot">
                            <circle className="outer" cx={x(d[0])} cy={y(d[1])} r="4"/>
                            <circle className="inner" cx={x(d[0])} cy={y(d[1])} r="2"/>
                            <text
                                x={this._width / 2}
                                y="10"
                                textAnchor="middle"
                            >
                                {text}
                            </text>
                        </g>
                    );
                }, this);
            }
        }

        return (
            <svg className="chart__svg chart__svg--line" ref="svg">
                {contents}
            </svg>
        );
    },
});

module.exports = LineChart;
