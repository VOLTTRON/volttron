'use strict';

import React from 'react';
import BaseComponent from './base-component';
import PreviewRegistryTable from './preview-registry-table';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var ConfirmForm = require('./confirm-form');

class PreviewRegistryForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_toggleLayout", "_updateFileName", "_onSubmit", "_saveRegistryFile");

        this.state = {
            csvlayout: false,
            fileName: (this.props.fileName ? this.props.fileName : ""),
            reconfiguring: (this.props.fileName ? true : false)
        }

        if (this.state.reconfiguring)
        {
            this.state.deviceInfo = this.props.deviceName;
        }
        else
        {
            this.state.deviceInfo = this.props.deviceName + " / " + this.props.deviceAddress + " / " + this.props.deviceId;
        }

        this.state.otherFileNames = getOtherRegistryFileNames();
    }
    _toggleLayout(itemKey) {

        this.setState({ csvlayout: !this.state.csvlayout });
    }
    _updateFileName(e) {

        this.setState({ fileName: e.target.value });
    }
    _onCancelClick(e) {
        modalActionCreators.closeModal();
    }
    _onSubmit(e) {
        e.preventDefault();

        if (this.state.reconfiguring)
        {
            if (this.state.otherFileNames.indexOf(this.state.fileName) > -1)
            {   
                modalActionCreators.openModal(
                    <ConfirmForm
                        promptTitle="Existing File Name"
                        promptText={"This registry file uses a pre-existing file name, \"" 
                            + this.state.fileName + "\". Saving changes to the registry using " + 
                            " this file name could affect other devices if they are configured with " +
                            " this registry file. You can proceed with the save, or cancel " +
                            " and choose a different file name. Proceed with save?"} 
                        confirmText="Save"
                        onConfirm={ this._saveRegistryFile }
                        cancelText="Cancel"
                        width="400px"
                    ></ConfirmForm> 
                );
            }
            else
            {
                this._saveRegistryFile();
            }
        }
        else
        {
            if (this.state.otherFileNames.indexOf(this.state.fileName) > -1)
            {   
                modalActionCreators.closeModal();

                modalActionCreators.openModal(
                    <ConfirmForm
                        promptTitle="Duplicate File Names"
                        promptText={"Another registry file exists with the name \"" + 
                            this.state.fileName + "\". Using this name will overwrite " + 
                            "the other file and risk disrupting previously configured devices. " +
                            "Proceed with save?"} 
                        confirmText="Save"
                        onConfirm={ this._saveRegistryFile }
                        cancelText="Cancel"
                        width="400px"
                    ></ConfirmForm> 
                );
            }
            else
            {
                this._saveRegistryFile();
            }
        }
    }
    _saveRegistryFile() {
        this.props.onsaveregistry(this.state.fileName);
    }
    render() {

        var layoutToggle;

        if (this.state.csvlayout)
        {
            layoutToggle = (

                        <div className="displayBlock">
                            <div className="form__link inlineBlock"
                                onClick={this._toggleLayout}>
                                <a>table</a>
                            </div>
                            &nbsp;/&nbsp;
                            <div className="inlineBlock">csv</div>
                        </div>);
        }
        else
        {
            layoutToggle = (
                <div className="displayBlock">
                    <div className="inlineBlock">table</div>
                    &nbsp;/&nbsp;
                    <div className="form__link inlineBlock"
                        onClick={this._toggleLayout}>
                        <a>csv</a>
                    </div>
                </div>
            );
        }

        return (
            <form className="preview-registry-form" onSubmit={this._onSubmit}>
                <h1>Save this registry configuration?</h1>
                <h4>{this.state.deviceInfo}</h4>
                { layoutToggle }
                <br/>
                <div className="displayBlock floatLeft">
                    <div className="inlineBlock">CSV File Name: </div>
                    &nbsp;
                    <div className="inlineBlock">
                        <input 
                            onChange={this._updateFileName}
                            value={this.state.fileName}
                            type="text">
                        </input>
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
                    <button 
                        className="button"
                        disabled={this.state.fileName === ""}>
                        Save
                    </button>
                </div>
                <PreviewRegistryTable 
                    csvlayout={this.state.csvlayout} 
                    attributes={this.props.attributes}
                    deviceId={this.props.deviceId}/>
            </form>
        );
    }
};

function getOtherRegistryFileNames() {
    var registryFiles = devicesStore.getSavedRegistryFiles();

    return (registryFiles ? registryFiles.files : []);
}

export default PreviewRegistryForm;
