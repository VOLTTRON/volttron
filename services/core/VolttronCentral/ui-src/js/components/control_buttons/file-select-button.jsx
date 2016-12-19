'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';
import {CsvParse} from '../../lib/csvparse';

var RegistryFilesSelector = require('../registry-files-selector');

var devicesActionCreators = require('../../action-creators/devices-action-creators');
var modalActionCreators = require('../../action-creators/modal-action-creators');

class FileSelectButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_loadSavedRegistryFiles');

        this.state = {
            triggerTooltip: false
        };
    }
    _loadSavedRegistryFiles()
    {
        devicesActionCreators.loadRegistryFiles(
            this.props.platformUuid,
            this.props.agentDriver,
            this.props.deviceId,
            this.props.deviceAddress
        );

        modalActionCreators.openModal(
            <RegistryFilesSelector
                platformUuid={this.props.platformUuid}
                agentDriver={this.props.agentDriver}
                deviceId={this.props.deviceId}
                deviceAddress={this.props.deviceAddress}>
            </RegistryFilesSelector>
        );
    }
    render() {

        var fileSelectTooltip = {
            content: <span>Select&nbsp;Registry File&nbsp;(CSV)</span>,
            tooltipClass: "colorBlack",
            "x": this.props.tooltipX,
            "y": this.props.tooltipY
        }

        return (
            <div className="fileSelectButton">
                <ControlButton
                    name={"file-select-" + this.props.deviceId + "-" + this.props.deviceAddress}
                    tooltip={fileSelectTooltip}
                    controlclass="file-select-button"
                    fontAwesomeIcon="file"
                    clickAction={this._loadSavedRegistryFiles}/>
            </div>
        );
    }
};

export default FileSelectButton;