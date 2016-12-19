'use strict';

import React from 'react';
import ReactDOM from 'react-dom';
import BaseComponent from './base-component';
import ConfigureRegistry from './configure-registry';
import ConfigDeviceForm from './config-device-form';
import FileUploadButton from './control_buttons/file-upload-button';
import FileSelectButton from './control_buttons/file-select-button';
import FileExportButton from './control_buttons/file-export-button';

import Select from 'react-select-me';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');


class ReconfigureDevice extends BaseComponent {    
    constructor(props) {
        super(props);
        this._bind('_onStoresChange', '_onConfigChange', '_validateDataFile');

        this.state = getStateFromStore();
    }
    componentDidMount() {
        
        devicesStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount() {
        devicesStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {
        
        var reconfiguring = devicesStore.reconfiguringDevice();

        if (reconfiguring)
        {
            this.setState(getStateFromStore);
        }
        else
        {
            if (this.state.device)
            {
                this.setState({ 
                    device: devicesStore.getDevice(
                                this.state.device.id, 
                                this.state.device.address
                            )
                });
            }
        }
    }
    _onConfigChange(selection) {
        this.setState({ configFile: selection.value });
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
    render() {        
        
        var registryConfig, deviceConfig, configuration, defaultMessage;

        if (this.state.device) 
        {
            var configOptions = [
                { value: "registryConfig", label: "Registry Config"},
                { value: "deviceConfig", label: "Device Config"}
            ];

            var configSelect = (
                <Select
                    name="config-select"
                    options={configOptions}
                    value={this.state.configFile}
                    onChange={this._onConfigChange}>
                </Select>
            );

            var containerWidth = {
                width: "80px"
            };

            var fileSelectContainer = (
                <div className="fileSelectContainer"
                    style={containerWidth}>
                    <FileSelectButton 
                        deviceId={this.state.device.id}
                        deviceAddress={this.state.device.address}
                        platformUuid={this.state.device.platformUuid}
                        agentDriver={this.state.device.agentDriver}
                        tooltipY={-60}
                        tooltipX={-20}/>
                    <FileUploadButton
                        deviceId={this.state.device.id}
                        deviceAddress={this.state.device.address}
                        tooltipY={-70}
                        tooltipX={-30}/>
                    <FileExportButton
                        deviceId={this.state.device.id}
                        deviceAddress={this.state.device.address}
                        tooltipY={-60}
                        tooltipX={-20}
                        fileName={this.state.configuration.registryFile}/>
                </div>
            );

            var cellStyle = {
                verticalAlign: "top"
            };

            configuration = (
                <div className="">
                    <table className="config-devices-table reconfig">
                        <tbody>
                            <tr>
                                <td className="plain" style={cellStyle}>
                                    <b>Registry Config: </b>
                                </td>
                                <td className="plain" style={cellStyle}>{this.state.configuration.registryFile} {fileSelectContainer}</td>
                                <td className="plain" style={cellStyle}></td>
                                <td className="plain" style={cellStyle}></td>
                            </tr>
                            <tr>
                                <td className="plain" style={cellStyle}>
                                    <b>Device Config: </b>
                                </td>
                                <td className="plain" style={cellStyle}>{this.state.device.name}</td>
                                <td className="plain" style={cellStyle}></td>
                                <td className="plain" style={cellStyle}></td>
                            </tr>
                            <tr>
                                <td className="plain" style={cellStyle}><b>File to Edit: </b></td>
                                <td className="plain" style={cellStyle}>{configSelect}</td>  
                                <td className="plain" style={cellStyle}></td>
                                <td className="plain" style={cellStyle}></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            );
            
            if (this.state.configFile === "registryConfig")
            {
                registryConfig = (
                    <ConfigureRegistry device={this.state.device} 
                        dataValidator={this._validateDataFile}
                        registryFile={this.state.configuration.registryFile}/>
                );
            }
            else
            {
                deviceConfig = (
                    <ConfigDeviceForm device={this.state.device}
                        config={this.state.configuration} 
                        registryFile={this.state.configuration.registryFile}/>
                );
            }
        }
        else
        {
            defaultMessage = (
                <div>To reconfigure a device, click on the <i className="fa fa-wrench"></i> button next to the device in the side tree.</div>
            );
        }

        return (
            <div className="view">   
                <h2>Reconfigure Device</h2> 
                {defaultMessage}      
                {configuration} 
                <div className="device-box device-container">
                    {registryConfig}
                    {deviceConfig}
                </div> 

            </div> 
        );
    }
};

function getStateFromStore() {

    var state = {};
    var reconfiguration = devicesStore.getReconfiguration();

    if (!objectIsEmpty(reconfiguration))
    {
        var deviceId = reconfiguration.driver_config.device_id;
        var deviceAddress = reconfiguration.driver_config.device_address;

        state = {
            device: devicesStore.getDeviceRef(deviceId, deviceAddress, reconfiguration.deviceName),
            configuration: reconfiguration,
            configFile: "registryConfig"
        };
    }

    return state;
}

function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

export default ReconfigureDevice;