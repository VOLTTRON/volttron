'use strict';

import React from 'react';
import BaseComponent from './base-component';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

class ConfigDeviceForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_updateSetting", "_onSubmit");

        this.state = getStateFromStores(this.props.device);
    }
    _updateSetting(evt) {
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
    }
    _onCancelClick(e) {
        modalActionCreators.closeModal();
    }
    _onSubmit(e) {
        e.preventDefault();
        devicesActionCreators.saveBacnetConfig(this.props.device, this.state.settings, this.props.registryFile);
        modalActionCreators.closeModal();
    }
    render() {       

        var tableStyle = {
            backgroundColor: "#E7E7E7"
        }

        var uneditableAttributes = 
            <table style={tableStyle}>
                <tbody>

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

        var firstStyle = {
            width: "30%",
            textAlign: "right"
        }

        var secondStyle = {
            width: "50%"
        }

        var settingsRows = 
            this.state.settings.map(function (setting) {

                var stateSetting = this.state.settings.find(function (s) {
                    return s.key === setting.key;
                })

                return (
                    <tr key={setting.key}>
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

        var editableAttributes = 
            <table>
                <tbody>
                    { settingsRows }
                </tbody>
            </table>

        var configDeviceBox = {
            padding: "0px 50px",
            marginTop: "20px",
            marginBottom: "20px"
        }

        return (
            <form className="config-device-form" onSubmit={this._onSubmit}>
                <div className="centerContent"><h3>Device Configuration</h3></div>
                <div className="configDeviceContainer">
                    <div className="uneditableAttributes">
                        { uneditableAttributes }
                    </div>
                    <div style={configDeviceBox}>                    
                        { editableAttributes }
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
                    <button className="button">
                        Save
                    </button>
                </div>
            </form>
        );
    }
};

var getStateFromStores = (device) => {

    return {
        settings: [
            { key: "campus", value: "", label: "Campus" },
            { key: "building", value: "", label: "Building" },
            { key: "unit", value: "", label: "Unit" },
            { key: "path", value: "", label: "Path" },
            { key: "interval", value: "", label: "Interval" },
            { key: "timezone", value: "", label: "Timezone" },
            { key: "heartbeat_point", value: "", label: "Heartbeat Point" },
            { key: "minimum_priority", value: "", label: "Minimum Priority" },
            { key: "max_objs_per_read", value: "", label: "Maximum Objects per Read" }
        ]
    };
}

export default ConfigDeviceForm;
