'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');
var moment = require('moment');


var chartStore = require('../stores/platform-chart-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var ConfirmForm = require('./confirm-form');
var ControlButton = require('./control-button');

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
                this.props.chart.series
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
            <div>
                {platformChart}
            </div>
        );
    },
});


var GraphLineChart = React.createClass({
  mixins: [
      require('react-onclickoutside')
  ],
  getInitialState: function () {
      
      var pattern = /[!@#$%^&*()+\-=\[\]{};':"\\|, .<>\/?]/g

      var state = {};

      state.chartName = this.props.name.replace(" / ", "_") + '_chart';
      state.chartName = state.chartName.replace(pattern, "_");
      state.lineChart = null;
      state.pinned = this.props.pinned;
      state.chartType = this.props.chartType;
      state.showTaptip = false;
      state.taptipX = 0;
      state.taptipY = 0;
      state.min = (this.props.min ? this.props.min : d3.min(this.props.data, function (d) {return d["1"]}));
      state.max = (this.props.max ? this.props.max : d3.max(this.props.data, function (d) {return d["1"]}));

      return state;
  },
  componentDidMount: function() {
      platformChartStore.addChangeListener(this._onStoresChange);
      var lineChart = this._drawLineChart(this.state.chartName, 
                                          this.state.chartType, 
                                          this._lineData(this._getNested(this.props.data)),
                                          this.state.min, this.state.max);
      this.setState({lineChart: lineChart});

      this.chart = React.findDOMNode(this.refs[this.state.chartName]);
  },
  componentWillUnmount: function () {
      platformChartStore.removeChangeListener(this._onStoresChange);
      if (this.lineChart)
      {
        delete this.lineChart;
      }
  },
  componentDidUpdate: function() {
      if (this.state.lineChart)
      {
          this._updateLineChart(this.state.lineChart, 
                                this.state.chartName, 
                                this._lineData(this._getNested(this.props.data)));
      }
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
      
      if (this.chart)
      {
          this.nvtooltip = this.chart.querySelector(".nvtooltip");

          if (this.nvtooltip)
          {
              this.nvtooltip.style.opacity = 0;
          }
      }
  },
  _onChartChange: function (e) {
      var chartType = e.target.value;
      
      var lineChart = this._drawLineChart(this.state.chartName, 
                                          chartType, 
                                          this._lineData(this._getNested(this.props.data)),
                                          this.state.min, this.state.max);

      this.setState({lineChart: lineChart});
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
  _onMinChange: function (e) {
      var min = e.target.value;
      var lineChart = this._drawLineChart(this.state.chartName, 
                                      this.state.chartType, 
                                      this._lineData(this._getNested(this.props.data)),
                                      min, this.state.max);

      this.setState({lineChart: lineChart});

      platformChartActionCreators.setMin(min, this.props.name);

      if (this.state.pinned)
      {
          platformActionCreators.saveCharts();
      }
  },
  _onMaxChange: function (e) {
      var max = e.target.value;
      var lineChart = this._drawLineChart(this.state.chartName, 
                                      this.state.chartType, 
                                      this._lineData(this._getNested(this.props.data)),
                                      this.state.min, max);

      this.setState({lineChart: lineChart});

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
                <option value="line">Line</option>
                <option value="lineWithFocus">Line with View Finder</option>
                <option value="stackedArea">Stacked Area</option>
                <option value="cumulativeLine">Cumulative Line</option>
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
                {chartMinControlButton}
                {chartMaxControlButton}
                <div className="inlineBlock"
                      style={spaceStyle}></div>
            </div>
        );
    }

    return (
      <div className='platform-line-chart'
          style={chartStyle}
          ref={this.state.chartName}>
          <svg id={this.state.chartName} style={svgStyle}></svg>
          {controlButtons}
      </div>
    );
  },
  _drawLineChart: function (elementParent, chartType, data, yMin, yMax) {
      
      var tickCount = 0;
      // var lineChart;

      switch (chartType)
      {
          case "line":
              this.lineChart = nv.models.lineChart();
              break;
          case "lineWithFocus":
              this.lineChart = nv.models.lineWithFocusChart();
              break;
          case "stackedArea":
              this.lineChart = nv.models.stackedAreaChart();
              break;
          case "cumulativeLine":
              this.lineChart = nv.models.cumulativeLineChart();
              break;
      }

      this.lineChart.margin({left: 25, right: 25})
          .x(function(d) {return d.x})
          .y(function(d) {return d.y})
          .useInteractiveGuideline(true)
          .showYAxis(true)
          .showXAxis(true);
      this.lineChart.xAxis
        .tickFormat(function (d, i) {

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
        })
        .staggerLabels(false);
      this.lineChart.yAxis
        .tickFormat(d3.format('.1f'));
      this.lineChart.forceY([yMin, yMax]);

      switch (chartType)
      {        
          case "lineWithFocus":            
              this.lineChart.x2Axis
                .tickFormat(function (d) {
                    return d3.time.format('%X')(new Date(d));
                });
              break;
      }

      d3.selectAll('#' + elementParent + ' > *').remove();
      d3.select('#' + elementParent)
        .datum(data)
        .call(this.lineChart);
      nv.utils.windowResize(function() {
        if (this.lineChart)
        {
           this.lineChart.update();
        }
      });

      nv.addGraph(function() {
        return this.lineChart;
      });

      return this.lineChart;
    },
    _updateLineChart: function (lineChart, elementParent, data) {
      d3.select('#' + elementParent)
        .datum(data)
        .call(lineChart);
    },
    _getNested: function (data) {
      var keyYearMonth = d3.nest()
        .key(function(d){return d.parent; })
        .key(function(d){return d["0"]; });
      var keyedData = keyYearMonth.entries(
        data.map(function(d) {
          return d;
        })
      );
      return keyedData;
    },
    _lineData: function (data) {
      var colors = ['DarkOrange', 'ForestGreen', 'DeepPink', 'DarkViolet', 'Teal', 'Maroon', 'RoyalBlue', 'Silver', 'MediumPurple', 'Red', 'Lime', 'Tan', 'LightGoldenrodYellow', 'Turquoise', 'Pink', 'DeepSkyBlue', 'OrangeRed', 'LightGrey', 'Olive'];
      data = data.sort(function(a,b){ return a.key > b.key; });
      var lineDataArr = [];
      for (var i = 0; i <= data.length-1; i++) {
        var lineDataElement = [];
        var currentValues = data[i].values.sort(function(a,b){ return +a.key - +b.key; });
        for (var j = 0; j <= currentValues.length-1; j++) {
          lineDataElement.push({
            'x': +currentValues[j].key,
            'y': +currentValues[j].values[0][1]
          });
        }
        lineDataArr.push({
          key: data[i].key,
          color: colors[i],
          values: lineDataElement
        });
      }
      return lineDataArr;
    }
  
});




module.exports = PlatformChart;
