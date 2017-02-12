'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
var d3 = require('d3');;
var NVD3Chart = require('react-nvd3');
var moment = require('moment');
var OutsideClick = require('react-click-outside');

import ControlButton from './control-button';

var chartStore = require('../stores/platform-chart-store');
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

        if (this.props.chart.data.length > 0)
        {

            var refreshInterval = platformChartStore.getRefreshRate(this.props.chart.data[0].name);

            if (refreshInterval !== this.state.refreshInterval)
            {
                this.setState({refreshInterval: refreshInterval}); 

                clearTimeout(this._refreshChartTimeout);
                this._refreshChartTimeout = setTimeout(this._refreshChart, refreshInterval);
            }
        }
    },
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
                onConfirm={deleteChart.bind(this)}>
            </ConfirmForm>
        );
    },
    render: function () {
        var chartData = this.props.chart; 
        var platformChart;

        var removeButton;

        if (!this.props.hideControls)
        {
            removeButton = (
              <div className="remove-chart"
                  onClick={this._removeChart}>
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
            width: (chartData.data[0].name.length > 10 ? chartData.data[0].name.length * 10 : 100) + "px",
            marginLeft: "auto",
            marginRight: "auto"
        }

        if (chartData)
        {
            if (chartData.data.length > 0)
            {
                platformChart = (
                  <div className="platform-chart with-3d-shadow with-transitions absolute_anchor">
                      <div style={containerStyle}>
                        <div className="absolute_anchor" style={innerStyle}>
                            <label className="chart-title">{chartData.data[0].name}</label> 
                            {refreshingIcon}
                        </div>
                      </div>
                      {removeButton}
                      <div>
                          <div className='viz'>        
                              { chartData.data.length != 0 ? 
                                    <GraphLineChart 
                                        key={this.props.chartKey}
                                        data={chartData.data}
                                        name={this.props.chartKey}
                                        hideControls={this.props.hideControls}
                                        refreshInterval={this.props.chart.refreshInterval}
                                        dataLength={this.props.chart.dataLength}
                                        max={chartData.max}
                                        min={chartData.min}
                                        pinned={this.props.chart.pinned}
                                        chartType={this.props.chart.type} /> : null }
                          </div>
                          <br/>
                      </div>
                  </div>)
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
      state.min = (this.props.min ? this.props.min : d3.min(this.props.data, function (d) {return d["1"]}));
      state.max = (this.props.max ? this.props.max : d3.max(this.props.data, function (d) {return d["1"]}));

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

      var min = platformChartStore.getMin(this.props.name);
      var max = platformChartStore.getMax(this.props.name);

      this.setState({min: (min ? min : d3.min(this.props.data, function (d) {return d["1"]}))});
      this.setState({max: (max ? max : d3.max(this.props.data, function (d) {return d["1"]}))});      
  },
  handleClickOutside: function () {      
      var tooltips = document.querySelectorAll(".nvtooltip");

      for (var i = 0; i < tooltips.length; i++)
      {
        tooltips[i].style.opacity = 0;
      }
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
  _onMinChange: function (e) {
      var min = e.target.value;
      
      platformChartActionCreators.setMin(min, this.props.name);

      if (this.state.pinned)
      {
          platformActionCreators.saveCharts();
      }
  },
  _onMaxChange: function (e) {
      var max = e.target.value;
      
      platformChartActionCreators.setMax(max, this.props.name);

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
        var taptipY = 40;

        var tooltipX = 0;
        var tooltipY = 80;

        var chartTypeSelect = (
            <select
                onChange={this._onChartChange}
                value={this.state.chartType}
                autoFocus
                required
            >
                <option value="lineChart">Line</option>
                <option value="lineWithFocusChart">Line with View Finder</option>
                <option value="stackedAreaChart">Stacked Area</option>
                <option value="cumulativeLineChart">Cumulative Line</option>
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
                icon={chartTypeIcon}></ControlButton>
        );

        
        var pinChartIcon = (
            <div className={pinClasses.join(' ')}>
                <i className="fa fa-thumb-tack"></i>
            </div>
        );
        var pinChartTooltip = {
            "content": "Pin to Dashboard",
            "x": tooltipX,
            "y": tooltipY
        };

        var pinChartControlButton = (
            <ControlButton 
                name={this.state.chartName + "_pinChartControlButton"}
                icon={pinChartIcon}
                tooltip={pinChartTooltip}
                clickAction={this._onPinToggle}></ControlButton>
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
            "x": taptipX,
            "y": taptipY
        };
        var refreshChartIcon = (
            <i className="fa fa-hourglass"></i>
        );
        var refreshChartTooltip = {
            "content": "Refresh Rate",
            "x": tooltipX,
            "y": tooltipY
        };

        var refreshChartControlButton = (
            <ControlButton 
                name={this.state.chartName + "_refreshChartControlButton"}
                taptip={refreshChartTaptip}
                tooltip={refreshChartTooltip}
                icon={refreshChartIcon}></ControlButton>
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
            "x": taptipX,
            "y": taptipY
        };

        var dataLengthTooltip = { 
            "content": "Data Length",
            "x": tooltipX - 10,
            "y": tooltipY
        };  

        var dataLengthControlButton = ( 
            <ControlButton
              name={this.state.chartName + "_dataLengthControlButton"}
              taptip={dataLengthTaptip}
              tooltip={dataLengthTooltip}
              icon={lengthIcon}></ControlButton>
        );

        var chartMin = (
            <div>
                <input
                    type="number"
                    onChange={this._onMinChange}
                    value={this.state.min}
                    step="1"
                />
            </div>
        );

        var chartMinTaptip = { 
            "title": "Y Axis Min", 
            "content": chartMin,
            "x": taptipX,
            "y": taptipY
        };
        var chartMinIcon = (
            <div className="moveMin">
                <span>&#9644;</span>
            </div>
        );

        tooltipX = tooltipX + 20;

        var chartMinTooltip = {
            "content": "Y Axis Min",
            "x": tooltipX,
            "y": tooltipY
        };

        var chartMinControlButton = (
            <ControlButton 
                name={this.state.chartName + "_chartMinControlButton"}
                taptip={chartMinTaptip}
                tooltip={chartMinTooltip}
                icon={chartMinIcon}></ControlButton>
        );

        var chartMax = (
            <div>
                <input
                    type="number"
                    onChange={this._onMaxChange}
                    value={this.state.max}
                    step="1"
                />
            </div>
        );

        var chartMaxTaptip = { 
            "title": "Y Axis Max", 
            "content": chartMax,
            "x": taptipX,
            "y": taptipY
        };
        var chartMaxIcon = (
            <div className="moveMax">
                <span>&#9644;</span>
            </div>
        );

        tooltipX = tooltipX + 20;

        var chartMaxTooltip = {
            "content": "Y Axis Max",
            "x": tooltipX,
            "y": tooltipY
        };

        var chartMaxControlButton = (
            <ControlButton 
                name={this.state.chartName + "_chartMaxControlButton"}
                taptip={chartMaxTaptip}
                tooltip={chartMaxTooltip}
                icon={chartMaxIcon}></ControlButton>
        );

        var spaceStyle = {
            width: "20px",
            height: "2px"
        }

        controlButtons = (
            <div className="displayBlock"
                style={controlStyle}>
                {pinChartControlButton}
                {chartTypeControlButton}
                {refreshChartControlButton}
                {dataLengthControlButton}
                {chartMinControlButton}
                {chartMaxControlButton}
                <div className="inlineBlock"
                    style={spaceStyle}></div>
            </div>
        );
    }

    var graphData = [{
      key: "test1",
      color: '#ff7f0e',
      values: this.props.data.map(function (item) {
        return {x: item[0], y: item[1]};
      })
    }];

    var tickCount = 0;
    var nvChart;

    switch(this.state.chartType)
    {
      case "lineWithFocusChart":

        nvChart = (
          <NVD3Chart
            key={this.state.chartName}
            xAxis={{
              tickFormat: function (d, i) {

                var tickValue;

                if (typeof i === "undefined")
                {
                    if (tickCount === 0)
                    {
                        tickValue = moment(d).fromNow();
                        tickCount++;
                    }
                    else if (tickCount === 1)
                    {
                        tickValue = moment(d).fromNow();
                        tickCount = 0;
                    }
                }
                else
                {
                    tickValue = "";
                }

                return tickValue;
              },
              axisLabel: 'Time'
            }}
            x2Axis={{
              tickFormat: function (d) { return d3.time.format('%X')(new Date(d)); }
            }}
            yAxis={{
              tickFormat: function(d) {return parseFloat(d).toFixed(1); }
            }}
            type={this.state.chartType}
            datum={graphData}
            x='x'
            y='y'
            duration={1}
            margin={{
              left: 200
            }}
            renderEnd={function(){
              console.log('renderEnd');
            }}/>
        );
        break;

      default:
        nvChart = (
          <NVD3Chart
            key={this.state.chartName}
            xAxis={{
              tickFormat: function (d, i) {

                var tickValue;

                if (typeof i === "undefined")
                {
                    if (tickCount === 0)
                    {
                        tickValue = moment(d).fromNow();
                        tickCount++;
                    }
                    else if (tickCount === 1)
                    {
                        tickValue = moment(d).fromNow();
                        tickCount = 0;
                    }
                }
                else
                {
                    tickValue = "";
                }

                return tickValue;
            },
              axisLabel: 'Period'
            }}
            yAxis={{
              tickFormat: function(d) {return parseFloat(d).toFixed(1); }
            }}
            type={this.state.chartType}
            datum={graphData}
            x='x'
            y='y'
            duration={1}
            margin={{
              left: 200
            }}
            renderEnd={function(){
              console.log('renderEnd');
            }}/>
        );
        break;
    }

    return (
      <div className='absolute_anchor'
          style={chartStyle}
          ref={this.state.chartName}>
          {nvChart}
          {controlButtons}
      </div>
    );
  }
  
}));




module.exports = PlatformChart;
