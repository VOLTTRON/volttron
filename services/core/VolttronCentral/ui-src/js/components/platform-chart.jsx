'use strict';

var React = require('react');
var moment = require('moment');
var OutsideClick = require('react-click-outside');

import ControlButton from './control-button';
import {Line} from 'react-chartjs-2';

var platformChartStore = require('../stores/platform-chart-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var ConfirmForm = require('./confirm-form');

var PlatformChart = React.createClass({
    getInitialState: function () {
        var state = {};

        state.refreshInterval = this.props.chart.refreshInterval;
        state.pinned = this.props.chart.pinned;

        state.refreshing = false;

        return state;
    },
    componentDidMount: function () {
        this._refreshChartTimeout = setTimeout(this._refreshChart, 0);
        platformChartStore.addChangeListener(this._onStoresChange);


    },
    componentWillUnmount: function () {
        clearTimeout(this._refreshChartTimeout);
        platformChartStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        this.setState({refreshing: false});

        if (this.props.chart.series.length > 0)
        {
            var refreshInterval = platformChartStore.getRefreshRate(this.props.chartKey);

            if (refreshInterval !== this.state.refreshInterval)
            {
                this.setState({refreshInterval: refreshInterval}); 

                clearTimeout(this._refreshChartTimeout);
                this._refreshChartTimeout = setTimeout(this._refreshChart, refreshInterval);
            }
        }
    },
    // _initializeChart: function () {
    //     if (this.props.hasOwnProperty("chart"))
    //     {
    //         this.setState({refreshing: true});

    //         platformChartActionCreators.initializeChart(
    //             this.props.chart.series,
    //             this.props.chart.dataLength
    //         );

    //         if (this.state.refreshInterval) {
    //             this._refreshChartTimeout = setTimeout(this._refreshChart, this.state.refreshInterval);
    //         }    
    //     }
    // },
    _refreshChart: function () {
        if (this.props.hasOwnProperty("chart"))
        {
            this.setState({refreshing: true});

            platformChartActionCreators.refreshChart(
                this.props.chart.series,
                this.props.chart.dataLength
            );

            if (this.state.refreshInterval) {
                this._refreshChartTimeout = setTimeout(this._refreshChart, this.state.refreshInterval);
            }    
        }
    },
    _removeChart: function () {
        var deleteChart = function () {
            modalActionCreators.closeModal();

            this.props.chart.series.forEach(function (series) {
                if (series.hasOwnProperty("path"))
                {
                    platformsPanelActionCreators.checkItem(series.path, false);
                }
            });

            platformChartActionCreators.removeChart(this.props.chartKey);
            platformActionCreators.saveCharts();
        }

        modalActionCreators.openModal(
            <ConfirmForm
              promptTitle="Delete chart"
              preText="Remove "
              promptText={this.props.chartKey}
              postText=" chart from here and from Dashboard?"
              confirmText="Delete"
              onConfirm={deleteChart.bind(this)}
            >
            </ConfirmForm>
        );
    },
    render: function () {
        var chartSeries = this.props.chart.series; 
        var platformChart;

        var removeButton;

        if (!this.props.hideControls)
        {
            removeButton = (
                <div className="remove-chart" onClick={this._removeChart}>
                    <i className="fa fa-remove"></i>
                </div>
            );
        }

        var refreshingIcon;

        if (this.state.refreshing)
        {
            refreshingIcon = <span className="refreshIcon"><i className="fa fa-refresh fa-spin fa-fw"></i></span>;
        } 

        var containerStyle = {
            width: "100%",
            textAlign: "center"
        }

        var innerStyle = {
            width: (this.props.chartKey.length > 10 ? this.props.chartKey.length * 10 : 100) + "px",
            marginLeft: "auto",
            marginRight: "auto"
        }
        
        if (chartSeries)
        {
            if (chartSeries.length > 0)
            {
                platformChart = (
                    <div className="platform-chart with-3d-shadow with-transitions absolute_anchor">
                        <div style={containerStyle}>
                            <div className="absolute_anchor" style={innerStyle}>
                                <label className="chart-title">{this.props.chartKey}</label> 
                                {refreshingIcon}
                            </div>
                        </div>
                        {removeButton}
                        <div>
                            <div className='viz'>        
                                { chartSeries.length != 0 ? 
                                    <GraphLineChart 
                                      key={this.props.chartKey}
                                      series={chartSeries}
                                      name={this.props.chartKey}
                                      hideControls={this.props.hideControls}
                                      refreshInterval={this.props.chart.refreshInterval}
                                      dataLength={this.props.chart.dataLength}
                                      pinned={this.props.chart.pinned}
                                      chartType={this.props.chart.type}
                                    /> : null }
                            </div>
                            <br/>
                        </div>
                    </div>
                );
            }
        }

        return (
            <div ref={function (div) {
                this.container = div;
            }.bind(this)}>
                {platformChart}
            </div>
        );
    },
});

var GraphLineChart = OutsideClick(React.createClass({
    getInitialState: function () {
        
        var pattern = /[!@#$%^&*()+\-=\[\]{};':"\\|, .<>\/?]/g

        var state = {};

        state.chartName = "vc_" + this.props.name.replace(" / ", "_") + '_chart';
        state.chartName = state.chartName.replace(pattern, "_");
        state.pinned = this.props.pinned;
        state.chartType = this.props.chartType;
        state.showTaptip = false;
        state.taptipX = 0;
        state.taptipY = 0;
        state.tooltipX = 0;
        state.tooltipY = 0;
        state.tooltipContent = "";

        return state;
    },
    componentDidMount: function() {
        platformChartStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformChartStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState({pinned: platformChartStore.getPinned(this.props.name)});
        this.setState({chartType: platformChartStore.getType(this.props.name)});
    },
    handleClickOutside: function () {      
        
        this.setState({ showTooltip: false });
    },
    _onChartChange: function (e) {

        var chartType = e.target.value;

        this.setState({showTaptip: false});

        platformChartActionCreators.setType(this.props.name, chartType);

        if (this.state.pinned)
        {
            platformActionCreators.saveCharts();
        }
    },
    _onPinToggle: function () {

        var pinned = !this.state.pinned;

        platformChartActionCreators.pinChart(this.props.name);

        platformActionCreators.saveCharts();
    },
    _onRefreshChange: function (e) {
        platformChartActionCreators.changeRefreshRate(e.target.value, this.props.name);

        if (this.state.pinned)
        {
            platformActionCreators.saveCharts();
        }
    },
    _onLengthChange: function (e) {
        platformChartActionCreators.changeDataLength(e.target.value, this.props.name);

        if (this.state.pinned)
        {
            platformActionCreators.saveCharts();
        }
    },
    render: function() {

        var chartStyle = {
            width: "90%"
        }

        var svgStyle = {
            padding: "0px 50px"
        }

        var controlStyle = {
            width: "100%",
            textAlign: "left"
        }

        var pinClasses = ["chart-pin inlineBlock"];
        pinClasses.push(this.state.pinned ? "pinned-chart" : "unpinned-chart");
    
        var controlButtons;

        if (!this.props.hideControls)
        {
            var taptipX = 0;
            var taptipY = -100;

            var tooltipX = 0;
            var tooltipY = -80;

            var chartTypeSelect = (
                <select
                  onChange={this._onChartChange}
                  value={this.state.chartType}
                  autoFocus
                  required
                >
                    <option value="line">Line</option>
                    <option value="stacked">Stacked Area</option>
                </select>
            );

            var chartTypeTaptip = { 
                "title": "Chart Type", 
                "content": chartTypeSelect,
                "x": taptipX,
                "y": taptipY
            };
            var chartTypeIcon = (
                <i className="fa fa-line-chart"></i>
            );
            var chartTypeTooltip = {
                "content": "Chart Type",
                "x": tooltipX,
                "y": tooltipY
            };

            var chartTypeControlButton = (
                <ControlButton 
                  name={this.state.chartName + "_chartTypeControlButton"}
                  taptip={chartTypeTaptip} 
                  tooltip={chartTypeTooltip}
                  icon={chartTypeIcon}
                >
                </ControlButton>
            );

            
            var pinChartIcon = (
                <div className={pinClasses.join(' ')}>
                    <i className="fa fa-thumb-tack"></i>
                </div>
            );
            var pinChartTooltip = {
                "content": "Pin to Dashboard",
                "x": tooltipX - 20,
                "y": tooltipY
            };

            var pinChartControlButton = (
                <ControlButton 
                  name={this.state.chartName + "_pinChartControlButton"}
                  icon={pinChartIcon}
                  tooltip={pinChartTooltip}
                  clickAction={this._onPinToggle}
                >
                </ControlButton>
            );
            
            var refreshChart = (
                <div>
                    <input
                      type="number"
                      onChange={this._onRefreshChange}
                      value={this.props.refreshInterval}
                      min="15000"
                      step="1000"
                      placeholder="disabled"
                    /> (ms)
                    <br/>
                    <span>
                        Omit to disable
                    </span>
                </div>
            );

            var refreshChartTaptip = { 
                "title": "Refresh Rate", 
                "content": refreshChart,
                "x": taptipX + 15,
                "y": taptipY - 10
            };
            var refreshChartIcon = (
                <i className="fa fa-hourglass"></i>
            );
            var refreshChartTooltip = {
                "content": "Refresh Rate",
                "x": tooltipX + 10,
                "y": tooltipY
            };

            var refreshChartControlButton = (
                <ControlButton 
                  name={this.state.chartName + "_refreshChartControlButton"}
                  taptip={refreshChartTaptip}
                  tooltip={refreshChartTooltip}
                  icon={refreshChartIcon}
                >
                </ControlButton>
            );

            var dataLength = (
                <div>
                    <input
                      type="number"
                      onChange={this._onLengthChange}
                      value={this.props.dataLength}
                      min="1"
                      step="1"
                    />
                    <br/>
                </div>
            );

            var lengthIcon = (
                <i className="fa fa-arrows-h"></i>
            );

            var dataLengthTaptip = { 
                "title": "Data Length", 
                "content": dataLength,
                "x": taptipX + 15,
                "y": taptipY
            };

            var dataLengthTooltip = { 
                "content": "Data Length",
                "x": tooltipX + 40,
                "y": tooltipY
            };  

            var dataLengthControlButton = ( 
                <ControlButton
                  name={this.state.chartName + "_dataLengthControlButton"}
                  taptip={dataLengthTaptip}
                  tooltip={dataLengthTooltip}
                  icon={lengthIcon}
                >
                </ControlButton>
            );

            tooltipX = tooltipX + 20;

            var spaceStyle = {
                width: "20px",
                height: "2px"
            }

            controlButtons = (
                <div className="displayBlock"style={controlStyle}>
                    {pinChartControlButton}
                    {chartTypeControlButton}
                    {refreshChartControlButton}
                    {dataLengthControlButton}
                    <div className="inlineBlock" style={spaceStyle}>
                    </div>
                </div>
            );
        }

        var rdcChart, leftLabel, rightLabel;

        if (this.props.series.length && this.props.series[0].data)
        {
            var labels = this.props.series[0].data.map(function (datum) {
                return datum[0];
            });

            var data = {
                labels: labels,
                datasets: this.props.series.map(function (item) {
                    
                    var mappedColor;
                    var lighterColor;
                    var lightestColor;

                    if (item.hasOwnProperty('colors'))
                    {
                        mappedColor = item.colors.color;
                        lighterColor = item.colors.lighter;
                        lightestColor = item.colors.lightest;
                    }
                    else
                    {
                        mappedColor = 'rgba(0,0,0,1)';
                        lighterColor = 'rgba(0,0,0,0.8)';
                        lightestColor = 'rgba(0,0,0,0.3)';
                    }

                    return {
                        label: item.parentPath,
                        data: item.data.map(function (datum) {
                            return datum[1];
                        }),
                        fill: this.state.chartType === 'stacked',
                        lineTension: 0.1,
                        backgroundColor: lightestColor,
                        borderColor: lighterColor,
                        borderCapStyle: 'butt',
                        borderDash: [],
                        borderDashOffset: 0.0,
                        borderJoinStyle: 'miter',
                        pointBorderColor: lighterColor,
                        pointBackgroundColor: '#fff',
                        pointBorderWidth: 1,
                        pointHoverRadius: 5,
                        pointHoverBackgroundColor: lighterColor,
                        pointHoverBorderColor: mappedColor,
                        pointHoverBorderWidth: 2,
                        pointRadius: 1,
                        pointHitRadius: 10
                    };
                }, this)
                .sort(function(a, b) {
                    if (a.label && b.label)
                    {
                        if (a.label < b.label)
                        {
                            return -1;
                        }
                        else if (a.label > b.label)
                        {
                            return 1;
                        }
                        else
                        {
                            return 0;
                        }
                    }
                    else
                    {
                        return 0;
                    }
                })
            }

            var convertTitle = function (tooltipItem, data) {
                return moment(Number(tooltipItem[0].xLabel)).format('MMM d, YYYY, h:mm:ss a');
            };

            var options = {
                scales: {                    
                    xAxes: [{
                        display: false
                    }],
                    yAxes: [{
                        stacked: this.state.chartType === 'stacked'
                    }]
                },
                tooltips: {
                    backgroundColor: '#eaebed',
                    titleFontColor: 'black',
                    bodyFontColor: 'black',
                    callbacks: {
                        title: convertTitle
                    }
                }
            };

            rdcChart = (
                <Line 
                  height={100} 
                  width={700} 
                  label={this.props.name}
                  data={data}
                  options={options}
                />
            );

            var leftText = moment(Number(labels[0])).fromNow();
            var rightText = moment(Number(labels[labels.length - 1])).fromNow();

            leftLabel = <div className="axis-label bottom-left">{leftText}</div>;
            rightLabel = <div className="axis-label bottom-right">{rightText}</div>;
        };

        return (
            <div style={chartStyle}
                ref={this.state.chartName}>
                <div className='absolute_anchor'>
                    <div className="chart-container">
                        {rdcChart}
                    </div>
                    {leftLabel}
                    {rightLabel}
                </div>
                <div className='absolute_anchor'>
                    {controlButtons}
                </div>
            </div>
        );
    }
}));

module.exports = PlatformChart;
