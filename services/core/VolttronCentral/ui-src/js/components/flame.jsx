'use strict';

var $ = require('jquery');
var React = require('react');
//var Router = require('react-router');
var xhr = require('../lib/xhr');

var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsStore = require('../stores/platforms-store');
var RegisterPlatformForm = require('../components/register-platform-form');
var StatusForm = require('../components/status-indicator');
var DeregisterPlatformConfirmation = require('../components/deregister-platform-confirmation');
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

function flame() {
    var page = {};
    page.promise = new xhr.Request({
        method: 'GET',
        url: '/flame/status',
	contentType:'application/json',
	timeout:600000,
    }).finally(function() {
	console.log("Flaming - finally");
	page.completed = Date.now();
    }).
	then(function(response) {
	    console.log("Flaming then");
	    page.response = response;
	    const element = (
		    <div>
      <h1>FLAME</h1> {response.content}
      <h2>Page refreshed at {new Date().toLocaleTimeString()}.</h2>
    </div>
  );
	ReactDOM.render(
    	element,
    	document.getElementById('flame')
  	);	

	})
        .catch(xhr.Error, function (error) {
            page.error = error;
	});
    }
    


var FLAME = React.createClass({
    render: function(){
    flame();
    return (
    <div className="view">
                <div className="absolute_anchor">
    <h2>FLAME</h2>
    This space for: listing each Flame partner, with time since last contact,
    reports, and events.
     {new Date().toLocaleTimeString()}
 <span id="flame" >TEST</span>
    
      </div>
      
    </div>
    );
    }
});

module.exports = FLAME;
