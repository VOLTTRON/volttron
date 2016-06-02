'use strict';

var React = require('react');
var Router = require('react-router');

// var platformsStore = require('../stores/platforms-store');
var DetectDevices = require('./detect-devices');
var DevicesFound = require('./devices-found');
var ConfigureDevice = require('./configure-device');
var ConfigureRegistry = require('./configure-registry');
var devicesStore = require('../stores/devices-store');

var Devices = React.createClass({
    // mixins: [Router.State],
    getInitialState: function () {
        return getStateFromStores();
    },
    componentDidMount: function () {
        devicesStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        devicesStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {

        var view_component;
        var platform = this.state.platform;

        switch (this.state.view)
        {
            case "Detect Devices":

                view_component = (<DetectDevices platform={this.state.platform} action={this.state.action}/>)

                break;
            case "Configure Devices":
                view_component = (<DevicesFound platform={this.state.platform} action={this.state.action}/>)
                break;
            case "Configure Device":
                view_component = (<ConfigureDevice device={this.state.device} action={this.state.action}/>)
                break;
            case "Registry Configuration":
                view_component = (<ConfigureRegistry device={this.state.device} action={this.state.action}/>)
                break;
        }
        
        return (
            <div className="view">
                <h2>{this.state.view}</h2>
                <div>
                    <label><b>Instance: </b></label><label>{platform.name}</label>
                    {view_component}
                
                </div>
                
            </div>
        );
    },
});


function getStateFromStores() {

    var deviceState = devicesStore.getState();
    
    return {
        // platform: platformsStore.getPlatform(component.getParams().uuid),
        platform: { name: "PNNL", uuid: "99090"},
        view: deviceState.view,
        action: deviceState.action,
        device: deviceState.device
    };
}

module.exports = Devices;