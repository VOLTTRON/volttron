'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';
import {CsvParse} from '../../lib/csvparse';

var statusIndicatorActionCreators = require('../../action-creators/status-indicator-action-creators');
var devicesActionCreators = require('../../action-creators/devices-action-creators');

class FileUploadButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_showFileButtonTooltip", "_uploadRegistryFile", "_validateDataFile",
            "_onFocus");

        this.state = {
            triggerTooltip: false
        };
    }
    _showFileButtonTooltip(showTooltip) {
        this.setState({ triggerTooltip: showTooltip });
    }
    _onFocus() {
        if (typeof this.props.onfocus === "function")
        {
            this.props.onfocus(this.props.deviceId, this.props.deviceAddress);
        }
    }
    _uploadRegistryFile(evt) {
        
        var csvFile = evt.target.files[0];

        evt.target.blur();

        if (!csvFile)
        {
            return;
        }

        if (typeof this.props.onupload === "function")
        {
            this.props.onupload(this.props.deviceId, this.props.deviceAddress);
        }

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
                    
                    devicesActionCreators.loadRegistry(
                        this.props.deviceId, 
                        this.props.deviceAddress, 
                        results.data, 
                        fileName);                        
                }
            }

        }.bind(this)

        reader.readAsText(csvFile); 
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

        var fileUploadTooltip = {
            content: <span>Import&nbsp;Registry File&nbsp;(CSV)</span>,
            tooltipClass: "fileUploadTooltip",
            "x": this.props.tooltipX,
            "y": this.props.tooltipY
        }

        return (
            <div className="fileButton">
                <ControlButton
                    name={"file-upload-" + this.props.deviceId + "-" + this.props.deviceAddress}
                    tooltip={fileUploadTooltip}
                    controlclass="file-button"
                    fontAwesomeIcon="upload"
                    triggerTooltip={this.state.triggerTooltip}/>
                <input 
                    className="uploadButton" 
                    type="file"
                    onChange={this._uploadRegistryFile.bind(this)}
                    onFocus={this._onFocus}
                    onMouseEnter={this._showFileButtonTooltip.bind(this, true)}
                    onMouseLeave={this._showFileButtonTooltip.bind(this, false)}/>
            </div>
        );
    }
};

export default FileUploadButton;