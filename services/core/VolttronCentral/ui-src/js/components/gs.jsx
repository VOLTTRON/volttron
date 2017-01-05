'use strict';

//var $ = require('jquery');
var React = require('react');
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
	ret.response=response;
	    page.response = response;
	    const element = (
		    <div>
      <h1>Global Scheduler</h1> {response.content}
      <h2>It is {new Date().toLocaleTimeString()}.</h2>
      {JSON.stringify(page)}
    </div>
  );
	React.render(
    	element,
    	document.getElementById('gs')
  	);	

	})
        .catch(xhr.Error, function (error) {
            page.error = error;
	    ret.error=error;
	});
	return page;
    }
    


var GS = React.createClass({
/*    getInitialState: function () {
        var state = getStateFromStores();
        return state;
    },
    componentDidMount: function () {
        platformChartStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformChartStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },*/

    render: function(){
    var result = "";
    var page = gs();
    if (page.hasOwnProperty("response")) { 
       result += JSON.stringify(page.response);
    }   else { 
        result = " GS Agent not up.";
    }
    console.log(page);
    return (
    <div className="view">
                <div className="absolute_anchor">
    <h2>Global scheduler status</h2>
    This space for: Listing the last data received by
    the global sceduler and the last actions taken.
    Page refreshed at: {new Date().toLocaleTimeString()}
<span id="gs" >{result}</span>
{JSON.stringify(page)}
    
      </div>
      
    </div>
    );
    }
});

//function getStateFromStores() {
//    return {
//        platformCharts: platformChartStore.getPinnedCharts()
//    };
//}

module.exports = GS;
