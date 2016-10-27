'use strict';


var React = require('react');
var Router = require('react-router');

var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsStore = require('../stores/platforms-store');
var RegisterPlatformForm = require('../components/register-platform-form');
var StatusForm = require('../components/status-indicator');
var DeregisterPlatformConfirmation = require('../components/deregister-platform-confirmation');

var OADR = React.createClass({

    render: function(){
    return (
    <div className="view">
    <h2>Open ADR</h2>
    This space for: listing each VEN, with time since last contact,
    reports, and events. 
    </div>);
    }
});

module.exports = OADR;
