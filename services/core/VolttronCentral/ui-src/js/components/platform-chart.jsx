'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');
var moment = require('moment');


var chartStore = require('../stores/platform-chart-store');
// var chartDataStore = require('../stores/chart-data-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');

var PlatformChart = React.createClass({
    componentDidMount: function () {
        if (!this._refreshChartTimeout) {
            this._refreshChartTimeout = setTimeout(this._refreshChart, 0);
        }
    },
    componentWillUnmount: function () {
        clearTimeout(this._refreshChartTimeout);
    },
    _refreshChart: function () {
        
        if (this.props.hasOwnProperty("chart"))
        {
            platformChartActionCreators.refreshChart(
                this.props.chart.series
            );

            if (this.props.chart.refreshInterval) {
                this._refreshChartTimeout = setTimeout(this._refreshChart, this.props.chart.refreshInterval);
            }    
        }
    },
    render: function () {
        var chartData = this.props.chart; 
        var platformChart;

        if (chartData)
        {
            if (chartData.data.length > 0)
            {
                platformChart = (
                  <div className="platform-chart with-3d-shadow with-transitions">
                      <label className="chart-title">{chartData.data[0].name}</label>                      
                      <div>
                          <div className='viz'>        
                              { chartData.data.length != 0 ? 
                                    <GraphLineChart data={chartData.data} 
                                        name={chartData.data[0].name } /> : null }
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

  getInitialState: function () {
      var state = {};
      state.chartName = this.props.name.replace(" / ", "_") + '_chart';
      state.type = "line";
      state.lineChart = null;
      state.pinned = false;
      state.showTaptip = false;
      state.taptipX = 0;
      state.taptipY = 0;

      return state;
  },
  componentDidMount: function() {
      
      var lineChart = this._drawLineChart(this.state.chartName, this.state.type, this._lineData(this._getNested(this.props.data)));
      this.setState({lineChart: lineChart});
  },
  componentDidUpdate: function() {
      if (this.state.lineChart)
      {
          this._updateLineChart(this.state.lineChart, this.state.chartName, this._lineData(this._getNested(this.props.data)));
      }
  },
  _showTaptip: function (evt) {

      if (!this.state.showTaptip)
      {
          this.setState({taptipX: evt.clientX - 60});
          this.setState({taptipY: evt.clientY - 100});
      }

      this.setState({showTaptip: !this.state.showTaptip});
  },
  _onChartChange: function (e) {
      var chartType = e.target.value;
      
      var lineChart = this._drawLineChart(this.state.chartName, chartType, this._lineData(this._getNested(this.props.data)));

      this.setState({ type: e.target.value});
      this.setState({lineChart: lineChart});
      this.setState({showTaptip: false});
  },
  _onPinToggle: function () {
      this.setState({pinned: !this.state.pinned});
      // platformChartActionCreators.pinChart(this.props.chartKey);
  },
  render: function() {

    // var chartHeight = 70 / this.props.count;

    var chartStyle = {
        // height: chartHeight.toString() + "%",
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

    var taptipStyle = {
        display: (this.state.showTaptip ? "block" : "none"),
        position: "absolute",
        left: this.state.taptipX + "px",
        top: this.state.taptipY + "px"
    };

    var tapTipClasses = "taptip_outer";
    
    return (
      <div className='platform-line-chart'
          style={chartStyle}>
          <svg id={this.state.chartName} style={svgStyle}></svg>
          <div className="displayBlock"
              style={controlStyle}>
              <div className="filter_button"
                  onClick={this._changeChartType}>
                  <div className="centeredDiv">
                      <div className={pinClasses.join(' ')}
                          onClick={this._onPinToggle}>
                          <i className="fa fa-thumb-tack"></i>
                      </div>
                  </div>
              </div>
              <div className={tapTipClasses}
                  style={taptipStyle}>
                  <div className="taptip_inner">
                      <div className="opaque_inner">
                          <h4>Chart Type</h4>
                          <br/>
                          <select
                              id="type"
                              onChange={this._onChartChange}
                              value={this.state.type}
                              autoFocus
                              required
                          >
                              <option value="line">Line</option>
                              <option value="lineWithFocus">Line with View Finder</option>
                              <option value="stackedArea">Stacked Area</option>
                              <option value="cumulativeLine">Cumulative Line</option>
                          </select>
                      </div>
                  </div>
              </div>
              <div className="inlineBlock">
                  <div className="filter_button"
                      onClick={this._showTaptip}>
                      <div className="centeredDiv">
                          <i className="fa fa-line-chart"></i>
                      </div>
                  </div>                  
              </div>
          </div>
      </div>
    );
  },
  _drawLineChart: function (elementParent, type, data) {
      var tickCount = 0;
      var lineChart;

      switch (type)
      {
          case "line":
              lineChart = nv.models.lineChart();
              break;
          case "lineWithFocus":
              lineChart = nv.models.lineWithFocusChart();
              break;
          case "stackedArea":
              lineChart = nv.models.stackedAreaChart();
              break;
          case "cumulativeLine":
              lineChart = nv.models.cumulativeLineChart();
              break;
      }

      lineChart.margin({left: 25, right: 25})
          .x(function(d) {return d.x})
          .y(function(d) {return d.y})
          .useInteractiveGuideline(true)
          .showYAxis(true)
          .showXAxis(true);
      lineChart.xAxis
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
      lineChart.yAxis
        .tickFormat(d3.format('.1f'));

      switch (type)
      {        
          case "lineWithFocus":            
              lineChart.x2Axis
                .tickFormat(function (d) {
                    return d3.time.format('%X')(new Date(d));
                });
              break;
      }

      d3.selectAll('#' + elementParent + ' > *').remove();
      d3.select('#' + elementParent)
        .datum(data)
        .call(lineChart);
      nv.utils.windowResize(function() { lineChart.update() });

      nv.addGraph(function() {
        return lineChart;
      });

      return lineChart;
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
