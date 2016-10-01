'use strict';

import React from 'react';
import BaseComponent from './base-component';
import ConfigureRegistry from './configure-registry';

var ConfirmForm = require('./confirm-form');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');

var CsvParse = require('babyparse');

var devicesWs, devicesWebsocket;
var pointsWs, pointsWebsocket;

class DevicesFound extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange', '_uploadRegistryFile', '_setUpDevicesSocket', '_setUpPointsSocket', 
            '_focusOnDevice');

        this.state = {};       
    }
    componentDidMount() {
        // devicesStore.addChangeListener(this._onStoresChange);
        this._setUpDevicesSocket()
    }
    componentWillUnmount() {
        // devicesStore.removeChangeListener(this._onStoresChange);
    }
    componentWillReceiveProps(nextProps) {
        if (this.props.canceled !== nextProps.canceled)
        {
            if (nextProps.canceled)
            {
                if (typeof devicesWs !== "undefined" && devicesWs !== null)
                {
                    devicesWs.close();
                    devicesWs = null;
                }
            }
            else
            {
                this._setUpDevicesSocket();
            }
        }

        if (nextProps.devices !== this.props.devices)
        {
            this.props.devicesloaded(nextProps.devices.length > 0);
        }
    }
    _setUpDevicesSocket() {

        if (typeof pointsWs !== "undefined" && pointsWs !== null)
        {
            pointsWs.close();
            pointsWs = null;
        }

        devicesWebsocket = "ws://" + window.location.host + "/vc/ws/iam";
        if (window.WebSocket) {
            devicesWs = new WebSocket(devicesWebsocket);
        }
        else if (window.MozWebSocket) {
            devicesWs = MozWebSocket(devicesWebsocket);
        }

        devicesWs.onmessage = function(evt)
        {
            devicesActionCreators.deviceDetected(evt.data, this.props.platform, this.props.bacnet);

            var warnings = devicesStore.getWarnings();

            if (!objectIsEmpty(warnings))
            {
                for (var key in warnings)
                {
                    var values = warnings[key].items.join(", ");

                    statusIndicatorActionCreators.openStatusIndicator(
                        "error", 
                        warnings[key].message + "ID: " + values, 
                        values, 
                        "left"
                    );
                }
            }

        }.bind(this);
    }    
    _setUpPointsSocket() {
        
        if (typeof devicesWs !== "undefined" && devicesWs !== null)
        {
            devicesWs.close();
            devicesWs = null;
        }

        pointsWebsocket = "ws://" + window.location.host + "/vc/ws/configure";
        if (window.WebSocket) {
            pointsWs = new WebSocket(pointsWebsocket);
        }
        else if (window.MozWebSocket) {
            pointsWs = MozWebSocket(pointsWebsocket);
        }

        pointsWs.onmessage = function(evt)
        {
            devicesActionCreators.pointReceived(evt.data, this.props.platform, this.props.bacnet);

            var warnings = devicesStore.getWarnings();

            if (!objectIsEmpty(warnings))
            {
                for (var key in warnings)
                {
                    var values = warnings[key].items.join(", ");

                    statusIndicatorActionCreators.openStatusIndicator(
                        "error", 
                        warnings[key].message + "ID: " + values, 
                        values, 
                        "left"
                    );
                }
            }

        }.bind(this);
    }
    _onStoresChange() {
        // var devices = devicesStore.getDevices(this.props.platform, this.props.bacnet); 
    }
    _configureDevice(device) {
        
        devicesActionCreators.focusOnDevice(device.id, device.address);

        device.showPoints = !device.showPoints;

        // Don't set up the socket again if we've already set it up once.
        // So before setting device.configuring to true, first check
        // if we're going to show points but haven't started configuring yet.
        // If so, set up the socket and set configuring to true.
        if (device.showPoints && !device.configuring)
        {
            this._setUpPointsSocket();
            device.configuring = true;
            devicesActionCreators.configureDevice(device);
        }
        else
        {
            devicesActionCreators.toggleShowPoints(device);
        }
    }
    _focusOnDevice(evt) {
        var deviceId = evt.target.dataset.id;
        var address = evt.target.dataset.address;
        devicesActionCreators.focusOnDevice(deviceId, address);
    }
    _uploadRegistryFile(evt) {
        
        var csvFile = evt.target.files[0];

        if (!csvFile)
        {
            return;
        }

        var deviceId = evt.target.dataset.id;
        var deviceAddress = evt.target.dataset.address;

        var device = this.props.devices.find(function (device) {
            return ((device.id === deviceId) && (device.address === deviceAddress));
        });

        if (device)
        {
            var fileName = evt.target.value;        

            var reader = new FileReader();

            reader.onload = function (e) {

                var contents = e.target.result;

                var results = parseCsvFile(contents);

                if (results.errors.length)
                {
                    var errorMsg = "The file wasn't in a valid CSV format.";

                    modalActionCreators.openModal(
                        <ConfirmForm
                            promptTitle="Error Reading File"
                            promptText={ errorMsg }
                            cancelText="OK"
                        ></ConfirmForm>
                    );
                }
                else 
                {
                    if (results.warnings.length)
                    {    
                        var warningMsg = results.warnings.map(function (warning) {
                                    return warning.message;
                                });                

                        modalActionCreators.openModal(
                            <ConfirmForm
                                promptTitle="File Upload Notes"
                                promptText={ warningMsg }
                                cancelText="OK"
                            ></ConfirmForm>
                        );
                    }

                    if (!results.meta.aborted)            
                    {
                        // this.setState({registry_config: fileName});       
                        devicesActionCreators.loadRegistry(device.id, device.address, results.data, fileName);
                    }
                }

            }.bind(this)

            reader.readAsText(csvFile); 
        }
        else
        {
            alert("Couldn't find device by ID " + deviceId + " and address " + deviceAddress);
        }               
    }
    render() {        
        
        var devicesContainer;
        if (this.props.devices.length)
        {
            var devices = 
                this.props.devices.map(function (device) {

                    var deviceId = device.id;
                    var deviceAddress = device.address;

                    var tds = device.items.map(function (d, i) {
                            return (<td 
                                        key={d.key + "-" + i} 
                                        className="plain"
                                        data-id={deviceId}
                                        data-address={deviceAddress}
                                        onClick={this._focusOnDevice}>{ d.value }</td>)
                        }, this);

                    return (
                        <tr key={deviceId + deviceAddress}>
                            <td key={"config-arrow-" + deviceId + deviceAddress} className="plain">
                                <div className={ device.showPoints ? "configure-arrow rotateConfigure" : "configure-arrow" }                                    
                                    onClick={this._configureDevice.bind(this, device)}>
                                        &#9654;
                                </div>
                            </td>

                            { tds }

                            <td key={"file-upload-" + deviceId + deviceAddress} className="plain">
                                <div className="fileButton">
                                    <div><i className="fa fa-file"></i></div>
                                    <input 
                                        className="uploadButton" 
                                        type="file"
                                        data-id={deviceId}
                                        data-address={deviceAddress}
                                        onChange={this._uploadRegistryFile}
                                        onFocus={this._focusOnDevice}/>
                                </div>
                            </td>
                        </tr>
                    );

                }, this); 

            var ths = this.props.devices[0].items.map(function (d, i) {
                            return (<th key={d.key + "-" + i + "-th"} className="plain">{d.label}</th>); 
                        }); 

            if (devices.length)
            {
                for (var i = devices.length - 1; i >= 0; i--)
                {
                    var device = this.props.devices.find(function (dev) {
                        return ((dev.id + dev.address) === devices[i].key);
                    });

                    if (device) {
                        
                        var configureRegistry = (
                            <tr key={"config-" + device.id + device.address}>
                                <td colSpan={7}>
                                    <ConfigureRegistry device={device}/>
                                </td>
                            </tr>
                        );

                        devices.splice(i + 1, 0, configureRegistry);
                    }

                }
            }

            devicesContainer = (
                <table>
                    <tbody>
                        <tr>
                            <th className="plain"></th>
                            { ths }
                            <th className="plain"></th>
                        </tr>
                        {devices}
                    </tbody>
                </table>
            );   
        }
        else
        {
            if (this.props.canceled)
            {
                devicesContainer = <div className="no-devices">No devices were detected.</div>;
            }
            else
            {
                devicesContainer = <div className="no-devices">Searching for devices ...</div>;
            }            
        }

        return (
            <div className="devicesFoundContainer">
                <div className="devicesFoundBox">
                    {devicesContainer}
                </div>
            </div>
        );
    }
};

var parseCsvFile = (contents) => {

    var results = CsvParse.parse(contents);

    var registryValues = [];

    var header = [];

    var data = results.data;

    results.warnings = [];

    if (data.length)
    {
        header = data.slice(0, 1);
    }

    var template = [];

    if (header[0].length)
    {
        header[0].forEach(function (column) {
            template.push({ "key": column.replace(/ /g, "_"), "value": null, "label": column });
        });

        var templateLength = template.length;

        if (data.length > 1)
        {
            var rows = data.slice(1);

            var rowsCount = rows.length;

            rows.forEach(function (r, num) {

                if (r.length)
                {   
                    if (r.length !== templateLength) 
                    {                           
                        if ((num === (rowsCount - 1)) && (r.length === 0 || ((r.length === 1) && (r[0] === "") )))
                        {
                            // Suppress the warning message if the out-of-sync row is the last one and it has no elements
                            // or all it has is an empty point name -- which can happen naturally when reading the csv file
                        }
                        else
                        {
                            results.warnings.push({ message: "Row " +  num + " was omitted for having the wrong number of columns."});
                        }
                    }
                    else
                    {
                        if (r.length === templateLength) // Have to check again, to keep from adding the empty point name
                        {                                // in the last row
                            var newTemplate = JSON.parse(JSON.stringify(template));

                            var newRow = [];

                            r.forEach( function (value, i) {
                                newTemplate[i].value = value;

                                newRow.push(newTemplate[i]);
                            });

                            registryValues.push(newRow);
                        }
                    }
                }
            });
        }
        else
        {
            registryValues = template;
        }
    }

    results.data = registryValues;

    return results;
}

function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

export default DevicesFound;