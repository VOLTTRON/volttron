'use strict';

import React from 'react';
import BaseComponent from './base-component';
import ConfigureRegistry from './configure-registry';

var devicesStore = require('../stores/devices-store');

class ReconfigureRegistry extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange', '_validateDataFile');

        this.state = getInitialState();
    }
    componentDidMount() {
        devicesStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount() {
        devicesStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {

        if (devicesStore.getNewScan())
        {
            this.setState(getInitialState());
        }
        else 
        {
            this.setState({devices: devicesStore.getDevices(this.state.platform, this.state.selectedProxyIdentity)});

            if (devicesStore.getScanningComplete() && this.state.scanning)
            {
                this._cancelScan();
            }
        }
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
        
        var configureRegistry = (
            <ConfigureRegistry device={device} 
                dataValidator={this._validateDataFile}/>
        );

        return (  
            <div className="view">   
                <h2>Reconfigure Device: Registry Config File</h2>      
                {configureRegistry} 

            </div>         
        );
    }
};


function getInitialState() {

    var state = devicesStore.getState();

    if (state.platform)
    {
        state.bacnetProxies = platformsStore.getRunningBacnetProxies(state.platform.uuid);
        state.deviceMethod = (state.bacnetProxies.length ? "scanForDevices" : "addDevicesManually");

        state.deviceStart = "";
        state.deviceEnd = "";
        state.address = "";
        state.scan_length = "";
        state.showAdvanced = false;

        state.startedInputtingDeviceEnd = false;

        state.newScan = true;
        state.devices = [];
        
        if (state.deviceMethod === "scanForDevices")
        {
            state.selectedProxyIdentity = state.bacnetProxies[0].identity;
        }

        state.scanning = false;
        state.canceled = false;
        state.devicesLoaded = false;
        state.scanStarted = false;
        state.cancelButton = false;

        state.showTooltip = false;
        state.tooltipX = 0;
        state.tooltooltipY = 0;
    }

    return state;
}

function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

export default ReconfigureRegistry;