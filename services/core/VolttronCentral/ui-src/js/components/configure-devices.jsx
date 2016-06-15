'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var DetectDevices = require('./detect-devices');
var DevicesFound = require('./devices-found');
var ConfigureDevice = require('./configure-device');
var ConfigureRegistry = require('./configure-registry');
var devicesStore = require('../stores/devices-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

var ConfigureDevices = React.createClass({
    // mixins: [Router.State],
    getInitialState: function () {
        var state = getStateFromStores();
        
        if (state.deviceMethod === "scanForDevices")
        {
            state.selectedProxyUuid = state.bacnetProxies[0].uuid;
        }

        return state;
    },
    componentDidMount: function () {
        devicesStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        devicesStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var state = getStateFromStores();

        if (!state.hasOwnProperty(selectedProxyUuid))
        {
            if (state.bacnetProxies.length)
            {
                state.selectedProxyUuid = state.bacnetProxies[0].uuid;
            }
        }
        this.setState(state);
    },
    _onDeviceMethodChange: function (evt) {

        var deviceMethod = evt.target.value;

        this.setState({deviceMethod: deviceMethod});

        if (this.state.bacnetProxies.length)
        {
            devicesActionCreators.addDevices(this.state.panelItem, deviceMethod);
            this.setState({ deviceMethod: deviceMethod });
        }
        else
        {
            statusIndicatorActionCreators.openStatusIndicator("error", "Can't scan for devices: A BACNet proxy agent must be installed for the platform.", null, "center");
        }
    },
    _onProxySelect: function (evt) {
        var selectedProxyUuid = evt.target.value;
        this.setState({ selectedProxyUuid: selectedProxyUuid });
    },
    render: function () {

        var view_component;
        var platform = this.state.platform;

        var devicesSelect = (
            <select
                onChange={this._onDeviceMethodChange}
                value={this.state.deviceMethod}
                autoFocus
                required
            >
                <option value="scanForDevices">Scan for Devices</option>
                <option value="addDevicesManually">Add Manually</option>
            </select>
        );

        var proxySelect;

        if (this.state.deviceMethod === "scanForDevices")
        {
            var proxies = this.state.bacnetProxies.map(function (proxy) {
                return (
                    <option value={proxy.uuid}>{proxy.name}</option>
                );
            });

            proxySelect = (
                <div>
                    <label><b>BACNet Proxy Agent: </b></label>
                    <select
                        onChange={this._onProxySelect}
                        value={this.state.selectedProxyUuid}
                        autoFocus
                        required
                    >
                        {proxies}
                    </select>
                </div>
            );
        }

        
        
        return (
            <div className="view">
                <h2>Install Devices</h2>
                <div>
                    <label><b>Instance: </b></label><label>{platform.name}</label><br/>
                    <label><b> Method: </b></label>{devicesSelect}<br/>
                    {proxySelect}                
                </div>
                
            </div>
        );
    },
});


function getStateFromStores() {

    var deviceState = devicesStore.getState();
    
    if (deviceState.platform)
    {
        deviceState.bacnetProxies = platformsStore.getBacnetProxies(deviceState.platform.uuid);

        deviceState.deviceMethod = (deviceState.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");
    }

    return deviceState;
}

module.exports = ConfigureDevices;