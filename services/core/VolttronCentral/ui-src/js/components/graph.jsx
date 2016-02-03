'use strict';

var React = require('react');
var Router = require('react-router');
var d3 = require('d3');
var nv = require('nvd3');


var graphStore = require('../stores/graph-store');

var lineChart;


var Graph = React.createClass({
    getInitialState: function () {
        var state = {};
        state.graphs = getGraphsFromStores();

        return state;
    },
    componentWillMount: function () {
        
    },
    componentDidMount: function () {
        graphStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        graphStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        var graphs = getGraphsFromStores();

        this.setState({graphs: graphs});
    },
    render: function () {
        var graphs  = this.state.graphs;  

        var vizGraph;

        if (graphs.length > 0)
        {
            vizGraph = <div id="chart" class='with-3d-shadow with-transitions'>
                          <Viz data={graphs}></Viz>
                      </div>
        }


        return (
            <div>
                {vizGraph}
            </div>
        );
    },
});


function getGraphsFromStores() {
    return graphStore.getData();
}


var GraphLineChart = React.createClass({
  componentDidMount: function() {
    drawLineChart('graph-line-chart', lineData(this.props.selection, keyToYearThenMonth(this.props.data)));
  },
  componentDidUpdate: function() {
    updateLineChart('graph-line-chart', lineData(this.props.selection, keyToYearThenMonth(this.props.data)));
  },
  render: function() {
    return (
      <div id='graph-line-chart'>
        <svg></svg>
      </div>
    );
  }
});

var Viz = React.createClass({
  getInitialState: function() {
    return {
      // data: this.props.data,
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
  // loadData: function () {
    
  //   this.setState({ data: this.props.data});
  // },
  // componentDidMount: function () {
  //   // var datum = graphStore.getGraphData();
  //   this.loadData();
  // },

    // componentDidUpdate: function() {
        
    //     this.setState({data: this.props.data});
    // },

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
        
        { this.props.data.length != 0 ? <GraphLineChart data={this.props.data} selection={this.state.selection} /> : null }
      </div>
    );
  }
});


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
    .key(function(d){return d.name; })
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
  data = data.sort(function(a,b){ return a.key > b.key; });
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
      key: data[i].key,
      color: colors[i],
      values: lineDataElement
    });
  }
  return lineDataArr;
}


module.exports = Graph;
