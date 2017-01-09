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
	var enabled =false;
	var last_time="";
	var price = "";
	var price_time = "";
	var wattage = "";
	var actions=[];
	ret.response=response;
	    page.response = response;
	    var started = response.content.Started;
	    if (response.content.SiteAnalysis.length>0){
        	    last_time = response.content.SiteAnalysis[0].TimeStamp;
		    actions = response.content.Actions;
		    enabled = response.content.Enabled;
		    wattage =  response.content.SiteAnalysis[1]["analysis/Shirley-MA/PV/RealPower"];
	    }
	    if (response.content.ISONE.hasOwnProperty("message")){
	       price_time = response.content.ISONE.message.LMP.Readings[0] ; 
	       price = response.content.ISONE.message.LMP.Readings[1] ; 
	    }
	    const element = (
		    <div>
      <h2>Global Scheduler</h2>      
      Last site update: {last_time} Power measured: {wattage} <br/>
      Pricing: {price} posted at {price_time} <br/>
      Actions enabled: <span id="gs_enabled">{(enabled)? "YES":"NO" }</span><br/>
      Actions Taken: {JSON.stringify(actions)}<br/>
      Page refreshed at  {new Date().toLocaleTimeString()}. <br/>
      GSAgent started at {started}      
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
    set_enabled :function ( setting ) {
	var promise = xhr.Request({
	    method:'POST',
	    url: '/gs/enable',  
	    contentType:'application/json',
	    timeout:600000,
	    data: JSON.stringify(setting)
	}).finally(function(){
	    ReactDOM.render(
		(<span>{(setting)? "YES":"NO"}</span>),
    		document.getElementById('gs_enabled')
  	    );	
	});
    },

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
    <button className="button button--secondary"
            type="button"
            onClick={this.set_enabled.bind(this,true)}
                >Enable Actions</button>
    <button className="button button--secondary"
            type="button"
            onClick={this.set_enabled.bind(this,false)}
                >Disable Actions</button>

      </div>
    </div>
    );
    }
});


module.exports = GS;
