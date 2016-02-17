'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');


var chartStore = require('../stores/platform-chart-store');
// var chartDataStore = require('../stores/chart-data-store');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');

var lineChart;


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
    _onPinToggle: function () {
        platformChartActionCreators.pinChart(this.props.chartKey);
    },
    render: function () {
        var chartData = this.props.chart; 
        var platformChart;

        if (chartData)
        {
            var pinClasses = ["chart-pin"];

            if (chartData.data.length > 0)
            {
                pinClasses.push(chartData.pinned ? "pinned-chart" : "unpinned-chart");
                
                platformChart = (<div className="platform-chart with-3d-shadow with-transitions">
                    <label className="chart-title">{chartData.data[0].name}</label>
                    
                    <div className={pinClasses.join(' ')}
                        onClick={this._onPinToggle}>
                        <i className="fa fa-thumb-tack"></i>
                    </div>
                    <div className='viz'>        
                        { chartData.data.length != 0 ? 
                              <GraphLineChart data={chartData.data} 
                                  name={chartData.data[0].name } /> : null }
                    </div>

                    <br/>
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

      return state;
  },
  componentDidMount: function() {
    drawLineChart(this.state.chartName, lineData(getNested(this.props.data)));
  },
  componentDidUpdate: function() {
    updateLineChart(this.state.chartName, lineData(getNested(this.props.data)));
  },
  render: function() {

    // var chartHeight = 70 / this.props.count;

    var chartStyle = {
        // height: chartHeight.toString() + "%",
        width: "100%"
    }

    return (
      <div id={this.state.chartName} 
            className='platform-line-chart'
            style={chartStyle}>
        <svg></svg>
      </div>
    );
  }
});


function drawLineChart (elementParent, data) {
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  nv.addGraph(function() {
    lineChart = nv.models.lineWithFocusChart()
      .margin({left: 25, right: 25})
      .x(function(d) {return d.x})
      .y(function(d) {return d.y})
      .useInteractiveGuideline(true)
      .showYAxis(true)
      .showXAxis(true);
    lineChart.xAxis
      .tickFormat(d3.format('f'))
      .staggerLabels(false);
    lineChart.yAxis
      .tickFormat(d3.format('.1f'));
    d3.select('#' + elementParent + ' svg')
      .datum(data)
      .call(lineChart);
    nv.utils.windowResize(function() { lineChart.update() });
    return lineChart;
  });
}

function updateLineChart (elementParent, data) {
  d3.select('#' + elementParent + ' svg')
    .datum(data)
    .call(lineChart);
}


//line data
function getNested (data) {
  var keyYearMonth = d3.nest()
    .key(function(d){return d.parent; })
    .key(function(d){return d["0"]; });
  var keyedData = keyYearMonth.entries(
    data.map(function(d) {
      return d;
    })
  );
  return keyedData;
}

function lineData (data) {
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


module.exports = PlatformChart;
