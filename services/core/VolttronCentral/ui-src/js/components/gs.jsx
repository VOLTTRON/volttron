'use strict';

//var $ = require('jquery');
var React = require('react');
//var Router = require('react-router');
var xhr = require('../lib/xhr');

var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var StatusForm = require('../components/status-indicator');
//
// TODO: 
//
// The interface here should report as follows:
//
// 1. That the OpenADR agent is up.
// 2. Each VEN and when it last had contact with it. 
// 3. The latest oadrReports on from all parties.
// 4. Whether any Events are active. 
//
// The entry point into the Oadr agent is with /oadr/.
// IT already has a method there to return its state.
// What is missing is enough React smarts to display it.
// platform-charg-action-createros.js has a clue as to how to do this.

function gs() {
    var page = {};
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
	    page.response = response;
	    const element = (
		    <div>
      <h1>Global Scheduler</h1> {response.content}
      <h2>It is {new Date().toLocaleTimeString()}.</h2>
    </div>
  );
	React.render(
    	element,
    	document.getElementById('gs')
  	);	

	})
        .catch(xhr.Error, function (error) {
            page.error = error;
	});
	return page;
    }
    


var GS = React.createClass({
    render: function(){
    console.log("GS");
    var page = gs();
    return (
    <div className="view">
                <div className="absolute_anchor">
    <h2>Global scheduler status</h2>
    This space for: Listing the last data received by
    the global sceduler and the last actions taken.
     {new Date().toLocaleTimeString()}
Test <span id="gs" >{page}</span>
    
      </div>
      
    </div>
    );
    }
});

module.exports = GS;
