'use strict';

import React from 'react';
import BaseComponent from './base-component';
import ConfigureRegistry from './configure-registry';
import ControlButton from './control-button';

var ConfirmForm = require('./confirm-form');
var RegistryFilesSelector = require('./registry-files-selector');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');

import {CsvParse} from '../lib/csvparse';

class DevicesFound extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_uploadRegistryFile', '_focusOnDevice', '_showFileButtonTooltip',
                    '_loadSavedRegistryFiles');

        this.state = {
            triggerTooltip: -1,
            savedRegistryFiles: {}
        };       
    }
    componentWillReceiveProps(nextProps) {
        if (nextProps.devices !== this.props.devices)
        {
            this.props.devicesloaded(nextProps.devices.length > 0);
        }
    }
    _configureDevice(device) {
        
        devicesActionCreators.focusOnDevice(device.id, device.address);

        device.showPoints = !device.showPoints;

        // Don't scan for points again if already scanning
        if (device.showPoints && !device.configuringStarted)
        {
            device.configuring = true;
            devicesActionCreators.configureDevice(device, this.props.bacnet);
        }
        else
        {
            devicesActionCreators.toggleShowPoints(device); 
        }
    }
    _focusOnDevice(deviceId, deviceAddress, evt) {
        devicesActionCreators.focusOnDevice(deviceId, deviceAddress);
    }
    _showFileButtonTooltip(showTooltip, rowIndex) {
        
        var triggerTooltip = -1;

        if (showTooltip)
        {
            triggerTooltip = rowIndex;
        }

        this.setState({ triggerTooltip: triggerTooltip });
    }
    _loadSavedRegistryFiles(device)
    {
        devicesActionCreators.loadRegistryFiles(device);

        modalActionCreators.openModal(
            <RegistryFilesSelector
                device={device}
                bacnet={this.props.bacnet}>
            </RegistryFilesSelector>
        );
    }
    _validateDataFile(data, callback) {
        
        var keyCells = ["Volttron Point Name", "BACnet Object Type", "Index"];
        var cellsNotFound = JSON.parse(JSON.stringify(keyCells));

        keyCells.forEach(function(keyCell) {

            data.forEach(function (cell) {

                if (keyCell === cell.label)
                {
                    var index = cellsNotFound.indexOf(keyCell);
                    cellsNotFound.splice(index, 1);
                }
            });

        });

        var valid = true;
        if (cellsNotFound.length) 
        {
            valid = false;

            var keyCellsString = cellsNotFound.map(function(cell) { 
                return "\"" + cell + "\""; 
            }).join(", ");

            callback(keyCellsString);
        }

        return valid;
    }
    _uploadRegistryFile(deviceId, deviceAddress, evt) {
        
        var csvFile = evt.target.files[0];

        evt.target.blur();

        if (!csvFile)
        {
            return;
        }

        devicesActionCreators.focusOnDevice(deviceId, deviceAddress);

        var device = this.props.devices.find(function (device) {
            return ((device.id === deviceId) && (device.address === deviceAddress));
        });

        if (device)
        {
            var fileName = evt.target.value;        

            var reader = new FileReader();

            reader.onload = function (e) {

                var contents = e.target.result;

                var results = CsvParse.parseCsvFile(contents);

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

                    if (results.data.length === 0)
                    {
                        modalActionCreators.openModal(
                            <ConfirmForm
                                promptTitle="File Upload Notes"
                                promptText={"There was a problem reading the file. Only one " +
                                    "row was found: either a heading row with no data, " +
                                    "a single data row with no header, or all rows merged into " +
                                    "one with no end-of-line markers."}
                                cancelText="OK"
                            ></ConfirmForm>
                        );
                    }
                    else if (!results.meta.aborted)            
                    {
                        this._validateDataFile(results.data[0], function (cellsNotFound) {
                            var message = "The following column names were not found in " +
                                "the data file: " + cellsNotFound + ". Make sure these " +
                                "columns are present when you save the registry config " +
                                "file, or the device will not be properly configured for Volttron.";
                            statusIndicatorActionCreators.openStatusIndicator("error", message, cellsNotFound);
                        });
                        
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
                this.props.devices.map(function (device, rowIndex) {

                    var deviceId = device.id;
                    var deviceAddress = device.address;

                    var tds = device.items.map(function (d, i) {
                            return (<td 
                                        key={d.key + "-" + i} 
                                        className="plain"
                                        onClick={this._focusOnDevice.bind(this, deviceId, deviceAddress)}>
                                        { d.value }
                                    </td>);
                        }, this);

                    var arrowTooltip = {
                        content: (!device.configuringStarted ? "Get Device Points" : "Hide/Show"),
                        "x": 40,
                        "yOffset": 140
                    }

                    var fileSelectTooltip = {
                        content: "Select Registry File CSV)",
                        tooltipClass: "colorBlack",
                        "x": -20,
                        "y": -120
                    }

                    var fileUploadTooltip = {
                        content: "Import Registry File (CSV)",
                        tooltipClass: "colorBlack",
                        "x": -20,
                        "y": -120
                    }

                    var triggerTooltip = (this.state.triggerTooltip === rowIndex);

                    var configButton;

                    if (!device.configuring)
                    {
                        configButton = (
                            <ControlButton
                                name={"config-arrow-" + deviceId + "-" + rowIndex}
                                tooltip={arrowTooltip}
                                controlclass={ device.showPoints ? "configure-arrow rotateConfigure" : "configure-arrow" }
                                icon="&#9654;"
                                clickAction={this._configureDevice.bind(this, device)}/>
                            );
                    }
                    else
                    {
                        var spinIcon = <span className="configIcon"><i className="fa fa-refresh fa-spin fa-fw"></i></span>;

                        configButton = (
                            <ControlButton
                                name={"config-arrow-" + deviceId + "-" + rowIndex}
                                controlclass="configure-arrow"
                                icon={spinIcon}/>
                            );
                    }

                    return (
                        <tr key={deviceId + deviceAddress}>
                            <td key={"config-arrow-" + deviceId + deviceAddress} className="plain">
                                {configButton}
                            </td>

                            { tds }

                            <td key={"file-upload-" + deviceId + deviceAddress} className="plain">
                                <div className="fileSelectContainer">
                                    <div className="fileSelectButton">
                                        <ControlButton
                                            name={"file-select-" + deviceId + "-" + rowIndex}
                                            tooltip={fileSelectTooltip}
                                            controlclass="file-select-button"
                                            fontAwesomeIcon="file"
                                            clickAction={this._loadSavedRegistryFiles.bind(this, device)}/>
                                    </div>
                                    <div className="fileButton">
                                        <ControlButton
                                            name={"file-upload-" + deviceId + "-" + rowIndex}
                                            tooltip={fileUploadTooltip}
                                            controlclass="file-button"
                                            fontAwesomeIcon="upload"
                                            triggerTooltip={triggerTooltip}/>
                                        <input 
                                            className="uploadButton" 
                                            type="file"
                                            onChange={this._uploadRegistryFile.bind(this, deviceId, deviceAddress)}
                                            onFocus={this._focusOnDevice.bind(this, deviceId, deviceAddress)}
                                            onMouseEnter={this._showFileButtonTooltip.bind(this, true, rowIndex)}
                                            onMouseLeave={this._showFileButtonTooltip.bind(this, false, rowIndex)}/>
                                    </div>
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

                        var pointsCounter;

                        if (device.configuring && device.registryConfig.length)
                        {
                            pointsCounter = (
                                <div key={"pr-" + i} 
                                    className="points-received">
                                    <span>Points received: </span>
                                    <span>{device.registryConfig.length}</span>
                                </div>
                            );
                        } 
                        else
                        {
                            pointsCounter = null;
                        }
                        
                        var configureRegistry = (
                            <tr key={"config-" + device.id + device.address}>
                                <td key={"td-" + i} colSpan={7}>
                                    {pointsCounter}
                                    <ConfigureRegistry device={device} 
                                        dataValidator={this._validateDataFile}/>
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

export default DevicesFound;