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
        url: '/oadr/test',
	contentType:'application/json',
	timeout:600000,
    }).finally(function() {
	console.log("oadring - finally");
	page.completed = Date.now();
    }).
	then(function(response) {
	    console.log("oadring then");
	    page.response = response;
	    const element = (
		    <div>
      <h1>FLAME</h1> {response.content}
      <h2>It is {new Date().toLocaleTimeString()}.</h2>
    </div>
  );
	React.render(
    	element,
    	document.getElementById('oadr')
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
    <h2>Open ADR</h2>
    This space for: listing each VEN, with time since last contact,
    reports, and events.
     {new Date().toLocaleTimeString()}
Test <span id="oadr" >TEST</span>
    
      </div>
      
    </div>
    );
    }
});

module.exports = OADR;
