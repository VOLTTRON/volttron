'use strict';

import React from 'react';
import BaseComponent from './base-component';
import CheckBox from './check-box';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');

class ConfigDeviceForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_updateSetting", "_checkItem", "_updateCampus", "_updateBuilding",
            "_updateUnit", "_updatePath", "_onSubmit");

        var settingsTemplate = devicesStore.getSettingsTemplate();

        this.state = {
            campus: (settingsTemplate ? settingsTemplate.campus : ""),
            building: (settingsTemplate ? settingsTemplate.building : ""),
            unit: "",
            path: ""
        };

        this.state.settings = initializeSettings(this.props.device.type, settingsTemplate);
        this.state.driver_config = initializeDriverConfig(this.props.device);
    }
    _updateSetting(evt) {
        var key = evt.currentTarget.dataset.setting;

        this.state.settings[key].value = evt.target.value;
        this.setState({settings: this.state.settings});
    }
    _checkItem(checked, key) {
        this.state.settings[key].value = checked;
        this.setState({settings: this.state.settings});
    }
    _updateCampus(evt) {
        this.setState({campus: evt.target.value.replace(/ /g, "_")});
    }
    _updateBuilding(evt) {
        this.setState({building: evt.target.value.replace(/ /g, "_")});
    }
    _updateUnit(evt) {
        this.setState({unit: evt.target.value.replace(/ /g, "_")});
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

        settings.config.driver_config = this.state.driver_config;
        settings.config.registry_config = "config://" + this.props.registryFile;
        
        devicesActionCreators.saveConfig(this.props.device, settings);

        modalActionCreators.closeModal();
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
                }

                editableAttributes.push(setting);
            }
        }

        var configDeviceBox = {
            padding: "0px 50px",
            marginTop: "20px",
            marginBottom: "20px"
        }

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
                                        />
                                    </td>
                                </tr>
                                <tr key="unit">
                                    <td style={firstStyle}>
                                        <span className="required-field">*</span>
                                        Unit</
                                    td>
                                    <td style={secondStyle}
                                        className="plain">
                                        <input
                                            className="form__control form__control--block"
                                            type="text"
                                            onChange={this._updateUnit}
                                            value={this.state.unit}
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
                                        />
                                    </td>
                                </tr>
                                { editableAttributes }
                            </tbody>
                        </table>
                    </div>
                </div>
                <div className="form__actions">
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
            </form>
        );
    }
};

var initializeDriverConfig = (device) => {
    var driver_config = {
        device_address: device.address,
        device_id: device.id,
        proxy_address: device.bacnetProxy
    };

    return driver_config;
}

var initializeSettings = (type, settingsTemplate) => {

    var settings = {};

    switch (type)
    {
        case "bacnet":

            if (settingsTemplate)
            {
                settings = settingsTemplate.config;
            }
            else
            {
                settings = {
                    driver_type: {
                        value: "bacnet", 
                        label: "Driver Type",
                        type: "text"
                    },
                    interval: {
                        value: "", 
                        label: "Interval",
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
                    max_objs_per_read: {
                        value: "", 
                        label: "Maximum Objects per Read",
                        type: "number"
                    },
                    publish_depth_first: {
                        value: false,
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
            }

            break;
    }

    return settings;
}

export default ConfigDeviceForm;
