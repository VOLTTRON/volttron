'use strict';

import React from 'react';
import BaseComponent from './base-component';
import ConfigureRegistry from './configure-registry';
import ControlButton from './control-button';
import FileUploadButton from './control_buttons/file-upload-button';
import FileSelectButton from './control_buttons/file-select-button';

var ConfirmForm = require('./confirm-form');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesStore = require('../stores/devices-store');

class DevicesFound extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_focusOnDevice', '_enableRefreshPoints', '_refreshDevicePoints');

        this.state = {
            savedRegistryFiles: {},
            enableRefreshPoints: []
        };       
    }
    componentWillReceiveProps(nextProps) {
        if (nextProps.devices !== this.props.devices)
        {
            this.props.devicesloaded(nextProps.devices.length > 0);

            this._enableRefreshPoints(nextProps.devices);
        }
    }
    _enableRefreshPoints(devices) {

        var refreshPointsList = [];

        devices.forEach(function (device) {
            var enableRefreshPoints = devicesStore.enableBackupPoints(
                device.id, device.address
            );

            if (enableRefreshPoints)
            {
                refreshPointsList.push({
                    id: device.id,
                    address: device.address
                });
            }
        });

        this.setState({ enableRefreshPoints: refreshPointsList });
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
    _refreshDevicePoints(device) {

        var confirmAction = devicesActionCreators.refreshDevicePoints.bind(this, device.id, device.address);
        
        modalActionCreators.openModal(
            <ConfirmForm
                promptTitle="Reload Device Points"
                promptText="Reload the device's original points?"
                confirmText="Reload"
                cancelText="Cancel"
                onConfirm={ confirmAction }
            ></ConfirmForm>
        );
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

                    var refreshPointsButton;

                    var enableRefresh = this.state.enableRefreshPoints.find(function(enable) {
                        return enable.id === deviceId && enable.address === deviceAddress;
                    });

                    if (typeof enableRefresh !== "undefined")
                    {
                        var refreshPointsTooltip = {
                            content: <span>Reload&nbsp;Points From&nbsp;Device</span>,
                            tooltipClass: "colorBlack",
                            "x": -20,
                            "y": -70
                        }

                        refreshPointsButton = (
                            <div className="refreshPointsButton">
                                <ControlButton
                                    name={"refresh-points-" + deviceId + "-" + rowIndex}
                                    tooltip={refreshPointsTooltip}
                                    controlclass="refresh-points-button"
                                    fontAwesomeIcon="undo"
                                    clickAction={this._refreshDevicePoints.bind(this, device)}/>
                            </div>
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
                                    <FileSelectButton 
                                        deviceId={deviceId}
                                        deviceAddress={deviceAddress}
                                        platformUuid={device.platformUuid}
                                        agentDriver={device.agentDriver}
                                        tooltipY={-70}
                                        tooltipX={-20}/>
                                    <FileUploadButton
                                        onupload={this._focusOnDevice}
                                        onfocus={this._focusOnDevice}
                                        deviceId={deviceId}
                                        deviceAddress={deviceAddress}
                                        tooltipY={-80}
                                        tooltipX={-30}/>
                                    {refreshPointsButton}
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