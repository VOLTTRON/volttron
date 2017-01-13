'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';
import {CsvParse} from '../../lib/csvparse';

var RegistryFilesSelector = require('../registry-files-selector');
var devicesActionCreators = require('../../action-creators/devices-action-creators');
var modalActionCreators = require('../../action-creators/modal-action-creators');
var devicesStore = require('../../stores/devices-store');


class FileExportButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_exportFile');

        this.state = {
            triggerTooltip: false
        };
    }
    _exportFile()
    {
        var fileContents = devicesStore.getRegistryValues(
                                this.props.deviceId, 
                                this.props.deviceAddress
                            );

        var csvData = "data:text/csv;charset=utf-8,";

        var headerRow = [];

        fileContents[0].forEach(function (item) {
            headerRow.push(item.label);
        });

        csvData = csvData.concat(headerRow.join() + "\n");

        fileContents.forEach(function (attributeRow, rowIndex) {

            var newRow = [];

            attributeRow.forEach(function (columnCell, columnIndex) {

                var altValue = columnCell.value;

                var index = altValue.indexOf(",");

                if (index > -1)
                {
                    altValue = "\"" + altValue + "\"";
                }

                newRow.push(altValue);
            });

            csvData = csvData.concat(newRow.join() + "\n");
        });

        var encodedUri = encodeURI(csvData);
        var link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", this.props.fileName);
        document.body.appendChild(link); // Required for FF

        link.click();

    }
    render() {

        var fileExportTooltip = {
            content: "Export " + this.props.fileName,
            tooltipClass: "fileExportTooltip",
            "x": this.props.tooltipX,
            "y": this.props.tooltipY,
            "nobr": true
        };

        var exportIcon = <span>&#x27A0;</span>;

        return (
            <div className="fileExportButton">
                <ControlButton
                    name={"file-export-" + this.props.deviceId + "-" + this.props.deviceAddress}
                    tooltip={fileExportTooltip}
                    controlclass="file-export-button"
                    icon={exportIcon}
                    clickAction={this._exportFile}/>
            </div>
        );
    }
};

export default FileExportButton;