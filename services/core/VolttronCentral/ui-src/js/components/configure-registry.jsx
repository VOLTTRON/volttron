'use strict';

import React from 'react';
import ReactDOM from 'react-dom';
import BaseComponent from './base-component';
import EditPointForm from './edit-point-form';
import PreviewRegistryForm from './preview-registry-form';
import NewColumnForm from './new-column-form';
import ConfigDeviceForm from './config-device-form';
import EditSelectButton from './control_buttons/edit-select-button';
import EditColumnButton from './control_buttons/edit-columns-button';
import KeyboardHelpButton from './control_buttons/keyboard-help-button';
import RegistryRow from './registry-row';
import ControlButton from './control-button';
import CheckBox from './check-box';
import Immutable from 'immutable';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var FilterPointsButton = require('./control_buttons/filter-points-button');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');


var _defaultColumnWidth = "200px";
var _tableWidth;

class ConfigureRegistry extends BaseComponent {    
    constructor(props) {
        super(props);
        this._bind("_onFilterBoxChange", "_onClearFilter", "_onAddPoint", "_onRemovePoints", "_removePoints", 
            "_selectAll", "_onAddColumn", "_onCloneColumn", "_onRemoveColumn", "_removeColumn",
            "_onFindNext", "_onReplace", "_onReplaceAll", "_onClearFind", "_cancelRegistry",
            "_saveRegistry", "_removeFocus", "_resetState", "_addColumn", "_selectCells", "_getParentNode",
            "_cloneColumn", "_onStoresChange", "_fetchExtendedPoints", "_onRegistrySave", "_focusOnDevice",
            "_handleKeyDown", "_onSelectForDelete", "_resizeColumn", "_initializeTable", "_removeSelectedPoints" );

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

        if ((keydown.target.nodeName !== "INPUT" || 
            keydown.target.className === "uploadButton" ||
            keydown.target.className === "registryCheckbox") && devicesStore.deviceHasFocus(this.props.device.id, this.props.device.address))
        { 
            if (this.state.keyboardStarted)
            {
                switch (keydown.which)
                {
                    case 17: // Control key

                        this.state.keyboardRange = (this.state.keyboardRange[0] === -1 && this.state.keyboardRange[1] === -1 ?
                                                        [0,0] : this.state.keyboardRange);

                        this.setState({ keyboardRange: this.state.keyboardRange});
                        break;
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
                        keydown.stopPropagation();

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
                        keydown.stopPropagation();

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
                        this._removeSelectedPoints(this.state.keyboardRange);
                        this.setState({ keyboardRange: [-1, -1] })
                        break;
                }
            }
            else if (keydown.which === 17) // Control key
            {
                this.setState({ keyboardRange: [0, 0]});
                this.setState({ keyboardStarted: true });
            }      
        }
        else
        {
            if (this.state.keyboardRange[0] !== -1 && this.state.keyboardRange[1] !== -1)
            {
                this.setState({ keyboardRange: [-1, -1] });
            }
        }
    }
    _resizeColumn(columnIndex, targetWidth, movement) {

        var newRegistryValues = this.state.registryValues.map(function (row) {

            row = row.updateIn(["attributes", columnIndex], function (cell) {
                cell.columnWidth = targetWidth;
                
                return cell;
            });

            return row;
        });
        
        var tableWidth = movement + _tableWidth;

        this.setState({ tableWidth: tableWidth + "px"});
        this.setState({ registryValues: newRegistryValues });
    }
    _initializeTable() {
        var table = this._getParentNode();
        var clientRect = table.getClientRects();
        _tableWidth = clientRect[0].width;
    }
    _resetState(device){
    
        var state = {};    

        state.tableRef = "table-" + device.id + "-" + device.address;

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
            state.columnNames = state.registryValues[0].get("attributes").map(function (column) {
                return column.key;
            });
        }

        state.pointsToDelete = [];
        state.allSelected = false;

        state.selectedCells = [];
        state.selectedCellRow = null;
        state.selectedCellColumn = null;
        state.filterOn = false;

        state.tableWidth = (this.hasOwnProperty("state") ? (this.state.tableWidth ? this.state.tableWidth : "100%") : "100%");
        state.resizingTable = false;

        this.scrollToBottom = false;
        this.resizeTable = false;

        // this.keyboardIndex = -1;

        return state;
    }
    _onStoresChange () {

        var deviceHasFocus = devicesStore.deviceHasFocus(this.props.device.id, this.props.device.address);

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
    }   
    _removeSelectedPoints(keyboardRange) {

        var pointNames = this.state.registryValues.filter(function (attributesList) {
    
            return (attributesList.get("virtualIndex") >= this.state.keyboardRange[0] &&
                 attributesList.get("virtualIndex") <= this.state.keyboardRange[1]);

        }, this)
            .map(function (selectedPoints) {
                return selectedPoints.getIn(["attributes", 0]).value
            });

        if (this.state.pointsToDelete.length)
        {
            pointNames = pointNames.concat(this.state.pointsToDelete);
        }

        this._onRemovePoints(pointNames);
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
                attributes={Immutable.List(pointValues)}
                selectedPoints={this.state.selectedPoints}
                deviceId={this.props.device.id} 
                deviceAddress={this.props.device.address}>
            </EditPointForm>);
        
    }
    _onRemovePoints(pointNames) {

        var promptText, confirmText, confirmAction, cancelText;

        var pointsToDelete = (pointNames.length > 0 ? pointNames : this.state.pointsToDelete);

        if (pointsToDelete.length > 0)
        {
            promptText = "Are you sure you want to delete these points? " + pointsToDelete.join(", ");
            confirmText = "Delete";
            confirmAction = this._removePoints.bind(this, pointsToDelete);
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
            // var pointValue = "";

            this.state.registryValues.find(function (row, i) {
                var pointMatched = (row.getIn(["attributes", 0]).value === pointToDelete);

                if (pointMatched)
                {
                    index = i;
                }

                return pointMatched;
            })

            if (index > -1)
            {
                this.state.registryValues.splice(index, 1);
            }
        }, this);

        var newRegistryValues = this.state.registryValues.map(function (row, i) {
            row = row.set("virtualIndex", i);

            return row;
        });

        this.setState({ registryValues: newRegistryValues });
        this.setState({ pointsToDelete: [] });
        // this.setState({ pointNames: this.state.pointNames });

        modalActionCreators.closeModal();
    }
    _onSelectForDelete(pointName) {
        
        var index = this.state.pointsToDelete.indexOf(pointName);

        if (index < 0)
        {
            this.state.pointsToDelete.push(pointName);
        }
        else
        {
            this.state.pointsToDelete.splice(index, 1);
        }

        this.setState({ pointsToDelete: this.state.pointsToDelete });

    }
    _selectAll(checked) {
        this.setState({ allSelected: checked });
    }
    _onAddColumn(index) {

        var newColumnLabel = this.state.registryValues[0].getIn(["attributes", index]).label + "_";

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

            row = row.updateIn(["attributes"], function (columnCells) {
                return columnCells.splice(index + 1, 0, { 
                    "key": newColumn,
                    "label": newColumnLabel,
                    "value": "", 
                    "editable": true, 
                    "keyProp": true,
                    "columnWidth": _defaultColumnWidth
                });
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

            var clonedCell = {};

            var columnCell = row.getIn(["attributes", index]);

            for (var key in columnCell)
            {
                clonedCell[key] = columnCell[key];
            }

            clonedCell.label = newColumnLabel;
            clonedCell.key = newColumn;

            row = row.updateIn(["attributes"], function (columnCells) {
                return columnCells.splice(index + 1, 0, clonedCell);
            });

            return row;
        });

        this.resizeTable = true;

        this.setState({ registryValues: newRegistryValues });
    }
    _onRemoveColumn(index) {

        var columnHeader = this.state.registryValues[0].getIn(["attributes", index]).label;
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

        var columnName = this.state.columnNames[index];

        this.state.columnNames.splice(index, 1);

        var newValues = this.state.registryValues.map(function (row) {
            return row.updateIn(["attributes"], function (columnCells) {
                return columnCells.splice(index, 1);
            });
        });

        index = this.state.keyPropsList.indexOf(columnName);

        if (index > -1)
        {
            this.state.keyPropsList.splice(index, 1);
        }

        this.setState({ keyPropsList: this.state.keyPropsList });
        this.setState({ columnNames: this.state.columnNames });
        this.setState({ registryValues: newValues });

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
                row.get("attributes").get(column).selected = (row.get("attributes").get(column).value.indexOf(findValue) > -1);

                if (row.get("attributes").get(column).selected)
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
            var newValue;

            this.state.registryValues[this.state.selectedCellRow] = 
                this.state.registryValues[this.state.selectedCellRow].updateIn(["attributes", column], function (item) {
                    newValue = item.value = item.value.replace(findValue, replaceValue);
                    return item;
                });

            //If the cell no longer has the target value, deselect it and move focus to the next selected cell
            if (newValue.indexOf(findValue) < 0)
            {
                this.state.registryValues[this.state.selectedCellRow] = 
                    this.state.registryValues[this.state.selectedCellRow].updateIn(["attributes", column], function (item) {
                        item.selected = false;
                        return item;
                    });

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
        
        var selectedCellsToKeep = [];

        this.state.selectedCells.forEach((selectedCell) => {

            // var newValue = this.state.registryValues[selectedCell].attributes[column].value.replace(findValue, replaceValue);

            var newValue;

            this.state.registryValues[selectedCell] = this.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                newValue = item.value = item.value.replace(findValue, replaceValue);
                return item;
            });  

            if (newValue.indexOf(findValue) < 0)
            {
                this.state.registryValues[selectedCell] = this.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                    item.selected = false;
                    selectedCellsToKeep.push(selectedCell);
                    return item;
                }); 
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
            this.state.registryValues[row] = this.state.registryValues[row].updateIn(["attributes", column], function (item) {                    
                item.selected = false;
                return item;
            });

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
                deviceId={this.props.device.id}
                deviceAddress={this.props.device.address} 
                deviceName={this.props.device.name}
                attributes={this.state.registryValues.map(function (row) {
                    return row.get("attributes");
                })}
                onsaveregistry={this._saveRegistry}>
            </PreviewRegistryForm>);
    }
    _saveRegistry() {

        devicesActionCreators.saveRegistry(
                                this.props.device.id, 
                                this.props.device.address, 
                                this.state.registryValues.map(function (row) {
                                        return row.get("attributes");
                                    })
                                );

        modalActionCreators.openModal(<ConfigDeviceForm device={this.props.device}/>);
    }
    _getParentNode() {
        return ReactDOM.findDOMNode(this.refs[this.state.tableRef]);
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
                    keyProps: this.props.device.keyProps,
                    selectedCell: (this.state.selectedCellRow === rowIndex),
                    selectedCellColumn: this.state.selectedCellColumn,
                    filterOn: this.state.filterOn,
                    keyboardSelected: keyboardSelected
                });

                return (
                    <RegistryRow 
                        key={"registryRow-" + attributesList.get("attributes").get(0).value + "-" + rowIndex}
                        attributesList={attributesList} 
                        immutableProps={immutableProps}
                        allSelected={this.state.allSelected}
                        oncheckselect={this._onSelectForDelete}
                        onresizecolumn={this._resizeColumn}
                        oninitializetable={this._initializeTable}
                        ongetparentnode={this._getParentNode}/>
                );
                
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
                                                columnwidth={item.columnWidth}
                                                tooltipMsg="Edit Column"
                                                findnext={this._onFindNext}
                                                replace={this._onReplace}
                                                replaceall={this._onReplaceAll}
                                                replaceEnabled={this.state.selectedCells.length > 0}
                                                onclear={this._onClearFind}
                                                onhide={this._removeFocus}
                                                name={this.props.device.id + "-" + item.key}/>);

                    var headerCell;

                    var columnWidth = {
                        width: item.columnWidth
                    }

                    if (tableIndex === 0)
                    {
                        // var firstColumnWidth = {
                        //     width: (item.length * 10) + "px"
                        // }

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
                            headerCell = ( <th key={"header-" + item.key + "-" + index} style={columnWidth}>
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
                            headerCell = ( <th key={"header-" + item.key + "-" + index} style={columnWidth}>
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
                            headerCell = ( <th key={"header-" + item.key + "-" + index} style={columnWidth}>
                                                <div className="th-inner" >
                                                    { item.label }
                                                    { editSelectButton }
                                                    { editColumnButton }
                                                </div>
                                            </th> );
                        }
                        else
                        {
                            headerCell = ( <th key={"header-" + item.key + "-" + index} style={columnWidth}>
                                                <div className="th-inner" >
                                                    { item.label }
                                                </div>
                                            </th> );
                        }
                    }

                    ++tableIndex;
                    headerColumns.push(headerCell);

                    if ((index + 1) < this.state.registryValues[0].get("attributes").size)
                    {
                        var resizeHandle = <th key={"resize-" + item.key + "-" + index} className="resize-handle-th"></th>;
                        headerColumns.push(resizeHandle);
                    }
                }
            }, this);  

            var checkboxColumnStyle = {
                width: "24px"
            }

            registryHeader = (
                <tr key="header-values">
                    <th style={checkboxColumnStyle} key="header-checkbox">
                        <div className="th-inner">
                            <CheckBox oncheck={this._selectAll}>
                            </CheckBox>
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


        var tableStyle = {
            width: this.state.tableWidth
        };

        var handleStyle = {
            backgroundColor: (this.state.resizingTable ? "#AAA" : "#DDD")
        }
        
        var keyboardHelpButton;

        if (registryRows)
        {
            if (registryRows.length)
            {
                keyboardHelpButton = (
                    <KeyboardHelpButton 
                        deviceInfo={this.props.device.id + "-" + this.props.device.address}/>
                    );
            }
        }

        return (
            <div className={visibilityClass}
                tabIndex={1}
                onFocus={this._focusOnDevice}>
                <div className="fixed-table-container"> 
                    <div className="header-background"></div>      
                    <div className="fixed-table-container-inner">    
                        <table
                            style={tableStyle}
                            ref={this.state.tableRef}
                            className="registryConfigTable">
                            <thead>
                                { registryHeader }                                
                            </thead>
                            <tbody>                            
                                { registryRows }
                            </tbody>
                        </table>
                        {keyboardHelpButton}
                    </div>
                </div>
                { registryButtons }
            </div>
        );
    }
};

function getFilteredPoints(registryValues, filterStr, column) {

    var virtualCount = 0;

    return registryValues.map(function (row, rowIndex) {

        row = row.set("visible", (filterStr === "" || (row.get("attributes")
                                                            .get(column)
                                                            .value
                                                            .trim()
                                                            .toUpperCase()
                                                            .indexOf(filterStr.trim().toUpperCase()) > -1)));

        if (row.get("visible"))
        {
            row = row.set("virtualIndex", virtualCount);
            ++virtualCount;
        }
        else
        {
            row = row.set("virtualIndex", -2);
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
            
            if (cell.keyProp)
            {
                if (rowIndex === 0)
                {
                    var minWidth = (cell.value.length * 10);

                    cell.columnWidth = (minWidth > 200 ? minWidth : 200) + "px"
                }
                else
                {
                    cell.columnWidth = ( cell.hasOwnProperty("columnWidth") ? cell.columnWidth : _defaultColumnWidth ) ;
                }
            }

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
            attributes: Immutable.List(row),
            selected: false
        });
    });
}


export default ConfigureRegistry;