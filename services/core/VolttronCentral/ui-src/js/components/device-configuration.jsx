'use strict';

import React from 'react';
import BaseComponent from './base-component';
import EditPointForm from './edit-point-form';
import ConfigDeviceForm from './config-device-form';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
var FilterPointsButton = require('./control_buttons/filter-points-button');
var ControlButton = require('./control-button');
var EditSelectButton = require('./control_buttons/edit-select-button');
var EditColumnButton = require('./control_buttons/edit-columns-button');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');

class DeviceConfiguration extends BaseComponent {    
    constructor(props) {
        super(props);
        this._bind("_onFilterBoxChange", "_onClearFilter", "_onAddPoint", "_onRemovePoints", "_removePoints", 
            "_selectForDelete", "_selectAll", "_onAddColumn", "_onCloneColumn", "_onRemoveColumn", "_removeColumn",
            "_updateCell", "_onFindNext", "_onReplace", "_onReplaceAll", "_onClearFind", "_cancelRegistry",
            "_saveRegistry", "_removeFocus", "_resetState", "_showProps" );

        this.state = this._resetState(this.props.device);
    }
    componentDidMount() {
        // platformsStore.addChangeListener(this._onStoresChange);

        this.containerDiv = document.getElementsByClassName("fixed-table-container-inner")[0];
        this.fixedHeader = document.getElementsByClassName("header-background")[0];
        this.fixedInner = document.getElementsByClassName("fixed-table-container-inner")[0];
        this.registryTable = document.getElementsByClassName("registryConfigTable")[0];
    }
    componentWillUnmount() {
        // platformsStore.removeChangeListener(this._onStoresChange);
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
        this.setState(this._resetState(nextProps.device));
    }
    // _onStoresChange() {
    //     this.setState({registryValues: getPointsFromStore(this.props.device) });
    // }
    _resetState(device){
    
        var state = {};    

        state.keyPropsList = device.keyProps;
        state.filterColumn = state.keyPropsList[0];

        state.registryValues = getPointsFromStore(device, state.keyPropsList);

        state.registryHeader = [];
        state.columnNames = [];
        state.pointNames = [];
        state.filteredList = [];

        if (state.registryValues.length > 0)
        {
            state.registryHeader = getRegistryHeader(state.registryValues[0]);
            state.columnNames = state.registryValues[0].map(function (columns) {
                return columns.key;
            });

            state.pointNames = state.registryValues.map(function (points) {
                return points[0].value;
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

        return state;
    }
    _onFilterBoxChange(filterValue) {
        this.setState({ filterOn: true });
        this.setState({ registryValues: getFilteredPoints(
                                            this.state.registryValues, 
                                            filterValue,
                                            this.state.filterColumn
                                        ) });
    }
    _onClearFilter() {
        this.setState({ filterOn: false });
        // this.setState({registryValues: getPointsFromStore(this.props.device) }); //TODO: when filtering, set nonmatches to hidden so they're
                                                                                //still there and we don't lose information in inputs
                                                                                //then to clear filter, set all to not hidden
    }
    _onAddPoint() {

        var pointNames = this.state.pointNames;

        pointNames.push("");

        this.setState({ pointNames: pointNames });

        var registryValues = this.state.registryValues;

        var pointValues = [];

        this.state.columnNames.map(function (column) {
            pointValues.push({ 
                                "key" : column, 
                                "value": "", 
                                "editable": true, 
                                "keyProp": (this.state.keyPropsList.indexOf(column) > -1) 
                            });
        });

        registryValues.push(pointValues);

        this.setState({ registryValues: registryValues });

        this.scrollToBottom = true;
    }
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
        
        var registryValues = JSON.parse(JSON.stringify(this.state.registryValues));
        var pointsList = JSON.parse(JSON.stringify(this.state.pointsToDelete));
        var namesList = JSON.parse(JSON.stringify(this.state.pointNames));

        pointsToDelete.forEach(function (pointToDelete) {

            var index = -1;
            var pointValue = "";

            registryValues.some(function (vals, i) {
                var pointMatched = (vals[0].value ===  pointToDelete);

                if (pointMatched)
                {
                    index = i;
                    pointValue = vals[0].value;
                }

                return pointMatched;
            })

            if (index > -1)
            {
                registryValues.splice(index, 1);
                
                index = pointsList.indexOf(pointValue);

                if (index > -1)
                {
                    pointsList.splice(index, 1);
                }

                index = namesList.indexOf(pointValue);

                if (index > -1)
                {
                    namesList.splice(index, 1);
                }
            }
        });

        this.setState({ registryValues: registryValues });
        this.setState({ pointsToDelete: pointsList });
        this.setState({ pointNames: namesList });

        modalActionCreators.closeModal();
    }
    _selectForDelete(attributesList) {
        
        var pointsToDelete = this.state.pointsToDelete;

        var index = pointsToDelete.indexOf(attributesList[0].value);

        if (index < 0)
        {
            pointsToDelete.push(attributesList[0].value);
        }
        else
        {
            pointsToDelete.splice(index, 1);
        }

        this.setState({ pointsToDelete: pointsToDelete });

    }
    _selectAll() {
        var allSelected = !this.state.allSelected;

        this.setState({ allSelected: allSelected });

        this.setState({ pointsToDelete : (allSelected ? JSON.parse(JSON.stringify(this.state.pointNames)) : []) }); 
    }
    _onAddColumn(index) {

        var registryHeader = JSON.parse(JSON.stringify(this.state.registryHeader));
        var registryValues = JSON.parse(JSON.stringify(this.state.registryValues));
        var columnNames = JSON.parse(JSON.stringify(this.state.columnNames));
        var keyPropsList = JSON.parse(JSON.stringify(this.state.keyPropsList));

        var newHeader = registryHeader[index] + "-";
        registryHeader.splice(index + 1, 0, newHeader);

        var newColumn = columnNames[index] + "-";
        columnNames.splice(index + 1, 0, newColumn);
        keyPropsList.push(newColumn);

        this.setState({ registryHeader: registryHeader });
        this.setState({ columnNames: columnNames });
        this.setState({ keyPropsList: keyPropsList });

        var newRegistryValues = registryValues.map(function (values) {

            values.splice(index + 1, 0, { 
                                            "key": newColumn, 
                                            "value": "", 
                                            "editable": true, 
                                            "keyProp": true 
                                        });
            return values;
        });

        this.resizeTable = true;

        this.setState({ registryValues: newRegistryValues });        
    }
    _onCloneColumn(index) {

        var registryHeader = JSON.parse(JSON.stringify(this.state.registryHeader));
        var registryValues = JSON.parse(JSON.stringify(this.state.registryValues));
        var columnNames = JSON.parse(JSON.stringify(this.state.columnNames));
        var keyPropsList = JSON.parse(JSON.stringify(this.state.keyPropsList));
        
        var newHeader = registryHeader[index] + "_";
        registryHeader.splice(index + 1, 0, newHeader);

        var newColumn = columnNames[index] + "_";
        columnNames.splice(index + 1, 0, newColumn);
        keyPropsList.push(newColumn);

        this.setState({ registryHeader: registryHeader });
        this.setState({ columnNames: columnNames });
        this.setState({ keyPropsList: keyPropsList });

        var newRegistryValues = registryValues.map(function (values, row) {

            var clonedValue = {};

            for (var key in values[index])
            {
                clonedValue[key] = values[index][key];
            }

            values.splice(index + 1, 0, clonedValue);

            return values;
        });

        this.resizeTable = true;

        this.setState({ registryValues: newRegistryValues });

    }
    _onRemoveColumn(index) {

        var columnHeader = this.state.registryHeader[index];

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

        var registryHeader = JSON.parse(JSON.stringify(this.state.registryHeader));
        var registryValues = JSON.parse(JSON.stringify(this.state.registryValues));
        var columnNames = JSON.parse(JSON.stringify(this.state.columnNames));
        var keyPropsList = JSON.parse(JSON.stringify(this.state.keyPropsList));

        var columnName = columnNames[index];

        columnNames.splice(index, 1);

        registryHeader.splice(index, 1);

        registryValues.forEach(function (values) {
            values.splice(index, 1);
        });

        index = keyPropsList.indexOf(columnName);

        if (index > -1)
        {
            keyPropsList.splice(index, 1);
        }

        this.setState({ keyPropsList: keyPropsList });
        this.setState({ columnNames: columnNames });
        this.setState({ registryValues: registryValues });
        this.setState({ registryHeader: registryHeader });

        this.resizeTable = true;

        modalActionCreators.closeModal();

    }
    _showProps(attributesList) {
        modalActionCreators.openModal(<EditPointForm device={this.props.device} attributes={attributesList}/>);
    }
    _updateCell(row, column, e) {

        var currentTarget = e.currentTarget;
        var newRegistryValues = this.state.registryValues.slice();

        newRegistryValues[row][column].value = currentTarget.value;

        this.setState({ registryValues: newRegistryValues });
    }
    _removeFocus() {
        this.setState({ selectedCellRow: null});
    }
    _onFindNext(findValue, column) {

        var registryValues = this.state.registryValues.slice();
        
        if (this.state.selectedCells.length === 0)
        {
            var selectedCells = [];

            this.setState({ registryValues: registryValues.map(function (values, row) {

                    //searching i-th column in each row, and if the cell contains the target value, select it
                    values[column].selected = (values[column].value.indexOf(findValue) > -1);

                    if (values[column].selected)
                    {
                        selectedCells.push(row);
                    }

                    return values;
                })
            });

            if (selectedCells.length > 0)
            {
                this.setState({ selectedCells: selectedCells });
                this.setState({ selectedCellColumn: column });

                //set focus to the first selected cell
                this.setState({ selectedCellRow: selectedCells[0]});
            }
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
            var registryValues = this.state.registryValues.slice();
            registryValues[this.state.selectedCellRow][column].value = registryValues[this.state.selectedCellRow][column].value.replace(findValue, replaceValue);        

            //If the cell no longer has the target value, deselect it and move focus to the next selected cell
            if (registryValues[this.state.selectedCellRow][column].value.indexOf(findValue) < 0)
            {
                registryValues[this.state.selectedCellRow][column].selected = false;

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

            this.setState({ registryValues: registryValues});
        }
    }
    _onReplaceAll(findValue, replaceValue, column) {

        if (!this.state.selectedCellRow)
        {
            this._onFindNext(findValue, column);
        }
        else
        {
            var registryValues = this.state.registryValues.slice();
            var selectedCells = this.state.selectedCells.slice();
            var selectedCellRow = this.state.selectedCellRow;

            while (selectedCells.length > 0)
            {
                registryValues[selectedCellRow][column].value = registryValues[this.state.selectedCellRow][column].value.replace(findValue, replaceValue);        

                if (registryValues[selectedCellRow][column].value.indexOf(findValue) < 0)
                {
                    registryValues[selectedCellRow][column].selected = false;

                    var index = selectedCells.indexOf(selectedCellRow);

                    if (index > -1)
                    {
                        selectedCells.splice(index, 1);
                    }
                    else
                    {
                        //something went wrong, so stop the while loop
                        break;
                    }

                    if (selectedCells.length > 0)
                    {
                        selectedCellRow = this._goToNext(selectedCellRow, this.state.selectedCells);
                    }
                }
            }

            this.setState({ selectedCellRow: null});
            this.setState({ selectedCells: [] });
            this.setState({ selectedCellColumn: null });
            this.setState({ registryValues: registryValues});
        }
    }
    _onClearFind(column) {

        var registryValues = this.state.registryValues.slice();

        this.state.selectedCells.map(function (row) {
            registryValues[row][column].selected = false;
        });

        this.setState({ registryValues: registryValues });
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
    _saveRegistry() {

        //TODO: open dialog for device config
        devicesActionCreators.saveRegistry(this.props.device, this.state.registryValues);
        modalActionCreators.openModal(<ConfigDeviceForm device={this.props.device}/>);
    }
    render() {        
        
        var filterPointsTooltip = {
            content: "Filter Points",
            "x": 160,
            "y": 30
        }

        var filterButton = <FilterPointsButton 
                                name={"filterRegistryPoints"}
                                tooltipMsg={filterPointsTooltip}
                                onfilter={this._onFilterBoxChange} 
                                onclear={this._onClearFilter}/>

        var addPointTooltip = {
            content: "Add New Point",
            "x": 160,
            "y": 30
        }

        var addPointButton = <ControlButton 
                                name="addRegistryPoint" 
                                tooltip={addPointTooltip}
                                controlclass="add_point_button"
                                fontAwesomeIcon="plus"
                                clickAction={this._onAddPoint}/>


        var removePointTooltip = {
            content: "Remove Points",
            "x": 160,
            "y": 30
        }

        var removePointsButton = <ControlButton
                                name="removeRegistryPoints" 
                                fontAwesomeIcon="minus"
                                tooltip={removePointTooltip}
                                controlclass="remove_point_button"
                                clickAction={this._onRemovePoints}/>        
        
        var registryRows, registryHeader;
        
        registryRows = this.state.registryValues.map(function (attributesList, rowIndex) {

            var registryCells = [];

            attributesList.forEach(function (item, columnIndex) {

                if (item.keyProp)
                {
                    var selectedStyle = (item.selected ? {backgroundColor: "#F5B49D"} : {});
                    var focusedCell = (this.state.selectedCellColumn === columnIndex && this.state.selectedCellRow === rowIndex ? "focusedCell" : "");

                    var itemCell = (columnIndex === 0 && !item.editable ? 
                                        <td key={item.key + "-" + rowIndex + "-" + columnIndex}><label>{ item.value }</label></td> : 
                                            <td key={item.key + "-" + rowIndex + "-" + columnIndex}><input 
                                                    id={this.state.registryValues[rowIndex][columnIndex].key + "-" + columnIndex + "-" + rowIndex}
                                                    type="text"
                                                    className={focusedCell}
                                                    style={selectedStyle}
                                                    onChange={this._updateCell.bind(this, rowIndex, columnIndex)} 
                                                    value={ this.state.registryValues[rowIndex][columnIndex].value }/>
                                            </td>);

                    registryCells.push(itemCell);
                }
            }, this);

            registryCells.push(
                <td key={"propsButton-" + rowIndex}>
                    <div className="propsButton"
                        onClick={this._showProps.bind(this, attributesList)}>
                        <i className="fa fa-ellipsis-h"></i>
                    </div>
                </td>);

            return ( 
                <tr key={"registry-row-" + rowIndex}>
                    <td key={"checkbox-" + rowIndex}>
                        <input type="checkbox"
                            onChange={this._selectForDelete.bind(this, attributesList)}
                            checked={this.state.pointsToDelete.indexOf(attributesList[0].value) > -1}>
                        </input>
                    </td>
                    { registryCells }                    
                </tr>
            )
        }, this);

        var wideCell = {
            width: "100%"
        }

        registryHeader = this.state.registryHeader.map(function (item, index) {

            var editSelectButton = (<EditSelectButton 
                                        onremove={this._onRemoveColumn}
                                        onadd={this._onAddColumn}
                                        onclone={this._onCloneColumn}
                                        column={index}/>);

            var editColumnButton = (<EditColumnButton 
                                        column={index} 
                                        tooltipMsg="Edit Column"
                                        findnext={this._onFindNext}
                                        replace={this._onReplace}
                                        replaceall={this._onReplaceAll}
                                        // onfilter={this._onFilterBoxChange} 
                                        onclear={this._onClearFind}
                                        onhide={this._removeFocus}/>);

            var firstColumnWidth;

            if (index === 0)
            {
                firstColumnWidth = {
                    width: (item.length * 10) + "px"
                }
            }

            var headerCell = (index === 0 ?
                                ( <th key={"header-" + item + "-" + index} style={firstColumnWidth}>
                                    <div className="th-inner zztop">
                                        { item } { filterButton } { addPointButton } { removePointsButton }
                                    </div>
                                </th>) :
                                ( <th key={"header-" + item + "-" + index}>
                                    <div className="th-inner" style={wideCell}>
                                        { item }
                                        { editSelectButton }
                                        { editColumnButton }
                                    </div>
                                </th> ) );

            return headerCell;
        }, this);        

        var wideDiv = {
            width: "100%",
            textAlign: "center",
            paddingTop: "20px"
        }

        var visibilityClass = ( this.props.device.configuring ? 
                                    "collapsible-registry-values slow-show" : 
                                        "collapsible-registry-values slow-hide" );

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
                clickAction={this._saveRegistry}></ControlButton>
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
            
        return (
            <div className={visibilityClass}>                
                <div className="fixed-table-container"> 
                    <div className="header-background"></div>      
                    <div className="fixed-table-container-inner">    
                        <table className="registryConfigTable">
                            <thead>
                                <tr key="header-values">
                                    <th key="header-checkbox">
                                        <div className="th-inner">
                                            <input type="checkbox"
                                                onChange={this._selectAll}
                                                checked={this.state.allSelected}/>
                                        </div>
                                    </th>
                                    { registryHeader }
                                </tr>
                            </thead>
                            <tbody>                            
                                { registryRows }
                            </tbody>
                        </table>
                    </div>
                </div>
                <div className="registry-buttons" style={wideDiv}>
                    <div className="inlineBlock">
                        {cancelButton}
                    </div>
                    <div className="inlineBlock">
                        {saveButton}
                    </div>                    
                </div>
            </div>
        );
    }
};

function getFilteredPoints(registryValues, filterStr, filterColumn) {

    return registryValues.map(function (row) {
        row.visible = (row[filterColumn].value.trim().toUpperCase().indexOf(filterStr.trim().toUpperCase()) > -1);
    });
}

function getPointsFromStore(device, keyPropsList) {
    return initializeList(devicesStore.getRegistryValues(device), keyPropsList);
}

function getRegistryHeader(registryItem) {
    
    var header = [];

    registryItem.forEach(function (item) {
        if (item.keyProp)
        {
            header.push(item.label);
        }
    });

    return header;
}

function initializeList(registryConfig, keyPropsList)
{
    return registryConfig.map(function (row) {
        row.forEach(function (cell) {
            cell.keyProp = (keyPropsList.indexOf(cell.key) > -1);            
            row.visible = true;
        });

        return row;
    });
}


export default DeviceConfiguration;