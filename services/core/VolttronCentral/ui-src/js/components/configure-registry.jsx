'use strict';

import React from 'react';
import BaseComponent from './base-component';
import EditPointForm from './edit-point-form';
import PreviewRegistryForm from './preview-registry-form';
import NewColumnForm from './new-column-form';
import ConfigDeviceForm from './config-device-form';
import EditSelectButton from './control_buttons/edit-select-button';
import EditColumnButton from './control_buttons/edit-columns-button';
import RegistryRow from './registry-row';
import Immutable from 'immutable';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var FilterPointsButton = require('./control_buttons/filter-points-button');
var ControlButton = require('./control-button');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');


var registryWs, registryWebsocket;
class ConfigureRegistry extends BaseComponent {    
    constructor(props) {
        super(props);
        this._bind("_onFilterBoxChange", "_onClearFilter", "_onAddPoint", "_onRemovePoints", "_removePoints", 
            "_selectAll", "_onAddColumn", "_onCloneColumn", "_onRemoveColumn", "_removeColumn",
            "_onFindNext", "_onReplace", "_onReplaceAll", "_onClearFind", "_cancelRegistry",
            "_saveRegistry", "_removeFocus", "_resetState", "_addColumn", "_selectCells", 
            "_cloneColumn", "_onStoresChange", "_fetchExtendedPoints", "_onRegistrySave", "_focusOnDevice",
            "_handleKeyDown" );

        this.state = this._resetState(this.props.device);

        this.state.keyboardRange = [-1, -1];
    }
    componentDidMount() {
        this.containerDiv = document.getElementsByClassName("fixed-table-container")[0];
        this.fixedHeader = document.getElementsByClassName("header-background")[0];
        this.fixedInner = document.getElementsByClassName("fixed-table-container-inner")[0];
        this.registryTable = document.getElementsByClassName("registryConfigTable")[0];

        devicesStore.addChangeListener(this._onStoresChange);
        document.addEventListener("keydown", this._handleKeyDown);
    }
    componentWillUnmount() {
        devicesStore.removeChangeListener(this._onStoresChange);
        document.removeEventListener("keydown", this._handleKeyDown);
    }
    componentDidUpdate() {

        if (this.scrollToBottom)
        {
            this.containerDiv.scrollTop = this.containerDiv.scrollHeight;

            this.scrollToBottom = false;
        }

        if (this.resizeTable)
        {
            this.fixedHeader.style.width = this.registryTable.clientWidth + "px";
            this.fixedInner.style.width = this.registryTable.clientWidth + "px";

            this.resizeTable = false;
        }

        if (this.state.selectedCellRow !== null)
        {
            var focusedCell = document.getElementsByClassName("focusedCell")[0];
            if (focusedCell)
            {
                focusedCell.focus();
            }
        }
    }
    componentWillReceiveProps(nextProps) {
        if (this.props.device !== nextProps.device)
        {
            var newState = this._resetState(nextProps.device);
            newState.keyboardRange = this.state.keyboardRange;

            this.setState(newState);
        }
    }
    _handleKeyDown (keydown) {

        console.log("Handling keydown");
        if (keydown.target.nodeName !== "INPUT" && this.state.deviceHasFocus)
        { 
            if (this.state.keyboardStarted)
            {
                switch (keydown.which)
                {
                    case 27: // ESC
                        this.setState({ keyboardRange: [-1, -1]});
                        this.setState({ keyboardStarted: false });

                        break;
                    case 13: // Enter

                        this._fetchExtendedPoints(this.state.keyboardRange);

                        break;
                    // case 9:    //Tab
                    case 32:    //Space
                    case 40:    //Down
                        keydown.preventDefault();

                        if (keydown.shiftKey) // extend down
                        {
                            var newIndex = this.state.keyboardRange[1] + 1;

                            if (newIndex < this.state.registryValues.length)
                            {
                                // this.setState({ keyboardIndex: newIndex });

                                if (newIndex > this.state.keyboardRange[1])
                                {
                                    this.state.keyboardRange[1] = newIndex;

                                    this.setState({ keyboardRange: this.state.keyboardRange});    
                                }
                            }
                        }
                        else // simple down
                        {
                            var newIndex = this.state.keyboardRange[1] + 1;

                            if (newIndex < this.state.registryValues.length)
                            {
                                // this.setState({ keyboardIndex: newIndex });
                                this.setState({ keyboardRange: [newIndex, newIndex]});
                            }
                        }

                        break;
                    case 38:    //Up
                        keydown.preventDefault();

                        if (keydown.shiftKey) // extend up
                        {
                            var newIndex = this.state.keyboardRange[0] - 1;

                            if (newIndex > -1)
                            {
                                // this.setState({ keyboardIndex: newIndex });

                                if (newIndex < this.state.keyboardRange[0])
                                {
                                    this.state.keyboardRange[0] = newIndex;

                                    this.setState({ keyboardRange: this.state.keyboardRange});    
                                }
                            }

                        }
                        else // simple up
                        {
                            var newIndex = this.state.keyboardRange[0] - 1;

                            if (newIndex > -1)
                            {
                                // this.setState({ keyboardIndex: newIndex });
                                this.setState({ keyboardRange: [newIndex, newIndex]});
                            }
                        }

                        break;
                    case 46:    //Delete
                        _keyboard.cmd = "delete";

                        break;
                }
            }
            else if (keydown.which === 17)
            {
                this.setState({ keyboardRange: [0, 0]});
                this.setState({ keyboardStarted: true });
            }      
        }
        else
        {
            this.setState({ keyboardRange: [-1, -1] });
        }
    }
    _resetState(device){
    
        var state = {};    

        state.keyPropsList = device.keyProps;
        state.filterColumn = state.keyPropsList[0];

        state.registryValues = getPointsFromStore(device, state.keyPropsList);

        state.columnNames = [];
        // state.pointNames = [];
        state.filteredList = [];

        state.deviceHasFocus = true;

        state.selectedPoints = devicesStore.getSelectedPoints(device);

        if (state.registryValues.length > 0)
        {
            state.columnNames = state.registryValues[0].get("attributes").map(function (columns) {
                return columns.key;
            });
        }

        state.pointsToDelete = [];
        state.allSelected = false;

        state.selectedCells = [];
        state.selectedCellRow = null;
        state.selectedCellColumn = null;
        state.filterOn = false;

        this.scrollToBottom = false;
        this.resizeTable = false;

        // this.keyboardIndex = -1;

        return state;
    }
    _onStoresChange () {

        var deviceHasFocus = devicesStore.deviceHasFocus(this.props.device.id);

        if (deviceHasFocus !== this.state.deviceHasFocus)
        {
            this.setState({ deviceHasFocus: deviceHasFocus });
        }
    }
    _fetchExtendedPoints(keyboardRange) {

        var configRequests = {};

        var registryValues = this.state.registryValues.map(function (attributesList) {

            if (!attributesList.get("selected"))
            {
                if (attributesList.get("virtualIndex") >= this.state.keyboardRange[0] && attributesList.get("virtualIndex") <= this.state.keyboardRange[1])
                {
                    if (!configRequests.hasOwnProperty(attributesList.get("bacnetObjectType")))
                    {
                        configRequests[attributesList.get("bacnetObjectType")] = [];
                    }

                    configRequests[attributesList.get("bacnetObjectType")].push(attributesList.get("index"));

                    attributesList = attributesList.set("selected", true);
                }
            }

            return attributesList;

        }, this);

        this.setState({ registryValues: registryValues });

        // _setUpRegistrySocket();

        //TODO: hook up onmessage in configure-registry.jsx or in registry-row.jsw
        // registryWs.send(JSON.stringify(configRequests));
    }    
    _setUpRegistrySocket() {

        if (typeof registryWebsocket === "undefined" || registryWebsocket === null)
        {
            registryWebsocket = "ws://" + window.location.host + "/vc/ws/configure";
            if (window.WebSocket) {
                registryWs = new WebSocket(devicesWebsocket);
            }
            else if (window.MozWebSocket) {
                registryWs = MozWebSocket(devicesWebsocket);
            }

            registryWS.onmessage = function(evt)
            {
                // devicesActionCreators.pointDataReceived(evt.data, this.props.device);

                // var warnings = devicesStore.getWarnings();

                // if (!objectIsEmpty(warnings))
                // {
                //     for (var key in warnings)
                //     {
                //         var values = warnings[key].items.join(", ");

                //         statusIndicatorActionCreators.openStatusIndicator(
                //             "error", 
                //             warnings[key].message + "ID: " + values, 
                //             values, 
                //             "left"
                //         );
                //     }
                // }

            }.bind(this);
        }
    }   
    _focusOnDevice() {
        devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);
        console.log("focused on device");
    } 
    _onFilterBoxChange(filterValue, column) {
        this.setState({ filterOn: true });

        this.setState({ 
            registryValues: getFilteredPoints(
                this.state.registryValues, 
                filterValue,
                column
            ) 
        });
    }
    _onClearFilter() {
        this.setState({ filterOn: false });
    }
    _onAddPoint() {

        var pointValues = [];

        this.state.registryValues[0].get("attributes").forEach(function (attribute) {
            pointValues.push({ 
                "key" : attribute.key, 
                "label": attribute.label,
                "value": "", 
                "editable": true, 
                "keyProp": attribute.keyProp 
            });
        }, this);

        modalActionCreators.openModal(
            <EditPointForm 
                device={this.props.device} 
                selectedPoints={this.state.selectedPoints}
                attributes={pointValues}>
            </EditPointForm>);
        
    }
    // _addPoint(pointValues) {
        
    //     this.state.registryValues.push({visible: true, attributes: pointValues});

    //     this.setState({ registryValues: this.state.registryValues });

    //     this.scrollToBottom = true;
    // }
    _onRemovePoints() {

        var promptText, confirmText, confirmAction, cancelText;

        if (this.state.pointsToDelete.length > 0)
        {
            promptText = "Are you sure you want to delete these points? " + this.state.pointsToDelete.join(", ");
            confirmText = "Delete";
            confirmAction = this._removePoints.bind(this, this.state.pointsToDelete);
        }  
        else
        {
            promptText = "Select points to delete.";
            cancelText = "OK";
        }
        
        modalActionCreators.openModal(
            <ConfirmForm
                promptTitle="Remove Points"
                promptText={ promptText }
                confirmText={ confirmText }
                onConfirm={ confirmAction }
                cancelText={ cancelText }
            ></ConfirmForm>
        );
    }
    _removePoints(pointsToDelete) {
        
        pointsToDelete.forEach(function (pointToDelete) {

            var index = -1;
            var pointValue = "";

            this.state.registryValues.some(function (row, i) {
                var pointMatched = (row.attributes[0].value === pointToDelete);

                if (pointMatched)
                {
                    index = i;
                    pointValue = row.attributes[0].value;
                }

                return pointMatched;
            })

            if (index > -1)
            {
                this.state.registryValues.splice(index, 1);
                
                index = this.state.pointsToDelete.indexOf(pointValue);

                if (index > -1)
                {
                    this.state.pointsToDelete.splice(index, 1);
                }

                // index = this.state.pointNames.indexOf(pointValue);

                // if (index > -1)
                // {
                //     this.state.pointNames.splice(index, 1);
                // }
            }
        }, this);

        this.setState({ registryValues: this.state.registryValues });
        this.setState({ pointsToDelete: this.state.pointsToDelete });
        // this.setState({ pointNames: this.state.pointNames });

        modalActionCreators.closeModal();
    }
    // _selectForDelete(attributesList) {
        
    //     var pointsToDelete = this.state.pointsToDelete;

    //     var index = pointsToDelete.indexOf(attributesList[0].value);

    //     if (index < 0)
    //     {
    //         pointsToDelete.push(attributesList[0].value);
    //     }
    //     else
    //     {
    //         pointsToDelete.splice(index, 1);
    //     }

    //     this.setState({ pointsToDelete: pointsToDelete });

    // }
    _selectAll() {
        var allSelected = !this.state.allSelected;

        this.setState({ allSelected: allSelected });

        this.setState({ pointsToDelete : (allSelected ? JSON.parse(JSON.stringify(this.state.pointNames)) : []) }); 
    }
    _onAddColumn(index) {

        var newColumnLabel = this.state.registryValues[0].attributes[index].label + "_";

        modalActionCreators.openModal(
            <NewColumnForm
                columnNames={this.state.columnNames}
                column={index}
                onConfirm={this._addColumn}
            ></NewColumnForm>
        );
    }
    _addColumn(newColumnLabel, index) {

        var newColumn = newColumnLabel.toLowerCase().replace(/ /g, "_");
        this.state.columnNames.splice(index + 1, 0, newColumn);
        this.state.keyPropsList.push(newColumn);

        this.setState({ columnNames: this.state.columnNames });
        this.setState({ keyPropsList: this.state.keyPropsList });

        var newRegistryValues = this.state.registryValues.map(function (row) {

            row.attributes.splice(index + 1, 0, { 
                                            "key": newColumn,
                                            "label": newColumnLabel,
                                            "value": "", 
                                            "editable": true, 
                                            "keyProp": true 
                                        });
            return row;
        });

        this.resizeTable = true;

        this.setState({ registryValues: newRegistryValues });        
    }
    _onCloneColumn(index) {

        modalActionCreators.openModal(
            <NewColumnForm
                columnNames={this.state.columnNames}
                column={index}
                onConfirm={this._cloneColumn}
            ></NewColumnForm>
        );
    }
    _cloneColumn(newColumnLabel, index) {

        var newColumn = newColumnLabel.toLowerCase().replace(/ /g, "_");
        this.state.columnNames.splice(index + 1, 0, newColumn);
        this.state.keyPropsList.push(newColumn);

        this.setState({ columnNames: this.state.columnNames });
        this.setState({ keyPropsList: this.state.keyPropsList });

        var newRegistryValues = this.state.registryValues.map(function (row) {

            var clonedValue = {};

            for (var key in row.attributes[index])
            {
                clonedValue[key] = row.attributes[index][key];
            }

            clonedValue.label = newColumnLabel;
            clonedValue.key = newColumn;

            row.attributes.splice(index + 1, 0, clonedValue);

            return row;
        });

        this.resizeTable = true;

        this.setState({ registryValues: newRegistryValues });
    }
    _onRemoveColumn(index) {

        var columnHeader = this.state.registryValues[0].attributes[index].label;
        var promptText = ("Are you sure you want to delete the column, " + columnHeader + "?");
        
        modalActionCreators.openModal(
            <ConfirmForm
                promptTitle="Remove Column"
                promptText={ promptText }
                confirmText="Delete"
                onConfirm={this._removeColumn.bind(this, index)}
            ></ConfirmForm>
        );
        
    }
    _removeColumn(index) {

        var registryValues = JSON.parse(JSON.stringify(this.state.registryValues));
        var columnNames = JSON.parse(JSON.stringify(this.state.columnNames));
        var keyPropsList = JSON.parse(JSON.stringify(this.state.keyPropsList));

        var columnName = columnNames[index];

        columnNames.splice(index, 1);

        registryValues.forEach(function (row) {
            row.attributes.splice(index, 1);
        });

        index = keyPropsList.indexOf(columnName);

        if (index > -1)
        {
            keyPropsList.splice(index, 1);
        }

        this.setState({ keyPropsList: keyPropsList });
        this.setState({ columnNames: columnNames });
        this.setState({ registryValues: registryValues });

        this.resizeTable = true;

        modalActionCreators.closeModal();

    }
    _removeFocus() {
        this.setState({ selectedCellRow: null});
    }
    _selectCells(findValue, column) {
        var selectedCells = [];

        this.setState({ registryValues: this.state.registryValues.map(function (row, index) {

                //searching i-th column in each row, and if the cell contains the target value, select it
                row.attributes[column].selected = (row.attributes[column].value.indexOf(findValue) > -1);

                if (row.attributes[column].selected)
                {
                    selectedCells.push(index);
                }

                return row;
            })
        });

        this.setState({ selectedCells: selectedCells });

        if (selectedCells.length > 0)
        {
            // this.setState({ selectedCells: selectedCells });
            this.setState({ selectedCellColumn: column });

            //set focus to the first selected cell
            this.setState({ selectedCellRow: selectedCells[0]});
        }

        return selectedCells;
    }
    _onFindNext(findValue, column) {

        // var registryValues = this.state.registryValues.slice();
        
        if (this.state.selectedCells.length === 0)
        {
            this._selectCells(findValue, column);
        }
        else
        {
            //we've already found the selected cells, so we need to advance focus to the next one
            if (this.state.selectedCells.length > 1)
            {
                var selectedCellRow = this._goToNext(this.state.selectedCellRow, this.state.selectedCells);

                this.setState({ selectedCellRow: selectedCellRow});
            }
        }
    }
    _onReplace(findValue, replaceValue, column) {

        if (!this.state.selectedCellRow)
        {
            this._onFindNext(findValue, column);
        }
        else
        {
            // var registryValues = this.state.registryValues.slice();
            this.state.registryValues[this.state.selectedCellRow].attributes[column].value = this.state.registryValues[this.state.selectedCellRow].attributes[column].value.replace(findValue, replaceValue);        

            //If the cell no longer has the target value, deselect it and move focus to the next selected cell
            if (this.state.registryValues[this.state.selectedCellRow].attributes[column].value.indexOf(findValue) < 0)
            {
                this.state.registryValues[this.state.selectedCellRow].attributes[column].selected = false;

                //see if there will even be another selected cell to move to
                var selectedCells = this.state.selectedCells.slice();
                var index = selectedCells.indexOf(this.state.selectedCellRow);

                if (index > -1)
                {
                    selectedCells.splice(index, 1);
                }

                if (selectedCells.length > 0)
                {
                    var selectedCellRow = this._goToNext(this.state.selectedCellRow, this.state.selectedCells);
                
                    this.setState({ selectedCellRow: selectedCellRow});
                    this.setState({ selectedCells: selectedCells });
                }
                else
                {
                    //there were no more selected cells, so clear everything out
                    this.setState({ selectedCells: [] });
                    this.setState({ selectedCellRow: null });
                    this.setState({ selectedCellColumn: null });
                }
            }

            this.setState({ registryValues: this.state.registryValues});
        }
    }
    _onReplaceAll(findValue, replaceValue, column) {
        
        // var selectedCellRow = this.state.selectedCells[0];

        var selectedCellsToKeep = [];

        this.state.selectedCells.forEach((selectedCell) => {
            var newValue = this.state.registryValues[selectedCell].attributes[column].value.replace(findValue, replaceValue);
            this.state.registryValues[selectedCell].attributes[column].value = newValue;  

            if (this.state.registryValues[selectedCell].attributes[column].value.indexOf(findValue) < 0)
            {
                this.state.registryValues[selectedCell].attributes[column].selected = false; 

                selectedCellsToKeep.push(selectedCell);
            }
        });

        this.setState({ selectedCellRow: null});
        this.setState({ selectedCells: selectedCellsToKeep });
        this.setState({ selectedCellColumn: null });
        this.setState({ registryValues: this.state.registryValues});
    }
    _onClearFind(column) {

        // var registryValues = this.state.registryValues.slice();

        this.state.selectedCells.forEach((row) => {
            this.state.registryValues[row].attributes[column].selected = false;
        }, this);

        this.setState({ registryValues: this.state.registryValues });
        this.setState({ selectedCells: [] });
        this.setState({ selectedCellRow: null });
        this.setState({ selectedCellColumn: null });

    }
    _goToNext(selectedCellRow, selectedCells) {

        //this is the row with current focus
        var rowIndex = selectedCells.indexOf(selectedCellRow);

        if (rowIndex > -1)
        {
            //either set focus to the next one in the selected cells list
            if (rowIndex < selectedCells.length - 1)
            {
                selectedCellRow = selectedCells[++rowIndex];
            }
            else //or if we're at the end of the list, go back to the first one
            {
                selectedCellRow = selectedCells[0];
            }
        }

        return selectedCellRow;
    }
    _cancelRegistry() {
        devicesActionCreators.cancelRegistry(this.props.device);
    }
    _onRegistrySave() {
        modalActionCreators.openModal(
            <PreviewRegistryForm 
                device={this.props.device} 
                attributes={this.state.registryValues.map(function (row) {
                    return row.attributes;
                })}
                onsaveregistry={this._saveRegistry}>
            </PreviewRegistryForm>);
    }
    _saveRegistry() {

        devicesActionCreators.saveRegistry(this.props.device, this.state.registryValues.map(function (row) {
            return row.attributes;
        }));
        modalActionCreators.openModal(<ConfigDeviceForm device={this.props.device}/>);
    }
    render() {        
        
        var registryRows, registryHeader, registryButtons;

        if (this.state.registryValues.length)
        {            
            registryRows = this.state.registryValues.map(function (attributesList, rowIndex) {

                var virtualRow = attributesList.get("virtualIndex");

                var keyboardSelected;

                if (this.state.keyboardRange[0] !== -1 && this.state.keyboardRange[1] !== -1)
                {
                    keyboardSelected = (virtualRow >= this.state.keyboardRange[0] && virtualRow <= this.state.keyboardRange[1]);
                }

                var immutableProps = Immutable.fromJS({
                    rowIndex: rowIndex,
                    deviceId: this.props.device.id,
                    deviceAddress: this.props.device.address,
                    deviceName: this.props.device.name,
                    selectedCell: (this.state.selectedCellRow === rowIndex),
                    selectedCellColumn: this.state.selectedCellColumn,
                    filterOn: this.state.filterOn,
                    keyboardSelected: keyboardSelected
                });

                return (<RegistryRow 
                            key={"registryRow-" + attributesList.get("attributes").get(0).value}
                            attributesList={attributesList} 
                            immutableProps={immutableProps}/>);
                
            }, this);

        
            var headerColumns = [];
            var tableIndex = 0;

            this.state.registryValues[0].get("attributes").forEach(function (item, index) {
            
                if (item.keyProp)
                {
                    var editSelectButton = (<EditSelectButton 
                                                onremove={this._onRemoveColumn}
                                                onadd={this._onAddColumn}
                                                onclone={this._onCloneColumn}
                                                column={index}
                                                name={this.props.device.id + "-" + item.key}/>);

                    var editColumnButton = (<EditColumnButton 
                                                column={index} 
                                                tooltipMsg="Edit Column"
                                                findnext={this._onFindNext}
                                                replace={this._onReplace}
                                                replaceall={this._onReplaceAll}
                                                replaceEnabled={this.state.selectedCells.length > 0}
                                                // onfilter={this._onFilterBoxChange} 
                                                onclear={this._onClearFind}
                                                onhide={this._removeFocus}
                                                name={this.props.device.id + "-" + item.key}/>);

                    var headerCell;

                    if (tableIndex === 0)
                    {
                        var firstColumnWidth = {
                            width: (item.length * 10) + "px"
                        }

                        var filterPointsTooltip = {
                            content: "Filter Points",
                            "x": 80,
                            "y": -60
                        }

                        var filterButton = <FilterPointsButton 
                                                name={"filterRegistryPoints-" + this.props.device.id}
                                                tooltipMsg={filterPointsTooltip}
                                                onfilter={this._onFilterBoxChange} 
                                                onclear={this._onClearFilter}
                                                column={index}/>

                        var addPointTooltip = {
                            content: "Add New Point",
                            "x": 80,
                            "y": -60
                        }

                        var addPointButton = <ControlButton 
                                                name={"addRegistryPoint-" + this.props.device.id}
                                                tooltip={addPointTooltip}
                                                controlclass="add_point_button"
                                                fontAwesomeIcon="plus"
                                                clickAction={this._onAddPoint}/>


                        var removePointTooltip = {
                            content: "Remove Points",
                            "x": 80,
                            "y": -60
                        }

                        var removePointsButton = <ControlButton
                                                name={"removeRegistryPoints-" + this.props.device.id}
                                                fontAwesomeIcon="minus"
                                                tooltip={removePointTooltip}
                                                controlclass="remove_point_button"
                                                clickAction={this._onRemovePoints}/>

                        if (item.editable)
                        {                        
                            headerCell = ( <th key={"header-" + item.key + "-" + index} style={firstColumnWidth}>
                                                <div className="th-inner zztop">
                                                    { item.label } 
                                                    { filterButton } 
                                                    { addPointButton } 
                                                    { removePointsButton }
                                                    { editSelectButton }
                                                    { editColumnButton }
                                                </div>
                                            </th>);
                        }
                        else
                        {
                            headerCell = ( <th key={"header-" + item.key + "-" + index} style={firstColumnWidth}>
                                                <div className="th-inner zztop">
                                                    { item.label } 
                                                    { filterButton } 
                                                    { addPointButton } 
                                                    { removePointsButton }
                                                </div>
                                            </th>);
                        }
                    }
                    else
                    {
                        if (item.editable)
                        {
                            headerCell = ( <th key={"header-" + item.key + "-" + index}>
                                                <div className="th-inner" >
                                                    { item.label }
                                                    { editSelectButton }
                                                    { editColumnButton }
                                                </div>
                                            </th> );
                        }
                        else
                        {
                            headerCell = ( <th key={"header-" + item.key + "-" + index}>
                                                <div className="th-inner" >
                                                    { item.label }
                                                </div>
                                            </th> );
                        }
                    }

                    ++tableIndex;
                    headerColumns.push(headerCell);
                }
            }, this);  

            var checkboxColumnStyle = {
                width: "24px"
            }

            registryHeader = (
                <tr key="header-values">
                    <th style={checkboxColumnStyle} key="header-checkbox">
                        <div className="th-inner">
                            <input type="checkbox"
                                onChange={this._selectAll}
                                checked={this.state.allSelected}/>
                        </div>
                    </th>
                    { headerColumns }
                </tr>
            );

            var wideDiv = {
                width: "100%",
                textAlign: "center",
                paddingTop: "20px"
            };

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
                    clickAction={this._onRegistrySave}></ControlButton>
            );

            var cancelTooltip = {
                "content": "Cancel Configuration",
                "xOffset": tooltipX,
                "yOffset": tooltipY
            };

            var cancelIcon = <span>&#10008;</span>;
            var cancelButton = (
                <ControlButton 
                    name="cancelConfigButton"
                    tooltip={cancelTooltip}
                    icon={cancelIcon}
                    clickAction={this._cancelRegistry}></ControlButton>
            );
            
            registryButtons = (
                <div className="registry-buttons" style={wideDiv}>
                    <div className="inlineBlock">
                        {cancelButton}
                    </div>
                    <div className="inlineBlock">
                        {saveButton}
                    </div>                    
                </div>
            );     
        };

        var visibilityClass = ( this.props.device.showPoints ? 
                                    "collapsible-registry-values slow-show" : 
                                        "collapsible-registry-values slow-hide" );        
            
        return (
            <div className={visibilityClass}
                tabIndex={1}
                onFocus={this._focusOnDevice}>
                <div className="fixed-table-container"> 
                    <div className="header-background"></div>      
                    <div className="fixed-table-container-inner">    
                        <table className="registryConfigTable">
                            <thead>
                                { registryHeader }                                
                            </thead>
                            <tbody>                            
                                { registryRows }
                            </tbody>
                        </table>
                    </div>
                </div>
                { registryButtons }
            </div>
        );
    }
};

function getFilteredPoints(registryValues, filterStr, column) {

    var virtualCount = 0;

    return registryValues.map(function (row) {

        row.visible = (filterStr === "" || (row.attributes[column].value.trim()
                                                .toUpperCase()
                                                .indexOf(filterStr.trim().toUpperCase()) > -1));

        if (row.visible)
        {
            row.virtualIndex = virtualCount;
            ++virtualCount;
        }
        else
        {
            row.virtualIndex = -2;
        }

        

        return row;
    });
}

function getPointsFromStore(device, keyPropsList) {
    return initializeList(devicesStore.getRegistryValues(device), keyPropsList);
}

function initializeList(registryConfig, keyPropsList)
{
    return registryConfig.map(function (row, rowIndex) {

        var bacnetObjectType, objectIndex;

        row.forEach(function (cell) {
            cell.keyProp = (keyPropsList.indexOf(cell.key) > -1); 
            if (cell.key === "bacnet_object_type")
            {
                bacnetObjectType = cell.value;
            }
            else if (cell.key === "index")
            {
                objectIndex = cell.value;
            }
        });

        return Immutable.fromJS({ 
            visible: true, 
            virtualIndex: rowIndex, 
            bacnetObjectType: bacnetObjectType, 
            index: objectIndex,
            attributes: row,
            selected: false
        });
    });
}


export default ConfigureRegistry;