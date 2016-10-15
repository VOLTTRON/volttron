'use strict';

var $ = require('jquery');
import React from 'react';
import BaseComponent from './base-component';
import DevicesFound from './devices-found';

import Select from 'react-select-me';

var platformsStore = require('../stores/platforms-store');
var devicesStore = require('../stores/devices-store');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

const scanDuration = 10000; // 10 seconds

class ConfigureDevices extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onPlatformStoresChange', '_onDevicesStoresChange', '_onDeviceMethodChange',
                    '_onProxySelect', '_onDeviceStart', '_onDeviceEnd', '_onAddress', '_onStartScan',
                    '_showCancel', '_resumeScan', '_cancelScan', '_onDevicesLoaded');

        this.state = getInitialState();
    }
    componentDidMount() {
        platformsStore.addChangeListener(this._onPlatformStoresChange);
        devicesStore.addChangeListener(this._onDevicesStoresChange);
    }
    componentWillUnmount() {
        platformsStore.removeChangeListener(this._onPlatformStoresChange);
        devicesStore.removeChangeListener(this._onDevicesStoresChange);

        if (this._scanTimeout)
        {
            clearTimeout(this._scanTimeout);    
        }
    }
    _onPlatformStoresChange() {

        if (this.state.platform)
        {            
            var bacnetProxies = platformsStore.getRunningBacnetProxies(this.state.platform.uuid);
            
            this.setState({ bacnetProxies: bacnetProxies });

            if ((bacnetProxies.length < 1) && this.state.deviceMethod === "scanForDevices")
            {
                this.setState({ deviceMethod: "addDevicesManually" });
            }
        }
    }
    _onDevicesStoresChange() {

        if (devicesStore.getNewScan())
        {
            this.setState(getInitialState());

            if (this._scanTimeout)
            {
                clearTimeout(this._scanTimeout);    
            }
        }
        else
        {
            this.setState({devices: devicesStore.getDevices(this.state.platform, this.state.selectedProxyIdentity)});
        }
    }
    _onDeviceMethodChange(selection) {

        var deviceMethod = selection.value;

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
    _onProxySelect(selection) {
        var selectedProxyIdentity = selection.value;
        this.setState({ selectedProxyIdentity: selectedProxyIdentity });
    }
    _onDeviceStart(evt) {

        this.setState({ deviceStart: evt.target.value });

        if (!this.state.startedInputtingDeviceEnd)
        {
            this.setState({ deviceEnd: evt.target.value });            
        }
    }
    _onDeviceEnd(evt) {

        if (!this.state.startedInputtingDeviceEnd)
        {
            this.setState({startedInputtingDeviceEnd: true});
        }

        this.setState({ deviceEnd: evt.target.value });
    }
    _onAddress(evt) {
        this.setState({ address: evt.target.value });
    }
    _onStartScan(evt) {
        var platformAgentUuid = platformsStore.getPlatformAgentUuid(this.state.platform.uuid);

        devicesActionCreators.scanForDevices(
            this.state.platform.uuid, 
            platformAgentUuid,
            this.state.selectedProxyIdentity,
            this.state.deviceStart, 
            this.state.deviceEnd, 
            this.state.address
        );

        this.setState({ scanning: true });
        this.setState({ scanStarted: true });
        this.setState({ canceled: false });

        if (this._scanTimeout)
        {
            clearTimeout(this._scanTimeout);    
        }
        
        this._scanTimeout = setTimeout(this._cancelScan, scanDuration);
    }
    _onDevicesLoaded(devicesLoaded) {
        this.setState({devicesLoaded: devicesLoaded});
    }
    _showCancel() {

        if (this.state.scanning)
        {
            this.setState({cancelButton: true});
        }
    }
    _resumeScan() {

        if (this.state.scanning)
        {
            this.setState({cancelButton: false});
        }
    }
    _cancelScan() {
        this.setState({scanning: false});
        this.setState({canceled: true});
    }
    render() {

        var deviceContent, defaultMessage;

        if (this.state.platform)
        {

            var platform = this.state.platform;

            var methodOptions = [
                { value: "scanForDevices", label: "Scan for Devices"},
                { value: "addDevicesManually", label: "Add Manually"}
            ];

            var methodSelect = (
                <Select
                    name="method-select"
                    options={methodOptions}
                    value={this.state.deviceMethod}
                    onChange={this._onDeviceMethodChange}>
                </Select>
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
                        { value: proxy.identity, label: proxy.name } 
                    );
                });

                proxySelect = (
                    <tr>
                        <td className="plain"><b>BACNet Proxy Agent </b></td>

                        <td className="plain"
                            colSpan={4}>
                            <Select
                                style={wideStyle}
                                options={proxies}
                                onChange={this._onProxySelect}
                                value={this.state.selectedProxyIdentity}
                            >   
                            </Select>
                        </td>

                        <td className="plain" style={fifthCell}></td>
                    </tr>
                );
            }

            var buttonStyle = {
                height: "24px"
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
                                    <td className="plain">Min:</td>
                                    <td className="plain">
                                        <input
                                            type="number"
                                            style={deviceRangeStyle}
                                            onChange={this._onDeviceStart}
                                            value={this.state.deviceStart}></input>
                                    </td>
                                    <td className="plain">Max:</td>
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
            var scanButton;

            if (this.state.scanning)
            {
                var spinnerContent;

                if (this.state.cancelButton)
                {
                    spinnerContent = <span className="cancelScanning"><i className="fa fa-remove"></i></span>;
                }
                else
                {
                    spinnerContent = <i className="fa fa-cog fa-spin fa-2x fa-fw margin-bottom"></i>;
                }

                scanButton = (
                    <div style={scanOptionsStyle}>
                        <div className="scanningSpinner"
                            onClick={this._cancelScan}
                            onMouseEnter={this._showCancel}
                            onMouseLeave={this._resumeScan}>
                            {spinnerContent}
                        </div>
                    </div>
                );
            }
            else
            {
                scanButton = <div style={scanOptionsStyle}><button style={buttonStyle} onClick={this._onStartScan}>Go</button></div>;
            }

            if (this.state.devicesLoaded || this.state.scanStarted)
            {      
                devicesContainer = (
                    <DevicesFound 
                        devices={this.state.devices}
                        devicesloaded={this._onDevicesLoaded} 
                        platform={this.state.platform} 
                        canceled={this.state.canceled}
                        bacnet={this.state.selectedProxyIdentity}/>
                );
            }

            deviceContent = (
                <div className="device-box device-scan">
                    <div style={platformNameStyle}>
                        <div style={scanOptionsStyle}>
                            <b>Platform: </b>
                        </div>
                        <div style={scanOptionsStyle}>{platform.name}</div>
                    </div>
                    <div style={scanOptionsStyle}><b>Method: </b></div>
                    <div style={scanOptionsStyle}>{methodSelect}</div>  
                    <div style={scanOptionsStyle}>{scanOptions}</div>
                    {scanButton}
                </div>
            )
            
        }
        else
        {
            defaultMessage = (
                <div>Launch device installation from the side tree by clicking on the <i className="fa fa-cogs"></i> button next to the platform instance.</div>
            )
        }

        
        return (  
            <div className="view">   
                <h2>Install Devices</h2>      
                {deviceContent} 
                {defaultMessage} 
                <div className="device-box device-container">
                    {devicesContainer}
                </div> 

            </div>         
        );
    }
};


function getInitialState() {

    var state = devicesStore.getState();

    if (state.platform)
    {
        state.bacnetProxies = platformsStore.getRunningBacnetProxies(state.platform.uuid);
        state.deviceMethod = (state.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");

        state.deviceStart = "";
        state.deviceEnd = "";
        state.address = "";

        state.startedInputtingDeviceEnd = false;

        state.newScan = true;
        state.devices = [];
        
        if (state.deviceMethod === "scanForDevices")
        {
            state.selectedProxyIdentity = state.bacnetProxies[0].identity;
        }

        state.scanning = false;
        state.canceled = false;
        state.devicesLoaded = false;
        state.scanStarted = false;
        state.cancelButton = false;
    }

    return state;
}

export default ConfigureDevices;