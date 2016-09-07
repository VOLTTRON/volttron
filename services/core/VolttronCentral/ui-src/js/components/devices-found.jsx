'use strict';

import React from 'react';
import io from 'socket';
import BaseComponent from './base-component';
import ConfigureRegistry from './configure-registry';

var ConfirmForm = require('./confirm-form');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesStore = require('../stores/devices-store');
let socket = io('https://localhost:3000');
var CsvParse = require('babyparse');

class DevicesFound extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange', '_uploadRegistryFile');

        this.state = {};
        this.state.devices = devicesStore.getDevices(props.platform, props.bacnet);

        if (socket)
        {
            socket.on('server:event', data => {
                console.log("data: " + data);
            });
        }
    }
    componentDidMount() {
        devicesStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount() {
        devicesStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {
        var devices = devicesStore.getDevices(this.props.platform, this.props.bacnet);
        this.props.devicesloaded(devices.length > 0);
        this.setState({devices: devices});
    }
    _configureDevice(device) {

        device.configuring = !device.configuring;
        devicesActionCreators.configureDevice(device);
    }
    _uploadRegistryFile(evt) {

        var csvFile = evt.target.files[0];

        if (!csvFile)
        {
            return;
        }

        var deviceId = evt.target.dataset.key;
        var device = this.state.devices.find(function (device) {
            return device.id === deviceId;
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

                    // this.setState({registry_config: this.state.registry_config});
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
                        devicesActionCreators.loadRegistry(device, results.data, fileName);
                        console.log(JSON.stringify(results.data));
                    }
                }

            }.bind(this)

            reader.readAsText(csvFile); 
        }
        else
        {
            alert("Couldn't find device by ID " + deviceId);
        }               
    }
    render() {        
        
        var devicesContainer;
        if (this.state.devices.length)
        {
            var devices = 
                this.state.devices.map(function (device) {

                    var deviceId = device.id;

                    var tds = device.items.map(function (d, i) {
                            return (<td key={d.key + "-" + i} className="plain">{ d.value }</td>)
                        });

                    return (
                        <tr key={deviceId}>
                            <td key={"config-arrow-" + deviceId} className="plain">
                                <div className={ device.configuring ? "configure-arrow rotateConfigure" : "configure-arrow" }
                                    onClick={this._configureDevice.bind(this, device)}>
                                        &#9654;
                                </div>
                            </td>

                            { tds }

                            <td key={"file-upload-" + deviceId} className="plain">
                                <div className="fileButton">
                                    <div><i className="fa fa-file"></i></div>
                                    <input 
                                        className="uploadButton" 
                                        type="file"
                                        data-key={deviceId}
                                        onChange={this._uploadRegistryFile}/>
                                </div>
                            </td>
                        </tr>
                    );

                }, this); 

            var ths = this.state.devices[0].items.map(function (d, i) {
                            return (<th key={d.key + "-" + i + "-th"} className="plain">{d.label}</th>); 
                        }); 

            if (devices.length)
            {
                for (var i = devices.length - 1; i >= 0; i--)
                {
                    var device = this.state.devices.find(function (dev) {
                        return dev.id === devices[i].key;
                    });

                    if (device) {
                        if (device.registryConfig.length > 0)
                        {
                            var configureRegistry = (
                                <tr key={"config-" + device.id}>
                                    <td colSpan={7}>
                                        <ConfigureRegistry device={device}/>
                                    </td>
                                </tr>
                            );

                            devices.splice(i + 1, 0, configureRegistry);
                        }
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

export default DevicesFound;