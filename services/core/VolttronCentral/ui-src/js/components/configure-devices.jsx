'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var DetectDevices = require('./detect-devices');
var DevicesFound = require('./devices-found');
var ConfigureDevice = require('./configure-device');
var ConfigureRegistry = require('./configure-registry');
var devicesStore = require('../stores/devices-store');
var devicesActionCreators = require('../action-creators/devices-action-creators');
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

        if (!state.hasOwnProperty("selectedProxyUuid"))
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

        // this.setState({deviceMethod: deviceMethod});

        if (this.state.bacnetProxies.length)
        {
            // devicesActionCreators.addDevices(this.state.panelItem, deviceMethod);
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

        var proxySelect, proxySelectLabel;

        var tableStyle = {
            width: "40%"
        }

        var shortTdStyle = {
            width: "15%",
            lineHeight: "12px"
        }

        var longTdStyle = {
            width: "25%"
        }

        if (this.state.deviceMethod === "scanForDevices")
        {
            var proxies = this.state.bacnetProxies.map(function (proxy) {
                return (
                    <option value={proxy.uuid}>{proxy.name}</option>
                );
            });

            tableStyle.width = "60%";
            shortTdStyle.width = "5%";

            var longerTdStyle = {
                width: "40%",
                minWidth: "130px"
            }
            proxySelectLabel = (<td className="plain" style={longerTdStyle}><b>BACNet Proxy Agent: </b></td>)

            proxySelect = (
                <td className="plain" style={longTdStyle}>
                    <select
                        onChange={this._onProxySelect}
                        value={this.state.selectedProxyUuid}
                        autoFocus
                        required
                    >
                        {proxies}
                    </select>
                </td>
            );
        }

        var buttonStyle = {
            height: "21px"
        }

        var platformNameLength = platform.name.length * 6;

        var platformNameStyle = {
            width: "25%",
            minWidth: platformNameLength
        }
        
        return (
            <div className="view">
                <h2>Install Devices</h2>
                <table style={tableStyle}>
                    <tbody>
                        <tr>
                            <td className="plain" style={shortTdStyle}><b>Instance: </b></td>
                            <td className="plain" style={platformNameStyle}>{platform.name}</td>
                            <td className="plain" style={shortTdStyle}><b>Method: </b></td>
                            <td className="plain" style={longTdStyle}>{devicesSelect}</td>
                            {proxySelectLabel}{proxySelect}   
                            <td className="plain" style={shortTdStyle}><button style={buttonStyle}>Go</button></td>             
                        </tr>
                    </tbody>
                </table>
                
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