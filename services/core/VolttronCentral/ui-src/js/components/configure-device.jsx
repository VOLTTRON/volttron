'use strict';

var React = require('react');
var Router = require('react-router');
var CsvParse = require('babyparse');

var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');

var ConfigureDevice = React.createClass({
    getInitialState: function () {
        return getStateFromStores(this.props.device);
    },
    componentDidMount: function () {
        devicesStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        devicesStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores(this.props.device));
    },
    _configureDevice: function (device) {
        devicesActionCreators.configureDevice(device);
    },
    _updateSetting: function (evt) {
        var newVal = evt.target.value;
        var key = evt.currentTarget.dataset.setting;

        var tmpState = JSON.parse(JSON.stringify(this.state));

        var newSettings = tmpState.settings.map(function (item) {
            if (item.key === key)
            {
                item.value = newVal;                
            }

            return item;
        });

        this.setState({settings: newSettings});
    },
    _updateRegistryPath: function (evt) {
        this.setState({registry_config: evt.target.value});
    },
    _uploadRegistryFile: function (evt) {

        var csvFile = evt.target.files[0];

        if (!csvFile)
        {
            return;
        }

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

                this.setState({registry_config: this.state.registry_config});
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
                    this.setState({registry_config: fileName});       
                    devicesActionCreators.loadRegistry(this.props.device, results.data, fileName);
                }
            }

        }.bind(this)

        reader.readAsText(csvFile);        
    },
    _generateRegistryFile: function () {
        devicesActionCreators.generateRegistry(this.props.device);
    },
    _editRegistryFile: function () {
        devicesActionCreators.editRegistry(this.props.device);
    },
    render: function () {        
        
        var attributeRows = 
            this.props.device.map(function (device) {

                return (
                    <tr>
                        <td>{device.label}</td>
                        <td className="plain">{device.value}</td>
                    </tr>
                );

            });

        var tableStyle = {
            backgroundColor: "#E7E7E7"
        }

        var uneditableAttributes = 
            <table style={tableStyle}>
                <tbody>

                    { attributeRows }

                    <tr>
                        <td>Proxy Address</td>
                        <td className="plain">10.0.2.15</td>
                    </tr>
                    <tr>
                        <td>Network Interface</td>
                        <td className="plain">UDP/IP</td>
                    </tr>
                    <tr>
                        <td>Campus</td>
                        <td className="plain">PNNL</td>
                    </tr>

                </tbody>
            </table>;

        var buttonStyle = {
            height: "24px",
            width: "66px",
            lineHeight: "18px"
        }

        var firstStyle = {
            width: "30%",
            textAlign: "right"
        }

        var secondStyle = {
            width: "50%"
        }

        var buttonColumns = {
            width: "8%"
        }

        var settingsRows = 
            this.state.settings.map(function (setting) {

                var stateSetting = this.state.settings.find(function (s) {
                    return s.key === setting.key;
                })

                return (
                    <tr>
                        <td style={firstStyle}>{setting.label}</td>
                        <td style={secondStyle}
                            className="plain">
                            <input
                                className="form__control form__control--block"
                                type="text"
                                data-setting={setting.key}
                                onChange={this._updateSetting}
                                value={stateSetting.value}
                            />
                        </td>
                    </tr>
                );
            }, this);


        var editButton = ( this.state.registry_saved ?
                                <td 
                                    style={buttonColumns}
                                    className="plain">
                                    <button 
                                        style={buttonStyle} onClick={this._editRegistryFile}>Edit</button>
                                </td> :

                                        <td className="plain"></td>
            );

        var registryConfigRow = 
            <tr>
                <td style={firstStyle}>Registry Configuration File</td>
                <td 
                    style={secondStyle}
                    className="plain">
                    <input
                        className="form__control form__control--block"
                        type="text"
                        onChange={this._updateRegistryPath}
                        value={this.state.registry_config}
                    />
                </td>
                <td 
                    style={buttonColumns}
                    className="plain">
                    <div className="buttonWrapper">
                        <div>Upload</div>
                        <input 
                            className="uploadButton" 
                            type="file"
                            onChange={this._uploadRegistryFile}/>
                    </div>
                </td>
                { editButton }
                <td 
                    style={buttonColumns}
                    className="plain">
                    <button 
                        style={buttonStyle} onClick={this._generateRegistryFile}>Generate</button>
                </td>
            </tr>

        var editableAttributes = 
            <table>
                <tbody>
                    { settingsRows }
                    { registryConfigRow }
                </tbody>
            </table>

        var boxPadding = (this.state.registry_saved ? "60px" : "60px 100px");

        var configDeviceBox = {
            padding: boxPadding,
            marginTop: "20px",
            marginBottom: "20px",
            border: "1px solid black"
        }

        return (
            <div className="configDeviceContainer">
                <div className="uneditableAttributes">
                    { uneditableAttributes }
                </div>
                <div style={configDeviceBox}>                    
                    { editableAttributes }
                </div>
            </div>
        );
    },
});

function getStateFromStores(device) {

    var registryFile = devicesStore.getRegistryFile(device);

    return {
        settings: [
            { key: "unit", value: "", label: "Unit" },
            { key: "building", value: "", label: "Building" },
            { key: "path", value: "", label: "Path" },
            { key: "interval", value: "", label: "Interval" },
            { key: "timezone", value: "", label: "Timezone" },
            { key: "heartbeat_point", value: "", label: "Heartbeat Point" },
            { key: "minimum_priority", value: "", label: "Minimum Priority" },
            { key: "max_objs_per_read", value: "", label: "Maximum Objects per Read" }
        ],
        registry_config: registryFile,
        registry_saved: (registryFile ? true : false)
    };
}

function parseCsvFile(contents) {

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

                if ((r.length !== templateLength) && (num !== (rowsCount - 1)))
                {
                    results.warnings.push({ message: "Row " +  num + " was omitted for having the wrong number of columns."});
                }
                else
                {
                    var newTemplate = JSON.parse(JSON.stringify(template));

                    var newRow = [];

                    r.forEach( function (value, i) {
                        newTemplate[i].value = value;

                        newRow.push(newTemplate[i]);
                    });

                    registryValues.push(newRow);
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



module.exports = ConfigureDevice;