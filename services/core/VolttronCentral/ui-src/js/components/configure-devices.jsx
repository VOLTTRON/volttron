'use strict';

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
                    '_showCancel', '_resumeScan', '_cancelScan', '_onDevicesLoaded', '_showTooltip',
                    '_hideTooltip', '_toggleAdvanced', '_onScanLength');

        this.state = getInitialState();
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

        if (this.refs["config-device-ref"])
        {
            if (devicesStore.getNewScan())
            {
                this.setState(getInitialState());
            }
            else 
            {
                this.setState({devices: devicesStore.getDevices(this.state.platform, this.state.selectedProxyIdentity)});

                if (devicesStore.getScanningComplete() && this.state.scanning)
                {
                    this._cancelScan();
                }
            }
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
                "To scan for devices, a BACNet proxy agent for the platform must be installed and running.", null, "left");
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
    _onDevicesLoaded(devicesLoaded) {
        this.setState({devicesLoaded: devicesLoaded});
    }
    _onStartScan(evt) {
        devicesActionCreators.scanForDevices(
            this.state.platform.uuid, 
            this.state.selectedProxyIdentity,
            this.state.deviceStart, 
            this.state.deviceEnd, 
            this.state.address,
            this.state.scan_length
        );

        this.setState({ scanning: true });
        this.setState({ scanStarted: true });
        this.setState({ canceled: false });

        this._hideTooltip();
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

        devicesActionCreators.cancelDeviceScan();
    }
    _showTooltip(evt) {

        var sidePanel = document.querySelector(".platform-statuses");
        var sidePanelRects = sidePanel.getClientRects();
        var sidePanelWidth = sidePanelRects[0].width;

        var targetRects = evt.target.getClientRects();
        var targetLeft = targetRects[0].left;

        this.setState({showTooltip: true});
        this.setState({tooltipX: targetLeft - sidePanelWidth - 20});
        this.setState({tooltipY: evt.clientY - 140});
    }
    _hideTooltip() {
        this.setState({showTooltip: false});
    }
    _toggleAdvanced() {
        var showAdvanced = !this.state.showAdvanced;

        if (!showAdvanced)
        {
            this.setState({scan_length: ""});
            this.setState({address: ""});
        }

        this.setState({showAdvanced: showAdvanced});
    }
    _onScanLength(evt) {
        var scanLength = evt.target.value;

        if (scanLength > -1)
        {
            this.setState({scan_length: scanLength});
        }
    }
    render() {

        var deviceContent, defaultMessage;

        if (this.state.platform)
        {

            var platform = this.state.platform;

            var methodOptions = [
                { value: "scanForDevices", label: "Scan for Devices"}
            ];

            var methodSelect = (
                <Select
                    name="method-select"
                    options={methodOptions}
                    value={this.state.deviceMethod}
                    onChange={this._onDeviceMethodChange}>
                </Select>
            );

            var proxySelect, scanLength;

            var wideStyle = {
                width: "100%"
            }

            var fifthCell = {
                width: "20px"
            }        

            var advancedClass = (
                this.state.showAdvanced ? "" : "displayNone"
            );

            if (this.state.deviceMethod === "scanForDevices")
            {
                var proxies = this.state.bacnetProxies.map(function (proxy) {
                    return (
                        { value: proxy.identity, label: proxy.name } 
                    );
                });

                proxySelect = (
                    <tr>
                        <td className="plain"><b>BACNet&nbsp;Proxy&nbsp;Agent </b></td>

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
                    </tr>
                );

                scanLength = (
                    <tr className={advancedClass}>
                        <td><b>Scan&nbsp;Duration&nbsp;(sec)</b></td>
                        <td className="plain"
                            colSpan={4}>
                            <input 
                                style={wideStyle}
                                type="number"
                                min="0"
                                onChange={this._onScanLength}
                                value={this.state.scan_length}></input>
                        </td>
                    </tr>
                );
            }

            var buttonStyle = {
                height: "24px"
            }

            var deviceRangeStyle = {
                width: "100%"
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
                                    <td className="plain" style={tdStyle}>                                        
                                        <b>Device&nbsp;ID&nbsp;Range</b>
                                    </td>
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
                                </tr>
                                <tr>
                                    <td className="plain advanced-toggle" colSpan="5">
                                        <a onClick={this._toggleAdvanced}>Advanced Options</a>
                                    </td>
                                </tr>
                                <tr className={advancedClass}>
                                    <td><b>Address</b></td>
                                    <td className="plain"
                                        colSpan={4}>
                                        <input 
                                            style={wideStyle}
                                            type="text"
                                            onChange={this._onAddress}
                                            value={this.state.address}></input>
                                    </td>
                                </tr>
                                {scanLength}
                            </tbody>
                        </table>
                    </div>                
                </div>
            )

            var scanOptionsStyle = {
                float: "left"
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
                    spinnerContent = <i className="fa fa-cog fa-spin fa-2x margin-bottom"></i>;
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
                var tooltipStyle = {
                    display: (this.state.showTooltip ? "block" : "none"),
                    position: "absolute",
                    top: this.state.tooltipY + "px",
                    left: this.state.tooltipX + "px"
                };

                var toolTipClasses = (this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer");

                scanButton = (
                    <div style={scanOptionsStyle}>  
                        <div className={toolTipClasses}
                            style={tooltipStyle}>
                            <div className="tooltip_inner">
                                <div className="opaque_inner">
                                    Find&nbsp;Devices
                                </div>
                            </div>
                        </div>                   
                        <div className="scanningSpinner tooltip_target" 
                            style={buttonStyle} 
                            onClick={this._onStartScan}
                            onMouseEnter={this._showTooltip}
                            onMouseLeave={this._hideTooltip}>
                            <i className="fa fa-cog fa-2x margin-bottom"></i>
                        </div>
                    </div>
                );
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

            var cellStyle = {
                verticalAlign: "top"
            };

            deviceContent = (
                <div className="device-box device-scan">
                    <table className="config-devices-table">
                        <tbody>
                            <tr>
                                <td className="plain" style={cellStyle}>
                                    <b>Platform: </b>
                                </td>
                                <td className="plain" style={cellStyle}>{platform.name}</td>
                                <td className="plain" style={cellStyle}></td>
                                <td className="plain" style={cellStyle}></td>
                            </tr>
                            <tr>
                                <td className="plain" style={cellStyle}><b>Method: </b></td>
                                <td className="plain" style={cellStyle}>{methodSelect}</td>  
                                <td className="plain" style={cellStyle}>{scanOptions}</td>
                                <td className="plain" style={cellStyle}> {scanButton} </td>
                            </tr>
                        </tbody>
                    </table>
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
            <div className="view config-devices"
                ref="config-device-ref">   
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

    var state = {};
    state.platform = devicesStore.getPlatform();

    if (state.platform)
    {
        state.bacnetProxies = platformsStore.getRunningBacnetProxies(state.platform.uuid);
        state.deviceMethod = (state.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");

        state.deviceStart = "";
        state.deviceEnd = "";
        state.address = "";
        state.scan_length = "";
        state.showAdvanced = false;

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

        state.showTooltip = false;
        state.tooltipX = 0;
        state.tooltooltipY = 0;
    }

    return state;
}

function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

export default ConfigureDevices;