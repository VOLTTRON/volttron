'use strict';

import React from 'react';
import BaseComponent from './base-component';
import CheckBox from './check-box';
import ControlButton from './control-button';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');

class ConfigDeviceForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_updateSetting", "_checkItem", "_updateCampus", "_updateBuilding",
            "_updateUnit", "_updatePath", "_onSubmit");

        this.state = {};
    
        if (this.props.config)
        {
            this.state.settings = initializeSettings(this.props.config.driver_type, this.props.config);
            this.state.driver_config = initializeDriverConfig(
                this.props.config.driver_config.device_address, 
                this.props.config.driver_config.device_id,
                this.props.config.driver_config.proxy_address
            );

            var nameParts = this.props.device.name.split("/");

            this.state.campus = nameParts[0];
            this.state.building = nameParts[1];
            this.state.unit = nameParts[2];
            this.state.path = "";

            for (var i = 3; i < nameParts.length; i++)
            {
                this.state.path = this.state.path + "/" + nameParts[i];
            }

            this.state.physicalDeviceName = this.props.config.physicalDeviceName;
            this.state.configUpdate = true;
        }
        else
        {
            var settingsTemplate = devicesStore.getSettingsTemplate();

            this.state.campus = (settingsTemplate ? settingsTemplate.campus : "");
            this.state.building = (settingsTemplate ? settingsTemplate.building : "");
            this.state.unit = "";
            this.state.path = "";

            this.state.settings = initializeSettings(this.props.device.type, null, settingsTemplate);
            this.state.driver_config = initializeDriverConfig(
                this.props.device.address, 
                this.props.device.id, 
                this.props.device.bacnetProxyIdentity
            );

            this.state.physicalDeviceName = this.props.device.name;

            this.state.configUpdate = false;
        }
        
    }
    _updateSetting(evt) {
        var key = evt.currentTarget.dataset.setting;

        if (this.state.settings[key].type === "number")
        {
            if (evt.target.value > 0 || evt.target.value === "")
            {
                this.state.settings[key].value = evt.target.value;
            }
        }
        else
        {
            this.state.settings[key].value = evt.target.value;
        }
        
        this.setState({settings: this.state.settings});
    }
    _checkItem(checked, key) {
        this.state.settings[key].value = checked;
        this.setState({settings: this.state.settings});
    }
    _updateCampus(evt) {
        this.setState({campus: evt.target.value.replace(/\//g, "").replace(/ /g, "_")});
    }
    _updateBuilding(evt) {
        this.setState({building: evt.target.value.replace(/\//g, "").replace(/ /g, "_")});
    }
    _updateUnit(evt) {
        this.setState({unit: evt.target.value.replace(/\//g, "").replace(/ /g, "_")});
    }
    _updatePath(evt) {
        this.setState({path: evt.target.value.replace(/ /g, "_")});
    }
    _onCancelClick(e) {
        modalActionCreators.closeModal();
    }
    _onSubmit(e) {

        e.preventDefault();

        var settings = {
            config: this.state.settings,
            campus: this.state.campus,
            building: this.state.building,
            unit: this.state.unit,
            path: this.state.path
        };

        var informalName = settings.campus + "/" + settings.building + "/" + 
                            settings.unit + settings.path;

        var config_name =  "devices/" + informalName;

        var allowDevice = true;

        if (!this.state.configUpdate) 
        {
            var preppedPath = "";

            if (settings.path) // If it's a subdevice ...
            {
                preppedPath = (settings.path.indexOf("/") === 0 ? settings.path : "/" + settings.path);

                if (preppedPath.lastIndexOf("/") === preppedPath.length - 1) // if ends with "/", trim it
                {
                    preppedPath = preppedPath.substring(0, preppedPath.length - 2);
                }

                informalName = settings.campus + "/" + settings.building + "/" + 
                                settings.unit + preppedPath;

                config_name =  "devices/" + informalName;

                // ... make sure the parent has been configured
                var devicesList = devicesStore.getDevicesList(this.props.device.platformUuid);

                var index = informalName.lastIndexOf("/");

                var parent = informalName.substring(0, index);

                var parentInTree = Object.keys(devicesList).find(function (device) {
                    return parent === device;
                });

                allowDevice = (typeof parentInTree !== "undefined");
            }
        }
        
        if (allowDevice)
        {
            settings.config.driver_config = this.state.driver_config;
            settings.config.registry_config = "config://" + this.props.registryFile;
            settings.config.physicalDeviceName = this.state.physicalDeviceName;
            
            var announce = true;

            devicesActionCreators.saveConfig(
                this.props.device, 
                this.state.configUpdate, 
                announce, 
                config_name, 
                settings
            );

            if (!this.props.config)
            {
                modalActionCreators.closeModal();
            }
        }
        else
        {
            var message = "Unable to add subdevice " + informalName + " because the parent " +
                "device hasn't been added. Add parent devices first, then subdevices.";
            
            var highlight = informalName;
            var orientation = "center";

            statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
        }
        
    }
    render() {   

        var firstStyle = {
            width: "30%"
        }

        var secondStyle = {
            width: "50%"
        }

        var editableAttributes = [];

        for (var key in this.state.settings)
        {
            if (typeof this.state.settings[key] == "object" && 
                this.state.settings[key].hasOwnProperty("value"))
            {
                var setting;

                if (this.state.settings[key].type === "bool")
                {
                    if (key !== "publish_depth_first")
                    {
                        setting = (
                            <tr key={key}>
                                <td style={firstStyle}>{this.state.settings[key].label}</td>
                                <td style={secondStyle}
                                    className="plain">
                                    <div className="centerContent flexContent"
                                        width="100%">
                                        <CheckBox 
                                            dataItem={key}
                                            oncheck={this._checkItem}
                                            selected={this.state.settings[key].value}
                                            controlClass="flexChild">
                                        </CheckBox>
                                    </div>
                                </td>
                            </tr>
                        );

                        editableAttributes.push(setting);
                    }
                }
                else
                { 
                    setting = (
                        <tr key={key}>
                            <td style={firstStyle}>{this.state.settings[key].label}</td>
                            <td style={secondStyle}
                                className="plain">
                                <input
                                    className="form__control form__control--block"
                                    type={this.state.settings[key].type}
                                    data-setting={key}
                                    onChange={this._updateSetting}
                                    value={this.state.settings[key].value}
                                />
                            </td>
                        </tr>
                    );

                    editableAttributes.push(setting);
                }
            }
        }

        var configDeviceBox = {
            padding: "0px 50px",
            marginTop: "20px",
            marginBottom: "20px"
        }

        var tooltipX = 320;
        var tooltipY = 150;        
        
        var saveTooltip = {
            "content": "Save Configuration",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        var saveButton = (
            <ControlButton 
                name="saveConfigButton"
                tooltip={saveTooltip}
                fontAwesomeIcon="save"
                clickAction={this._onSubmit}></ControlButton>
        );   

        return (
            <form className="config-device-form" onSubmit={this._onSubmit}>
                <h1>Device Configuration</h1>
                <h4>{this.props.device.name} / {this.props.device.address} / {this.props.device.id}</h4>
                <div className="configDeviceContainer">
                    <div style={configDeviceBox}>
                        <table>
                            <tbody>
                                <tr key="campus">
                                    <td style={firstStyle}>
                                        <span className="required-field">*</span>
                                        Campus
                                    </td>
                                    <td style={secondStyle}
                                        className="plain">
                                        <input
                                            className="form__control form__control--block"
                                            type="text"
                                            onChange={this._updateCampus}
                                            value={this.state.campus}
                                            disabled={this.state.configUpdate}
                                            autoFocus
                                        />
                                    </td>
                                </tr>
                                <tr key="building">
                                    <td style={firstStyle}>
                                        <span className="required-field">*</span>
                                        Building
                                    </td>
                                    <td style={secondStyle}
                                        className="plain">
                                        <input
                                            className="form__control form__control--block"
                                            type="text"
                                            onChange={this._updateBuilding}
                                            value={this.state.building}
                                            disabled={this.state.configUpdate}
                                        />
                                    </td>
                                </tr>
                                <tr key="unit">
                                    <td style={firstStyle}>
                                        <span className="required-field">*</span>
                                        Unit
                                    </td>
                                    <td style={secondStyle}
                                        className="plain">
                                        <input
                                            className="form__control form__control--block"
                                            type="text"
                                            onChange={this._updateUnit}
                                            value={this.state.unit}
                                            disabled={this.state.configUpdate}
                                        />
                                    </td>
                                </tr>
                                <tr key="path">
                                    <td style={firstStyle}>Path</td>
                                    <td style={secondStyle}
                                        className="plain">
                                        <input
                                            className="form__control form__control--block"
                                            type="text"
                                            onChange={this._updatePath}
                                            value={this.state.path}
                                            disabled={this.state.configUpdate}
                                        />
                                    </td>
                                </tr>
                                { editableAttributes }
                            </tbody>
                        </table>
                    </div>
                </div>
                <div className="form__actions config-buttons">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                    >
                        Cancel
                    </button>
                    <button className="button"
                        disabled={!this.state.campus || !this.state.building || !this.state.unit}>
                        Save
                    </button>
                </div>
                <div className="reconfig-button">
                    <div className="inlineBlock">
                        {saveButton}
                    </div>                    
                </div>
            </form>
        );
    }
};

var initializeDriverConfig = (address, id, bacnetProxy) => {
    var driver_config = {
        device_address: address,
        device_id: id,
        proxy_address: bacnetProxy
    };

    return driver_config;
}

var initializeSettings = (type, savedConfig, settingsTemplate) => {

    var settings = {};

    switch (type)
    {
        case "bacnet":
            
            settings = {
                driver_type: {
                    value: "bacnet", 
                    label: "Driver Type",
                    type: "text"
                },
                max_per_request: {
                    value: 10000,
                    label: "Maximum Per Request",
                    type: "number"
                },
                interval: {
                    value: 60,
                    label: "Interval (seconds)",
                    type: "number"
                },
                timezone: {
                    value: "", 
                    label: "Timezone",
                    type: "text"
                },
                heartbeat_point: {
                    value: "", 
                    label: "Heartbeat Point",
                    type: "text"
                },
                minimum_priority: {
                    value: 8, 
                    label: "Minimum Priority",
                    type: "number"
                },
                publish_depth_first: {
                    value: true,
                    label: "Publish Depth-First",
                    type: "bool"
                },
                publish_breadth_first: {
                    value: false,
                    label: "Publish Breadth-First",
                    type: "bool"
                },
                publish_breadth_first_all: {
                    value: false,
                    label: "Publish Breadth-First All",
                    type: "bool"
                }
            }
                
            if (settingsTemplate)
            {
                for (var key in settings)
                {
                    settings[key].value = (
                        settingsTemplate.config[key].hasOwnProperty("value") ? 
                            settingsTemplate.config[key].value : 
                                settingsTemplate.config[key]);
                }
            }

            if (savedConfig)
            {
                for (var key in settings)
                {
                    settings[key].value = savedConfig[key];
                }
            }

            break;
    }

    return settings;
}

export default ConfigDeviceForm;
