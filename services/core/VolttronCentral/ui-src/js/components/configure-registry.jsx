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
import FilterPointsButton from './control_buttons/filter-points-button';
import CheckBox from './check-box';
import Immutable from 'immutable';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');

var _defaultColumnWidth = "200px";
var _tableWidth;

var _esc = 27;
var _ctrl = 17;
var _enter = 13;
var _space = 32;
var _down = 40;
var _up = 38;

class ConfigureRegistry extends BaseComponent {    
    constructor(props) {
        super(props);
        this._bind("_onFilterBoxChange", "_onClearFilter", "_onAddPoint", "_onRemovePoints", "_removePoints", 
            "_selectAll", "_onAddColumn", "_onCloneColumn", "_onRemoveColumn", "_removeColumn",
            "_onFindNext", "_onReplace", "_onReplaceAll", "_onClearFind", "_cancelRegistry",
            "_saveRegistry", "_removeFocus", "_resetState", "_addColumn", "_selectCells", "_getParentNode",
            "_cloneColumn", "_onStoresChange", "_selectPoints", "_onRegistrySave", "_focusOnDevice",
            "_handleKeyDown", "_onSelectForActions", "_resizeColumn", "_initializeTable", "_updateTable",
            "_handleMouseMove", "_createBlankRow", "_setTaptipTarget" );

        this.state = this._resetState(this.props.device);

        this.state.keyboardRange = [-1, -1];
    }
    componentDidMount() {
        this.containerDiv = document.getElementsByClassName("fixed-table-container")[0];
        this.fixedHeader = document.getElementsByClassName("header-background")[0];
        this.fixedInner = document.getElementsByClassName("fixed-table-container-inner")[0];
        this.registryTable = document.getElementsByClassName("registryConfigTable")[0];
        this.viewDiv = document.getElementsByClassName("view")[0];

        this.taptipTarget = null;

        this.direction = "down";

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

        // scroll to keep keyboard selections on screen
        if (this.state.keyboardRange[0] > -1)
        {
            var rowItems = document.querySelectorAll(".registry-row");

            var topItem = rowItems[this.state.keyboardRange[0]];
            var bottomItem = rowItems[this.state.keyboardRange[1]];

            var tableRect = this.containerDiv.getBoundingClientRect();
            var viewRect = this.viewDiv.getBoundingClientRect();
            var topRect = topItem.getBoundingClientRect();
            var bottomRect = bottomItem.getBoundingClientRect();

            if (this.direction === "down")
            {    
                if (bottomRect.bottom > viewRect.bottom)
                {
                    var newTop = bottomRect.top - tableRect.top;

                    this.viewDiv.scrollTop = newTop;
                }
            }
            else
            {
                if (topRect.top < viewRect.top)
                {
                    var newTop = topRect.top - tableRect.top;

                    this.viewDiv.scrollTop = newTop;
                }
            }
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

            // scroll to keep find-and-replace selections on screen
            var targetRow = focusedCell.parentNode.parentNode;

            var tableRect = this.containerDiv.getBoundingClientRect();
            var viewRect = this.viewDiv.getBoundingClientRect();
            var targetRect = targetRow.getBoundingClientRect();
                
            if (targetRect.bottom > viewRect.bottom || targetRect.top < viewRect.top)
            {
                var newTop = targetRect.top - tableRect.top;

                this.viewDiv.scrollTop = newTop;
            }

            // move the find-and-replace taptip to keep it on screen
            if (this.taptipTarget)
            {
                var taptipRect = this.taptipTarget.getBoundingClientRect();

                var windowHeight = window.innerHeight;

                if (taptipRect.top < 0 || taptipRect.top > windowHeight)
                {
                    var innerTable = this._getParentNode();
                    var top = innerTable.getClientRects()[0].top;

                    var newTop = 100;

                    if (top < 0)
                    {
                        newTop = 0 - top + 100;
                    }

                    this.taptipTarget.style.top = newTop + "px";
                }
            }
        }
    }
    componentWillReceiveProps(nextProps) {
        if ((this.props.device.configuring !== nextProps.device.configuring) || 
            (this.props.device.showPoints !== nextProps.device.showPoints) ||
            (this.props.device.registryCount !== nextProps.device.registryCount) ||
            (this.props.device.name !== nextProps.device.name))
        {
            var newState = this._resetState(nextProps.device);
            newState.keyboardRange = this.state.keyboardRange;

            this.setState(newState);
        }
    }
    _handleMouseMove(evt) {
        if (!this.state.hoverEnabled)
        {
            this.setState({ hoverEnabled: true });

            if (this.state.keyboardStarted)
            {
                this.setState({ keyboardStarted: false });
                this.setState({ keyboardRange: [-1, -1]});
            }
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
                    case _ctrl: 

                        this.state.keyboardRange = (this.state.keyboardRange[0] === -1 && this.state.keyboardRange[1] === -1 ?
                                                        [0,0] : this.state.keyboardRange);

                        this.setState({ keyboardRange: this.state.keyboardRange});
                        break;
                    case _esc:
                        this.setState({ keyboardRange: [-1, -1]});
                        this.setState({ keyboardStarted: false });
                        this.setState({ hoverEnabled: true });

                        break;
                    case _enter:

                        this._selectPoints(this.state.keyboardRange);

                        break;
                    // case 9:    //Tab
                    case _space:   
                    case _down:
                        keydown.preventDefault();
                        keydown.stopPropagation();

                        this.direction = "down";

                        if (keydown.shiftKey) // extend down
                        {
                            var newIndex = this.state.keyboardRange[1] + 1;

                            if (newIndex < this.state.registryValues.length)
                            {
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
                                this.setState({ keyboardRange: [newIndex, newIndex]});
                            }
                        }

                        break;
                    case _up:
                        keydown.preventDefault();
                        keydown.stopPropagation();

                        this.direction = "_up";

                        if (keydown.shiftKey) // extend up
                        {
                            var newIndex = this.state.keyboardRange[0] - 1;

                            if (newIndex > -1)
                            {
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
                                this.setState({ keyboardRange: [newIndex, newIndex]});
                            }
                        }

                        break;
                }
            }
            else if (keydown.which === _ctrl)
            {
                this.setState({ keyboardRange: [0, 0]});
                this.setState({ keyboardStarted: true });
                this.setState({ hoverEnabled: false });
            }     
        }
        else
        {
            if ((keydown.target.nodeName === "INPUT") && 
                (keydown.target.type === "text"))
            {
                if (keydown.which === _esc)
                {
                    keydown.target.blur();
                }
            }
            else if (this.state.keyboardRange[0] !== -1 && this.state.keyboardRange[1] !== -1)
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

        state.configUpdate = (this.props.registryFile ? true : false);
        state.allSelected = state.configUpdate;

        state.tableRef = "table-" + device.id + "-" + device.address;

        state.keyPropsList = device.keyProps;
        state.filterColumn = state.keyPropsList[0];

        state.registryValues = getPointsFromStore(device, state.allSelected, state.keyPropsList);

        state.columnNames = [];
        state.filteredList = [];

        state.deviceHasFocus = true;
        state.hoverEnabled = true;

        if (state.registryValues.length > 0)
        {
            state.columnNames = state.registryValues[0].get("attributes").map(function (column) {
                return column.key;
            });
        }

        state.selectedCells = [];
        state.selectedCellRow = null;
        state.selectedCellColumn = null;
        state.filterOn = false;

        state.tableWidth = (this.hasOwnProperty("state") ? (this.state.tableWidth ? this.state.tableWidth : "100%") : "100%");
        state.resizingTable = false;

        this.scrollToBottom = false;
        this.resizeTable = false;

        return state;
    }
    _onStoresChange () {

        var deviceHasFocus = devicesStore.deviceHasFocus(this.props.device.id, this.props.device.address);

        if (deviceHasFocus !== this.state.deviceHasFocus)
        {
            this.setState({ deviceHasFocus: deviceHasFocus });
        }

        var updatedRow = devicesStore.getUpdatedRow(this.props.device.id, this.props.device.address);

        if (updatedRow)
        {
            this._updateTable(Immutable.List(updatedRow));
        }
    }
    _selectPoints(keyboardRange) {

        var configRequests = {};

        var registryValues = this.state.registryValues.map(function (attributesList) {

            if (attributesList.get("virtualIndex") >= this.state.keyboardRange[0] && attributesList.get("virtualIndex") <= this.state.keyboardRange[1])
            {
                if (!configRequests.hasOwnProperty(attributesList.get("bacnetObjectType")))
                {
                    configRequests[attributesList.get("bacnetObjectType")] = [];
                }

                configRequests[attributesList.get("bacnetObjectType")].push(attributesList.get("index"));

                var selected = !attributesList.get("selected");

                attributesList = attributesList.set("selected", selected);
            }

            return attributesList;

        }, this);

        this.setState({ registryValues: registryValues });
    }
    _focusOnDevice() {
        devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);
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

        var pointValues = this._createBlankRow(this.state.registryValues[0].get("attributes"));

        modalActionCreators.openModal(
            <EditPointForm 
                attributes={Immutable.List(pointValues)}
                deviceId={this.props.device.id} 
                deviceAddress={this.props.device.address}>
            </EditPointForm>);        
    }
    _updateTable(updatedRow) {

        var i = -1;
        var keyProps = [];
        var updateKeyProps = false;

        var attributes = this.state.registryValues.find(function (attributes, index) {
            var match = (attributes.getIn(["attributes", 0]).value === updatedRow.get(0).value);

            if (match)
            {
                i = index;
            }

            return match;
        });

        updatedRow.forEach(function (item) {
            if (item.keyProp)
            {
                keyProps.push(item.key);
                if (this.state.keyPropsList.indexOf(item.key) < 0)
                {
                    updateKeyProps = true;
                }
            }
            else
            {
                if (this.state.keyPropsList.indexOf(item.key) > -1)
                {
                    updateKeyProps = true;
                }
            }
        }, this);

        if (typeof attributes !== "undefined")
        {                
            this.state.registryValues[i] = this.state.registryValues[i].set("attributes", updatedRow);
        }
        else
        {
            this.state.registryValues.push(initializeRow(this.state.allSelected, updatedRow.toJS(), this.state.registryValues.length, keyProps));
        }

        if (updateKeyProps)
        {
            this.state.registryValues = this.state.registryValues.map(function (attributeRow) {

                attributeRow = attributeRow.updateIn(["attributes"], function (columnCells) {

                    columnCells = columnCells.map(function (columnCell) {
                        columnCell.keyProp = (keyProps.indexOf(columnCell.key) > -1);
                        return columnCell;
                    });

                    return columnCells;
                });

                return attributeRow;
            });

            this.setState({keyPropsList: keyProps});
        }
        
        this.setState({registryValues: this.state.registryValues});
    }
    _createBlankRow(attributes) {
        var pointValues = [];

        attributes.forEach(function (attribute) {
            pointValues.push({ 
                "key" : attribute.key, 
                "label": attribute.label,
                "value": "", 
                "editable": true, 
                "keyProp": attribute.keyProp 
            });
        }, this);

        return pointValues;
    }
    _onRemovePoints() {

        var promptText, confirmText, confirmAction, cancelText;

        var selectedPointNames = [];
        var selectedPointIndices = [];

        this.state.registryValues.forEach(function (attributeRow, rowIndex) {

            if (attributeRow.get("selected"))
            {
                attributeRow.get("attributes").find(function (columnCell, columnIndex) {

                    var match = (columnCell.key.toLowerCase() === "volttron_point_name");

                    if (match)
                    {
                        selectedPointNames.push(columnCell.value);
                    }

                    return match;
                });

                selectedPointIndices.push(rowIndex);
            }       
        });

        if (selectedPointNames.length > 0)
        {
            promptText = "Are you sure you want to delete these points? " + selectedPointNames.join(", ");
            confirmText = "Delete";
            confirmAction = this._removePoints.bind(this, selectedPointIndices);
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
    _removePoints(pointIndices) {
        
        var backupPoint = JSON.parse(JSON.stringify(this.state.registryValues[0].get("attributes")));
        
        for (var i = pointIndices.length - 1; i > -1; i--)
        {
            this.state.registryValues.splice(pointIndices[i], 1);
        }


        var newRegistryValues = [];

        if (this.state.registryValues.length === 0)
        {
            var newBlankRow = this._createBlankRow(backupPoint);

            newRegistryValues.push(
                initializeRow(
                    newBlankRow, 
                    1, 
                    this.state.keyPropsList
                )
            );
        }
        else
        {
            newRegistryValues = this.state.registryValues.map(function (row, i) {
                row = row.set("virtualIndex", i);

                return row;
            });
        }

        if (this.state.allSelected)
        {
            this.setState({ allSelected: false });
        }

        this.setState({ registryValues: newRegistryValues });

        modalActionCreators.closeModal();
    }
    _onSelectForActions(rowIndex) {
        
        var newRegistryValues = this.state.registryValues.map(function (row, index) {
            
            if (index === rowIndex)
            {
                var selected = !row.get("selected");
                row = row.set("selected", selected);
            }

            return row;
        });

        this.setState({ registryValues: newRegistryValues });  
        this.setState({ allSelected: false });

    }
    _selectAll(checked) {
        var newRegistryValues = this.state.registryValues.map(function (row) {
            if (row.get("visible"))
            {
                row = row.set("selected", checked);
            }
            return row;
        });

        this.setState({ registryValues: newRegistryValues });
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
        this.state.columnNames = this.state.columnNames.splice(index + 1, 0, newColumn);
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
        this.state.columnNames = this.state.columnNames.splice(index + 1, 0, newColumn);
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

        this.state.columnNames = this.state.columnNames.splice(index, 1);

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
                row.get("attributes").get(column).selected = (
                    (row.get("visible")) &&
                    (row.get("attributes").get(column).value.indexOf(findValue) > -1));

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
            else
            {
                this.setState({ selectedCellRow: this.state.selectedCells[0] });
            }
        }
    }
    _onReplace(findValue, replaceValue, column) {

        if (this.state.selectedCellRow === null)
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

            while (newValue.indexOf(findValue) > -1)
            {
                this.state.registryValues[this.state.selectedCellRow] = 
                    this.state.registryValues[this.state.selectedCellRow].updateIn(["attributes", column], function (item) {
                        newValue = item.value = item.value.replace(findValue, replaceValue);
                        return item;
                    });
            }

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
            

            this.setState({ registryValues: this.state.registryValues});
        }
    }
    _onReplaceAll(findValue, replaceValue, column) {
        
        var selectedCellsToKeep = [];

        this.state.selectedCells.forEach((selectedCell) => {

            var newValue;

            this.state.registryValues[selectedCell] = this.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                newValue = item.value = item.value.replace(findValue, replaceValue);
                return item;
            });  

            while (newValue.indexOf(findValue) > -1)
            {
                this.state.registryValues[selectedCell] = this.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                    newValue = item.value = item.value.replace(findValue, replaceValue);
                    return item;
                });
            }

            this.state.registryValues[selectedCell] = this.state.registryValues[selectedCell].updateIn(["attributes", column], function (item) {
                item.selected = false;
                selectedCellsToKeep.push(selectedCell);
                return item;
            }); 
        });

        this.setState({ selectedCellRow: null});
        this.setState({ selectedCells: selectedCellsToKeep });
        this.setState({ selectedCellColumn: null });
        this.setState({ registryValues: this.state.registryValues});
    }
    _onClearFind(column) {

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

        var attributes = this.state.registryValues.filter(function (row) {
                                return row.get("selected");
                            })
                            .map(function (row) {
                                return row.get("attributes");
                            });

        if (attributes.length === 0)
        {
            modalActionCreators.openModal(
                <ConfirmForm
                    promptTitle="Registry Config File"
                    promptText="Select points to include in the registry file."
                    cancelText="OK"
                ></ConfirmForm>
            );
        }
        else
        {
            if (this.props.dataValidator(attributes[0], function (cellsNotFound) {
                modalActionCreators.openModal(
                    <ConfirmForm
                        promptTitle="Registry Config File"
                        promptText={"Unable to save this registry configuration. The " +
                            "following data columns must be included in the registry " +
                            "config file: " + cellsNotFound + ". Hint: Use the Edit Columns " +
                            "options to add, duplicate, and remove columns."}
                        cancelText="OK"
                    ></ConfirmForm>
                );
            }))
            {
                devicesActionCreators.loadRegistryFiles(
                    this.props.device.platformUuid, 
                    this.props.device.agentDriver, 
                    this.props.device.id,
                    this.props.device.address
                ).then(function () {

                    modalActionCreators.openModal(
                        <PreviewRegistryForm 
                            deviceId={this.props.device.id}
                            deviceAddress={this.props.device.address} 
                            deviceName={this.props.device.name}
                            fileName={this.props.registryFile}
                            attributes={attributes}
                            onsaveregistry={this._saveRegistry}>
                        </PreviewRegistryForm>);
                    }.bind(this));
            }
        }
    }
    _saveRegistry(fileName) {

        var csvData = "";

        var headerRow = [];

        this.state.registryValues[0].get("attributes").forEach(function (item) {
            headerRow.push(item.label);
        });

        csvData = headerRow.join() + "\n";

        var newValues = this.state.registryValues.map(function (attributeRow, rowIndex) {

            if (attributeRow.get("selected"))
            {
                var newRow = [];

                attributeRow.get("attributes").forEach(function (columnCell, columnIndex) {

                    var altValue = columnCell.value;

                    var index = altValue.indexOf(",");

                    if (index > -1)
                    {
                        altValue = "\"" + altValue + "\"";
                    }

                    newRow.push(altValue);
                });

                csvData = csvData.concat(newRow.join() + "\n");

                attributeRow = attributeRow.set("alreadyUsed", true);
                attributeRow = attributeRow.set("selected", false);
            }

            return attributeRow;

        });

        devicesActionCreators.saveRegistry(this.props.device, fileName, this.state.configUpdate, csvData);

        if (!this.state.configUpdate)
        {
            this.setState({ registryValues: newValues });
            this.setState({ allSelected: false });

            modalActionCreators.openModal(<ConfigDeviceForm device={this.props.device} registryFile={fileName}/>);
        }
        else
        {
            modalActionCreators.closeModal();

            if (typeof this.props.onreconfigure === "function")
            {
                this.props.onreconfigure(fileName);
            }
        }
    }
    _getParentNode() {
        return ReactDOM.findDOMNode(this.refs[this.state.tableRef]);
    }
    _setTaptipTarget(taptip) {
        this.taptipTarget = taptip;
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
                    selectedRow: attributesList.get("selected"),
                    keyboardSelected: keyboardSelected
                });

                return (
                    <RegistryRow 
                        key={"registryRow-" + attributesList.get("attributes").get(0).value + "-" + rowIndex}
                        attributesList={attributesList} 
                        immutableProps={immutableProps}
                        oncheckselect={this._onSelectForActions}
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
                    var editColumnButtonName = 
                        "editColumn-" + this.props.device.id + "-" + this.props.device.address + "-" + item.key + "-controlButton";

                    var editItems = [
                        { 
                            label: "Find and Replace",
                            position: "top",
                            action: controlButtonActionCreators.toggleTaptip.bind(this, editColumnButtonName)
                        },
                        { 
                            label: "Duplicate",
                            action: this._onCloneColumn.bind(this, index)
                        },
                        { 
                            label: "Add",
                            action: this._onAddColumn.bind(this, index)
                        },
                        { 
                            label: "Remove",
                            position: "bottom",
                            action: this._onRemoveColumn.bind(this, index)
                        }
                    ];

                    var editColumnTooltip = {
                        content: "Edit Column",
                        tooltipX: 80,
                        tooltipY: -60
                    }

                    var editColumnTaptip = {                        
                        taptipX: 80,
                        taptipY: -80
                    }

                    var editSelectButton = (<EditSelectButton 
                                                tooltip={editColumnTooltip}
                                                taptip={editColumnTaptip}
                                                iconName="pencil"
                                                buttonClass="edit_column_select"
                                                name={this.props.device.id + "-" + this.props.device.address + "-" + item.key}
                                                listItems={editItems}/>);

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
                                                name={editColumnButtonName}
                                                taptipRef={this._setTaptipTarget}/>);

                    var headerCell;

                    var columnWidth = {
                        width: (item.columnWidth ? item.columnWidth : _defaultColumnWidth)
                    }

                    if (tableIndex === 0)
                    {
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
                        <div className="th-inner"
                            style={{marginLeft: "0px"}}>
                            <div className="centerContent flexContent">
                                <CheckBox 
                                    controlClass="flexChild"
                                    oncheck={this._selectAll}
                                    selected={this.state.allSelected}>
                                </CheckBox>
                            </div>
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
                    <div className="inlineBlock cancel-button">
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

        var tableClasses = ["registryConfigTable"];

        if (this.state.hoverEnabled)
        {
            tableClasses.push("hover-enabled");
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
                            className={tableClasses.join(" ")}
                            onMouseMove={this._handleMouseMove}>
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

function getPointsFromStore(device, allSelected, keyPropsList) {
    return initializeList(allSelected, devicesStore.getRegistryValues(device.id, device.address, device.name), keyPropsList);
}

function initializeList(allSelected, registryConfig, keyPropsList)
{
    return registryConfig.map(function (row, rowIndex) {
        return initializeRow(allSelected, row, rowIndex, keyPropsList);
    });
}

function initializeRow(allSelected, row, rowIndex, keyPropsList)
{
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
        selected: allSelected,
        alreadyUsed: false
    });
}


export default ConfigureRegistry;