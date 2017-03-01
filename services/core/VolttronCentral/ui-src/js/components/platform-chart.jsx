'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
var d3 = require('d3');
var moment = require('moment');
var OutsideClick = require('react-click-outside');

import ControlButton from './control-button';
// import {LineChart, AreaChart} from 'react-d3-components';
// var LineChart = ReactD3.LineChart;
// var AreaChart = ReactD3.AreaChart;
import {Line} from 'react-chartjs-2';

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
      state.tooltipContent = "";
      state.min = (this.props.min ? this.props.min : d3.min(this.props.data, function (d) {return d["1"]}));
      state.max = (this.props.max ? this.props.max : d3.max(this.props.data, function (d) {return d["1"]}));

      return state;
  },
  componentDidMount: function() {
      platformChartStore.addChangeListener(this._onStoresChange);

      // this.chart = ReactDOM.findDOMNode(this.refs[this.state.chartName]);
  },
  componentWillUnmount: function () {
      platformChartStore.removeChangeListener(this._onStoresChange);
      
      // if (this.chart)
      // {
      //     delete this.chart;
      // }
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
  _showTooltip: function (d, e) {
      // var content = JSON.stringify(e);
      var content = JSON.stringify(d);
      this.setState({ tooltipContent: content });
      this.setState({ showTooltip: true });
  },
  _hideTooltip: function (e) {

      this.setState({ showTooltip: false });
  },
  mouseMoveHandler: function (e) {

      // this.setState({ showTooltip: false });
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

    var graphData = this.props.data.map(function (item) {
      return {x: item[0], y: item[1]};
    });

    // console.log(graphData[0]);

    var chartData = [
      {
        label: this.props.data[0].name,
        values: graphData
      }
    ];

    var labels = this.props.data.map(function (item) {
        return item[0];
      });

    var dataLabel = this.props.data[0].parent;

    var values = this.props.data.map(function (item) {
          return item[1];
        });

    var data = {
      labels: labels,
      datasets: [
        { 
          label: dataLabel,
          data: values,
          fill: false,
          lineTension: 0.1,
          backgroundColor: 'rgba(75,192,192,0.4)',
          borderColor: 'rgba(75,192,192,1)',
          borderCapStyle: 'butt',
          borderDash: [],
          borderDashOffset: 0.0,
          borderJoinStyle: 'miter',
          pointBorderColor: 'rgba(75,192,192,1)',
          pointBackgroundColor: '#fff',
          pointBorderWidth: 1,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: 'rgba(75,192,192,1)',
          pointHoverBorderColor: 'rgba(220,220,220,1)',
          pointHoverBorderWidth: 2,
          pointRadius: 1,
          pointHitRadius: 10
        }
      ]

    };

    

    var rdcChart;

    switch(this.state.chartType)
    {
      default:

        // chartTooltip = function(x, pt) {
        //     return "x: " + pt.x + " y: " + pt.y;
        // };
        rdcChart = (
          <Line 
            height={200} 
            width={700} 
            label={this.props.name}
            data={data}/>
        );
        break;
    }

    return (
      <div className='absolute_anchor'
          style={chartStyle}
          ref={this.state.chartName}>
          {rdcChart}
          {controlButtons}
      </div>
    );
  }
  
}));




module.exports = PlatformChart;