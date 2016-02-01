'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');


var graphStore = require('../stores/graph-store');

var lineChart;

var Header = React.createClass({
  render: function() {
    return (
      <div className='row text-center'>
        <div className='col-md-12'>
          <h3>2011 to 2015</h3>
        </div>
      </div>
    );
  }
});

var UserSelect = React.createClass({
  render: function() {
    return (
      <div className='row text-center'>
        <div className='col-md-12'>
          <div id='user-select-dropdown' className='dropdown'>
            <button className='btn btn-default dropdown-toggle' type='button' id='user-select' data-toggle='dropdown' aria-haspopup='true' aria-expanded='true'>
              <span id='select-text'>Avg Temp (ºF)</span> <span className='caret'></span>
            </button>
            <ul onClick={this.props.handleSelect} className='dropdown-menu' aria-labelledby='user-select'>
              <li><a href='javascript:void(0)' className='select current-selection' id='avg_temp_f'>Avg Temp (ºF)</a></li>
              <li><a href='javascript:void(0)' className='select' id='avg_min_temp_f'>Avg Min Temp (ºF)</a></li>
              <li><a href='javascript:void(0)' className='select' id='avg_max_temp_f'>Avg Max Temp (ºF)</a></li>
              <li><a href='javascript:void(0)' className='select' id='total_percipitation_in'>Total Percipitation (in)</a></li>
              <li><a href='javascript:void(0)' className='select' id='total_snowfall_in'>Total Snowfall (in)</a></li>
            </ul>
          </div>
        </div>
      </div>
    );
  }
});

var BarChart = React.createClass({
  componentDidMount: function() {
    drawLineChart('line-chart', lineData(this.props.selection, keyToYearThenMonth(this.props.data)));
  },
  componentDidUpdate: function() {
    updateLineChart('line-chart', lineData(this.props.selection, keyToYearThenMonth(this.props.data)));
  },
  render: function() {
    return (
      <div id='line-chart'>
        <svg></svg>
      </div>
    );
  }
});

var Viz = React.createClass({
  getInitialState: function() {
    return {
      data: [],
      selection: 'avg_temp_f'
    };
  },
  // loadData: function () {
  //   d3.csv('/data/018_analytics_chart.csv',function(csv){
  //     this.setState({
  //       data: csv
  //     });
  //   }.bind(this));
  // },
  // componentDidMount: function () {
  //   this.loadData();
  // },
  loadData: function (datum) {
    
    this.setState({ data: datum});
  },
  componentDidMount: function () {
    var datum = graphStore.getGraphData();
    this.loadData(datum);
  },
  handleUserSelect: function (e) {
    var selection = e.target.id;
    $('#select-text').text(e.target.innerHTML);
    $('.select').removeClass('current-selection');
    $('#' + selection).addClass('current-selection');
    this.setState({
      selection: selection
    });
  },
  render: function() {
    return (
      <div id='viz'>
        <Header />
        <UserSelect selection={this.state.selection} handleSelect={this.handleUserSelect} />
        { this.state.data.length != 0 ? <BarChart data={this.state.data} selection={this.state.selection} /> : null }
      </div>
    );
  }
});


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

        

        return (
                <div className="view">
                    <div id="chart" class='with-3d-shadow with-transitions'>
                        <Viz/>
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


function drawLineChart (elementParent, data) {
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  nv.addGraph(function() {
    lineChart = nv.models.lineChart()
      .margin({left: 25, right: 25})
      .x(function(d) {return d.x})
      .y(function(d) {return d.y})
      .useInteractiveGuideline(true)
      .showYAxis(true)
      .showXAxis(true);
    lineChart.xAxis
      .tickFormat(function (d) { return months[d - 1]; })
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
function keyToYearThenMonth (data) {
  var keyYearMonth = d3.nest()
    .key(function(d){return d.year; })
    .key(function(d){return d.month; });
  var keyedData = keyYearMonth.entries(
    data.map(function(d) {
      return d;
    })
  );
  return keyedData;
}

function lineData (selection, data) {
  var colors = ['#ff7f00','#984ea3','#4daf4a','#377eb8','#e41a1c'];
  data = data.sort(function(a,b){ return +a.key - +b.key; });
  var lineDataArr = [];
  for (var i = 0; i <= data.length-1; i++) {
    var lineDataElement = [];
    var currentValues = data[i].values.sort(function(a,b){ return +a.key - +b.key; });
    for (var j = 0; j <= currentValues.length-1; j++) {
      lineDataElement.push({
        'x': +currentValues[j].key,
        'y': +currentValues[j].values[0][selection]
      });
    }
    lineDataArr.push({
      key: +data[i].key,
      color: colors[i],
      values: lineDataElement
    });
  }
  return lineDataArr;
}


module.exports = Graph;
