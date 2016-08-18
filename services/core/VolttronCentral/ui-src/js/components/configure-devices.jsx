'use strict';

import React from 'react';
import BaseComponent from './base-component';

var platformsStore = require('../stores/platforms-store');
var devicesStore = require('../stores/devices-store');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
import DevicesFound from './devices-found';

class ConfigureDevices extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onPlatformStoresChange', '_onDevicesStoresChange', '_onDeviceMethodChange',
                    '_onProxySelect', '_onDeviceStart', '_onDeviceEnd', '_onAddress', '_onWhoIs',
                    '_onDeviceStart', '_onDeviceEnd', '_onAddress');

        this.state = devicesStore.getState();

        this.state.bacnetProxies = platformsStore.getRunningBacnetProxies(this.state.platform.uuid);
        this.state.deviceMethod = (this.state.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");

        this.state.deviceStart = "";
        this.state.deviceEnd = "";
        this.state.address = "";

        this.state.newScan = true;
        
        if (this.state.deviceMethod === "scanForDevices")
        {
            this.state.selectedProxyUuid = this.state.bacnetProxies[0].uuid;
        }

        this.state.scanning = false;
    }
    componentDidMount() {
        platformsStore.addChangeListener(this._onPlatformStoresChange);
        devicesStore.addChangeListener(this._onDevicesStoresChange);
    }
    componentWillUnmount() {
        platformsStore.removeChangeListener(this._onPlatformStoresChange);
        devicesStore.removeChangeListener(this._onDevicesStoresChange);
    }
    _onPlatformStoresChange() {

        var bacnetProxies = platformsStore.getRunningBacnetProxies(this.state.platform.uuid);
        
        this.setState({ bacnetProxies: bacnetProxies });

        if ((bacnetProxies.length < 1) && this.state.deviceMethod === "scanForDevices")
        {
            this.setState({ deviceMethod: "addDevicesManually" });
        }
    }
    _onDevicesStoresChange() {

        var deviceState = devicesStore.getState();

        if (deviceState.platform.uuid !== this.state.platform.uuid)
        {
            deviceState.bacnetProxies = platformsStore.getRunningBacnetProxies(deviceState.platform.uuid);
            deviceState.deviceMethod = (deviceState.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");
            
            if (deviceState.deviceMethod === "scanForDevices")
            {
                deviceState.selectedProxyUuid = deviceState.bacnetProxies[0].uuid;
            }

            deviceState.scanning = false;

            this.setState(deviceState);
        }
        else
        {
            this.setState({scanning: true});
            // this.setState({devices: devicesStore.getDevices()});

            // for (key in deviceState)
            // {
            //     this.setState({ key: deviceState[key] });
            // }
        }

    }
    _onDeviceMethodChange(evt) {

        var deviceMethod = evt.target.value;

        if (this.state.bacnetProxies.length)
        {
            this.setState({ deviceMethod: deviceMethod });
        }
        else
        {
            statusIndicatorActionCreators.openStatusIndicator("error", 
                "Can't scan for devices: A BACNet proxy agent for the platform must be installed and running.", null, "left");
        }
    }
    _onProxySelect(evt) {
        var selectedProxyUuid = evt.target.value;
        this.setState({ selectedProxyUuid: selectedProxyUuid });
    }
    _onDeviceStart(evt) {
        this.setState({ deviceStart: evt.target.value });
    }
    _onDeviceEnd(evt) {
        this.setState({ deviceEnd: evt.target.value });
    }
    _onAddress(evt) {
        this.setState({ address: evt.target.value });
    }
    _onWhoIs(evt) {
        devicesActionCreators.scanForDevices(this.state.deviceStart, this.state.deviceEnd, this.state.address);
        this.setState({ scanning: true });
    }
    render() {

        var view_component;
        var platform = this.state.platform;

        var methodSelect = (
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

        var wideStyle = {
            width: "100%"
        }

        var fifthCell = {
            width: "20px"
        }        

        if (this.state.deviceMethod === "scanForDevices")
        {
            var proxies = this.state.bacnetProxies.map(function (proxy) {
                return (
                    <option key={proxy.uuid} value={proxy.uuid}>{proxy.name}</option>
                );
            });

            proxySelect = (
                <tr>
                    <td className="plain"><b>BACNet Proxy Agent: </b></td>

                    <td className="plain"
                        colSpan={4}>
                        <select
                            style={wideStyle}
                            onChange={this._onProxySelect}
                            value={this.state.selectedProxyUuid}
                            autoFocus
                            required
                        >
                            {proxies}
                        </select>
                    </td>

                    <td className="plain" style={fifthCell}></td>
                </tr>
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

        var deviceRangeStyle = {
            width: "70px"
        }

        var tdStyle = {
            minWidth: "120px"
        }

        var scanOptions = (
            <div className="detectDevicesContainer">
                <div className="detectDevicesBox">
                    <table>
                        <tbody>
                            {proxySelect}
                            <tr>
                                <td className="plain" style={tdStyle}><b>Device ID Range</b></td>
                                <td className="plain">Start:</td>
                                <td className="plain">
                                    <input
                                        type="number"
                                        style={deviceRangeStyle}
                                        onChange={this._onDeviceStart}
                                        value={this.state.deviceStart}></input>
                                </td>
                                <td className="plain">End:</td>
                                <td className="plain">
                                    <input 
                                        type="number"
                                        style={deviceRangeStyle}
                                        onChange={this._onDeviceEnd}
                                        value={this.state.deviceEnd}></input>
                                </td>
                                <td className="plain"></td>
                            </tr>
                            <tr>
                                <td><b>Address</b></td>
                                <td className="plain"
                                    colSpan={4}>
                                    <input 
                                        style={wideStyle}
                                        type="text"
                                        onChange={this._onAddress}
                                        value={this.state.address}></input>
                                </td>
                                <td className="plain" style={fifthCell}></td>
                            </tr>
                        </tbody>
                    </table>
                </div>                
            </div>
        )

        var scanOptionsStyle = {
            float: "left",
            marginRight: "10px"
        }

        var platformNameStyle = {
            float: "left",
            width: "100%"
        }

        var devicesContainer;

        if (this.state.scanning)
        {
            devicesContainer = <DevicesFound platform={this.state.platform}/>;            
        }
        
        return (
            <div className="view">
                <h2>Install Devices</h2>
                <div className="device-box device-scan">
                    <div style={platformNameStyle}>
                        <div style={scanOptionsStyle}>
                            <b>Instance: </b>
                        </div>
                        <div style={scanOptionsStyle}>{platform.name}</div>
                    </div>
                    <div style={scanOptionsStyle}><b>Method: </b></div>
                    <div style={scanOptionsStyle}>{methodSelect}</div>  
                    <div style={scanOptionsStyle}>{scanOptions}</div>
                    <div style={scanOptionsStyle}><button style={buttonStyle} onClick={this._onWhoIs}>Go</button></div>
                </div>
                <div className="device-box device-container">
                    {devicesContainer}
                </div>
            </div>
        );
    }
};


function getStateFromStores() {

    var deviceState = devicesStore.getState();
    
    if (deviceState.platform)
    {
        deviceState.bacnetProxies = platformsStore.getRunningBacnetProxies(deviceState.platform.uuid);

        deviceState.deviceMethod = (deviceState.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");
    }

    return deviceState;
}

export default ConfigureDevices;