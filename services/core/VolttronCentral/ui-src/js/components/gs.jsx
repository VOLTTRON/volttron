'use strict';

//var $ = require('jquery');
var React = require('react');
var ReactDOM = require('react-dom');
//var Router = require('react-router');
var xhr = require('../lib/xhr');
//var platformChartStore = require('../stores/platform-chart-store');

//var modalActionCreators = require('../action-creators/modal-action-creators');
//var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
//var StatusForm = require('../components/status-indicator');

function gs() {
    var page = {};
    var ret = {}
    console.log("gs");
    page.promise = new xhr.Request({
        method: 'GET',
        url: '/gs/status',
	contentType:'application/json',
	timeout:600000,
    }).finally(function() {
	page.completed = Date.now();
    }).
	then(function(response) {
	var enabled ="";
	var last_time="";
	var wattage = "";
	var actions=[];
	ret.response=response;
	    page.response = response;
	    if (response.content.SiteAnalysis.length>0){
        	    last_time = response.content.SiteAnalysis[0].TimeStamp;
		    actions = response.content.Actions;
		    enabled = response.content.Enabled;
		    wattage =  response.content.SiteAnalysis[1]["analysis/Shirley-MA/PV/RealPower"];
	    }
	    const element = (
		    <div>
      <h2>Global Scheduler</h2>      
      Last site update: {last_time} Power measured: {wattage} <br/>
      Actions enabled: {enabled}<br/>
      Actions Taken: {actions}<br/>
      Page refreshed at  {new Date().toLocaleTimeString()}.
    </div>
  );
	ReactDOM.render(
    	element,
    	document.getElementById('gs')
  	);	

	})
        .catch(xhr.Error, function (error) {
            page.error = error;
	    ret.error=error;
	    const element = (
		    <div>Global Scheduler is not up.</div>);
	    ReactDOM.render(
		element,
    	document.getElementById('gs')
  	);	
	    
	});
    }
    


var GS = React.createClass({

    render: function(){
    var result = "";
    gs();
    
    return (
    <div className="view">
                <div className="absolute_anchor">
		<span id="gs">
    <h2>Global scheduler status</h2>
    This space for: Listing the last data received by
    the global sceduler and the last actions taken.
    <br/>
    Page refreshed at: {new Date().toLocaleTimeString()}
    </span>
    
      </div>
      
    </div>
    );
    }
});


module.exports = GS;
