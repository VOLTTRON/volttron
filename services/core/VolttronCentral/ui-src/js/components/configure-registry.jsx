'use strict';

// draws from example at https://plnkr.co/edit/N4iYHYE9gPLp4Y3NHbhk

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
import Immutable from 'immutable';

import {Table, Column, defaultTableRowRenderer, AutoSizer} from 'react-virtualized';
import {SortableHandle, SortableContainer, SortableElement} from 'react-sortable-hoc';

const Draggable = 'react-draggable';

const SortableTable = SortableContainer(Table, {
    withRef: true
});

const SortableRow = SortableElement(defaultTableRowRenderer);

const DragHandle = SortableHandle(({ contents }) => (
    <div>{contents}</div>
));

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var FilterPointsButton = require('./control_buttons/filter-points-button');
var ControlButton = require('./control-button');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');


var registryWs, registryWebsocket;
var _defaultColumnWidth = "200px";
var _tableWidth;
var _table;

class ConfigureRegistry extends BaseComponent {    
    constructor(props) {
        super(props);
        this._bind("_onFilterBoxChange", "_onClearFilter", "_onAddPoint", "_onRemovePoints", "_removePoints", 
            "_selectAll", "_onAddColumn", "_onCloneColumn", "_onRemoveColumn", "_removeColumn",
            "_onFindNext", "_onReplace", "_onReplaceAll", "_onClearFind", "_cancelRegistry",
            "_saveRegistry", "_removeFocus", "_resetState", "_addColumn", "_selectCells", "_updateCell",
            "_cloneColumn", "_onStoresChange", "_fetchExtendedPoints", "_onRegistrySave", "_focusOnDevice",
            "_handleKeyDown", "_onSelectForDelete", "_selectForDelete", "_resizeColumn", "_initializeTable", "_removeSelectedPoints",
            "_rowGetter", "_rowRenderer", "_headerRenderer", "_cellDataGetter", "_cellRenderer", "_sortRow",
            "_showProps" );

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
    _resizeColumn ({ dataKey, deltaX }) {
        // const { flexColumProps } = this.state;

        // // Once a column has been resized, lock its size
        // // This prevents an awkward user experience where their resized width is overridden by flex
        // const thisColumn = flexColumProps[dataKey]
        // thisColumn.flexGrow = 0
        // thisColumn.flexShrink = 0
        
        this.state.columnWidths[dataKey].width = Math.max(MIN_COLUMN_WIDTH, thisColumn.width + deltaX)

        // this.setState({ columnWidths: this.state.columnWidths });

        var newRegistryValues = this.state.registryValues.map(function (row) {

            row = row.updateIn(["attributes", columnIndex], function (cell) {
                cell.columnWidth = targetWidth;
                
                return cell;
            });

            return row;
        });

        this.setState({ registryValues: newRegistryValues });
    }

    // _resizeColumn(columnIndex, targetWidth, movement) {

    //     var newRegistryValues = this.state.registryValues.map(function (row) {

    //         row = row.updateIn(["attributes", columnIndex], function (cell) {
    //             cell.columnWidth = targetWidth;
                
    //             return cell;
    //         });

    //         return row;
    //     });
        
    //     var tableWidth = movement + _tableWidth;

    //     this.setState({ tableWidth: tableWidth + "px"});
    //     this.setState({ registryValues: newRegistryValues });
    // }
    _setTableTarget(table) {
        _table = table;
    }
    _initializeTable() {
        // var table = React.findDOMNode(this.refs[this.state.tableName]);

        var clientRect = _table.getClientRects();
        _tableWidth = clientRect[0].width;
    }
    _resetState(device){
    
        var state = {};    

        state.keyPropsList = device.keyProps;
        state.filterColumn = state.keyPropsList[0];

        state.registryValues = getPointsFromStore(device, state.keyPropsList);

        state.columnNames = [];
        state.columnWidths = [];
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

        state.tableName = "table-" + device.id + "-" + device.address;

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

        // _setUpRegistrySocket();

        //TODO: hook up onmessage in configure-registry.jsx or in registry-row.jsw
        // registryWs.send(JSON.stringify(configRequests));
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
                "filterable": attribute.filterable,
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

    _selectForDelete(rowIndex, e) {
        devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);

        var selected = e.currentTarget.checked;

        this.state.registryValues[rowIndex] = this.state.registryValues[rowIndex].set("checked", selected);

        this.setState({registryValues: this.state.registryValues});

        _onSelectForDelete(this.state.registryValues[rowIndex].get("pointName"));
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
    _selectAll() {
        var allSelected = !this.state.allSelected;
        this.setState({ allSelected: allSelected });
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
                    "filterable": false,
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
    _updateCell(column, rowIndex, e) {

        var currentTarget = e.currentTarget;
        
        this.state.registryValues[rowIndex] = this.state.registryValues[rowIndex].updateIn(["attributes", column], function (item) {

            item.value = currentTarget.value;

            return item;
        });

        this.setState({ registryValues: this.state.registryValues });
        // this.forceUpdate();

    }
    _showProps(attributesList) {
        
        devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);

        modalActionCreators.openModal(
            <EditPointForm 
                deviceId={this.props.device.id} 
                deviceAddress={this.props.device.address}
                attributes={attributesList}/>);
    }
    _rowGetter ({index}) {
        console.log("index: " + index);
        return this.state.registryValues[index];
    }
    _rowRenderer (props) {
        return <SortableRow {...props}></SortableRow>;
    }
    _cellDataGetter({ columnData, dataKey, rowData }) {

        console.log("columnData, dataKey, rowData");
        console.log(columnData);
        console.log(dataKey);
        console.log(rowData);

        var index = columnData.index;

        var cellData = rowData[index];

        return cellData;
    }
    _cellRenderer(props) {

        console.log("cellRendering");
        console.log(props);

        var index = props.columnData.index;
        var cellData = props.rowData.getIn(["attributes", index]);
        var checked = props.rowData.get("checked");
        var cellContainer;

        if (props.columnData.type === "moreButton")
        {
            cellContainer = (
                <div className="ReactVirtualized__Table__rowColumn" 
                    key={"propsButton-" + props.rowIndex}>
                    <div className="propsButton"
                        onClick={this._showProps.bind(this, this.state.registryValues[props.rowIndex].get("attributes"))}>
                        <i className="fa fa-ellipsis-h"></i>
                    </div>
                </div>
            );
        }
        else if (props.columnData.type === "checkbox")
        {
            cellContainer = (
                <div className="ReactVirtualized__Table__rowColumn"
                    key={"checkbox-" + props.rowIndex}>
                    <div className="th-inner">
                        <input type="checkbox"
                            className="registryCheckbox"
                            onChange={this._selectForDelete.bind(this, props.rowIndex)}
                            checked={checked}/>
                    </div>
                </div>
            );

        }
        else
        {
            var selectedCellStyle = (cellData.selected ? {backgroundColor: "#F5B49D", width: "100%"} : {width: "100%"});
                
            var focusedCell = (this.state.selectedCellColumn === index && (this.state.selectedCellRow === props.rowIndex) ? "focusedCell" : "");

            var contents = (
                !cellData.editable ? 
                    <label>{ cellData.value }</label> : 
                    <input 
                        id={cellData.key + "-" + index + "-" + props.rowIndex}
                        type="text"
                        className={focusedCell}
                        style={selectedCellStyle}
                        onChange={this._updateCell.bind(this, index, props.rowIndex)} 
                        value={ cellData.value }/>
                    );

            cellContainer = <DragHandle contents={contents}/>;
        }

        return cellContainer;

    }
    _headerRenderer(props) {

        var headerCell, headerCellContainer;

        // console.log(props);
        // console.log("index: " + props.index);
        // var index = props.index;

        var index;
        var item = this.state.registryValues[0].get("attributes").find(function (column, i) {

            var match = (column.key === props.dataKey);

            if (match)
            {
                index = i;
            }

            return match;
        });

        console.log(item);

        

        // var checkboxColumnStyle = {
        //     width: "24px"
        // }

        // registryHeader = (
        //     <div className="ReactVirtualized__Table__headerRow" key="header-values">
        //         <div className="ReactVirtualized__Table__headerColumn" 
        //             style={checkboxColumnStyle} 
        //             key="header-checkbox">
        //             <div className="th-inner">
        //                 <input type="checkbox"
        //                     onChange={this._selectAll}
        //                     checked={this.state.allSelected}/>
        //             </div>
        //         </div>
        //         { headerColumns }
        //     </div>
        // );

        
        if (props.columnData.type === "checkbox")
        {            
            headerCellContainer = (
                <div className="ReactVirtualized__Table__headerColumn">
                    <div className="th-inner zztop">
                        <input type="checkbox"
                            onChange={this._selectAll}
                            checked={this.state.allSelected}/>
                    </div>
                </div>
            );
        }
        else if (props.columnData.type === "moreButton")
        {
            headerCellContainer = <div></div>;
        }
        else
        {   var editSelectButton = (<EditSelectButton 
                                        onremove={this._onRemoveColumn}
                                        onadd={this._onAddColumn}
                                        onclone={this._onCloneColumn}
                                        column={index}
                                        name={this.props.device.id + "-" + props.dataKey}/>);

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
                                        name={this.props.device.id + "-" + props.dataKey}/>);

            var columnWidth = {
                width: item.columnWidth
            }

            if (item.filterable)
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
                    headerCell = ( <div className="ReactVirtualized__Table__headerColumn" 
                                        key={"header-" + props.dataKey + "-" + index} 
                                        style={columnWidth}>
                                        <div className="th-inner zztop">
                                            { item.label } 
                                            { filterButton } 
                                            { addPointButton } 
                                            { removePointsButton }
                                            { editSelectButton }
                                            { editColumnButton }
                                        </div>
                                    </div>);
                }
                else
                {
                    headerCell = ( <div className="ReactVirtualized__Table__headerColumn" 
                                        key={"header-" + props.dataKey + "-" + index} 
                                        style={columnWidth}>
                                        <div className="th-inner zztop">
                                            { item.label } 
                                            { filterButton } 
                                            { addPointButton } 
                                            { removePointsButton }
                                        </div>
                                    </div>);
                }
            }
            else
            {
                if (item.editable)
                {
                    headerCell = ( <div className="ReactVirtualized__Table__headerColumn" 
                                        key={"header-" + props.dataKey + "-" + index} 
                                        style={columnWidth}>
                                        <div className="th-inner" >
                                            { item.label }
                                            { editSelectButton }
                                            { editColumnButton }
                                        </div>
                                    </div> );
                }
                else
                {
                    headerCell = ( <div className="ReactVirtualized__Table__headerColumn" 
                                        key={"header-" + props.dataKey + "-" + index} 
                                        style={columnWidth}>
                                        <div className="th-inner" >
                                            { item.label }
                                        </div>
                                    </div> );
                }
            

                headerCellContainer = (
                    <div className="draggable-header">
                        {headerCell}
                        <Draggable
                            axis='x'
                            defaultClassName='DragHandle'
                            defaultClassNameDragging='DragHandleActive'
                            onStop={(event, data) => this._resizeColumn({
                                dataKey: props.dataKey,
                                deltaX: data.x
                            })}
                            position={{
                                x: 0,
                                y: 0
                            }}
                            zIndex={999}>
                            <div className="resize-handle-th"></div>
                        </Draggable>

                    </div>);
            }
        }

        return headerCellContainer;
    }
    _sortRow ({ newIndex, oldIndex }) {
        if (newIndex !== oldIndex) {
            
            const row = this.state.registryValues[oldIndex];

            this.state.registryValues.splice(oldIndex, 1)
            this.state.registryValues.splice(newIndex, 0, row)

            //this.forceUpdate() // Re-render

            this.setState({ registryValues: this.state.registryValues });
        }
    }
    render() {

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
        
        var registryButtons = (
            <div className="registry-buttons" style={wideDiv}>
                <div className="inlineBlock">
                    {cancelButton}
                </div>
                <div className="inlineBlock">
                    {saveButton}
                </div>                    
            </div>
        );   

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

        var columns = [];

        if (this.state.registryValues.length)
        {
            keyboardHelpButton = (
                <KeyboardHelpButton 
                    deviceInfo={this.props.device.id + "-" + this.props.device.address}/>
                );    

            columns.push(
                <Column
                    key="checkbox"
                    label="checkbox"
                    dataKey="checkbox"
                    columnData={{"index": -1, "type": "checkbox"}}
                    headerRenderer={this._headerRenderer}
                    cellRenderer={this._cellRenderer}
                    width={50}/>
            );

            this.state.registryValues[0].get("attributes").forEach(function (item, index) {

                if (item.keyProp)
                {
                    columns.push(
                        <Column
                            key={item.key}
                            label={item.label}
                            dataKey={item.key}
                            columnData={{"index": index}}
                            headerRenderer={this._headerRenderer}
                            cellDataGetter={this._cellDataGetter}
                            cellRenderer={this._cellRenderer}
                            width={item.columnWidth}/>
                    );
                }
            }, this);

            columns.push(
                <Column
                    key="moreButton"
                    label="moreButton"
                    dataKey="moreButton"
                    columnData={{"index": -1, "type": "moreButton"}}
                    headerRenderer={this._headerRenderer}
                    cellDataGetter={this._cellDataGetter}
                    cellRenderer={this._cellRenderer}
                    width={50}/>
            );
        }

        return (
            <div className={visibilityClass}
                tabIndex={1}
                onFocus={this._focusOnDevice}>
                <div className="fixed-table-container"> 
                    <div className="header-background"></div>      
                    <div className="fixed-table-container-inner"> 
                        <SortableTable 
                            getContainer={(wrappedInstance) => ReactDOM.findDOMNode(wrappedInstance.Grid)}
                            height={500}
                            width={500}
                            onSortEnd={this._sortRow}
                            rowClassName='Row'                                    
                            rowGetter={this._rowGetter}
                            rowRenderer={this._rowRenderer}
                            rowCount={this.state.registryValues.length}
                            rowHeight={40}
                            headerHeight={40}
                            className="registryConfigTable">
                            {columns}                                                      
                        </SortableTable>
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

        var pointName = "";

        row.forEach(function (cell) {
            cell.keyProp = (keyPropsList.indexOf(cell.key) > -1); 
            
            if (cell.keyProp)
            {
                if (rowIndex === 0)
                {
                    var minWidth = (cell.value.length * 10);

                    cell.columnWidth = (minWidth > 200 ? minWidth : 200)
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
            else if (cell.key === "point_name" || cell.key === "reference_point_name")
            {
                pointName = cell.value;
            }
        });

        return Immutable.fromJS({ 
            pointName: pointName,
            visible: true, 
            virtualIndex: rowIndex, 
            bacnetObjectType: bacnetObjectType, 
            index: objectIndex,
            attributes: Immutable.List(row),
            selected: false,
            checked: false
        });
    });
}


export default ConfigureRegistry;