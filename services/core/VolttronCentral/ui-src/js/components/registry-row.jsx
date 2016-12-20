'use strict';

import React from 'react';
import BaseComponent from './base-component';
import EditPointForm from './edit-point-form';
import CheckBox from './check-box';
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var columnMoverActionCreators = require('../action-creators/column-mover-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');
import Immutable from 'immutable';

class RegistryRow extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_handleRowClick', '_clickCheckbox');

        this.state = this._resetState(this.props);  
    }
    componentWillReceiveProps(nextProps)
    {
        if (this.props.attributesList !== nextProps.attributesList)
        {
            var newState = this._resetState(nextProps);
            this.setState(newState);
        }
    }
    shouldComponentUpdate(nextProps, nextState) {
        var doUpdate = false;

        if (this.state.attributesList !== nextState.attributesList)
        {
            doUpdate = true;
        }
        else
        {
            doUpdate = (!this.props.immutableProps.equals(nextProps.immutableProps));
        }

        return doUpdate;
    }
    _resetState(props) {
        var state = {};

        state.attributesList = props.attributesList;

        state.deviceId = this.props.immutableProps.get("deviceId");
        state.deviceAddress = this.props.immutableProps.get("deviceAddress");
        state.rowIndex = this.props.immutableProps.get("rowIndex");

        state.devicePrefix = "dvc" + state.deviceId + "-" + state.deviceAddress + "-" + state.rowIndex + "-";

        return state;
    }
    _updateCell(column, e) {

        var currentTarget = e.currentTarget;
        
        var newValues = this.state.attributesList.updateIn(["attributes", column], function (item) {

            item.value = currentTarget.value;

            return item;
        });

        this.setState({ attributesList: newValues });
        this.forceUpdate();

    }
    _showProps(attributesList) {
        
        devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));

        modalActionCreators.openModal(
            <EditPointForm 
                deviceId={this.props.immutableProps.get("deviceId")} 
                deviceAddress={this.props.immutableProps.get("deviceAddress")}
                attributes={this.state.attributesList.get("attributes")}/>);
    }
    _clickCheckbox(checked) {
        devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));
        this.props.oncheckselect(this.props.immutableProps.get("rowIndex"));
    }
    _handleRowClick(evt){

        if ((evt.target.nodeName !== "INPUT") && 
            (evt.target.nodeName !== "I") && 
            (evt.target.nodeName !== "DIV") &&
            (evt.target.className !== "resize-handle-td"))  
        {

            devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));

            this.props.oncheckselect(this.props.immutableProps.get("rowIndex"));
        }
    }
    _grabResizeHandle(columnIndex, evt) {
        
        evt.stopPropagation();
        evt.nativeEvent.stopImmediatePropagation();

        var targetColumn = this.refs[this.state.devicePrefix + columnIndex];

        var originalClientX = evt.clientX;
        var clientRect = targetColumn.getClientRects();
        var originalTargetWidth = clientRect[0].width;

        var innerTable = this.props.ongetparentnode();

        var top = innerTable.getClientRects()[0].top;
        var height = innerTable.getClientRects()[0].height;

        columnMoverActionCreators.startColumnMovement(originalClientX, top, height);

        this.props.oninitializetable();

        var onMouseMove = function (evt)
        {            
            var movement = evt.clientX - originalClientX;
            columnMoverActionCreators.moveColumn(movement);

        }.bind(this);                    

        var onMouseUp = function (evt)
        {
            document.removeEventListener("mousemove", onMouseMove);
            document.removeEventListener("mouseup", onMouseUp);  

            columnMoverActionCreators.endColumnMovement();

            var movement = evt.clientX - originalClientX;
            var targetWidth = originalTargetWidth + movement;
            this.props.onresizecolumn(columnIndex, targetWidth + "px", movement);

        }.bind(this); 

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
    }
    render() {        
        
        var registryCells = [];
        var rowIndex = this.props.immutableProps.get("rowIndex");

        this.state.attributesList.get("attributes").forEach(function (item, columnIndex) {

            if (item.keyProp)
            {
                var selectedCellStyle = (item.selected ? {backgroundColor: "rgba(187, 137, 102, 0.6)", width: "100%"} : {width: "100%"});
                var focusedCell = (this.props.immutableProps.get("selectedCellColumn") === columnIndex && this.props.immutableProps.get("selectedCell") ? "focusedCell" : "");

                var itemCell = (
                    !item.editable ? 
                        <td key={item.key + "-" + rowIndex + "-" + columnIndex}
                            ref={this.state.devicePrefix + columnIndex}>
                            <label>{ item.value }</label>
                        </td> : 
                            <td key={item.key + "-" + rowIndex + "-" + columnIndex}
                                ref={this.state.devicePrefix + columnIndex}>
                                <input 
                                    id={this.state.attributesList.get("attributes").get(columnIndex).key + "-" + columnIndex + "-" + rowIndex}
                                    type="text"
                                    className={focusedCell}
                                    style={selectedCellStyle}
                                    onChange={this._updateCell.bind(this, columnIndex)} 
                                    value={ this.state.attributesList.get("attributes").get(columnIndex).value }/>
                            </td>
                );

                registryCells.push(itemCell);

                if ((columnIndex + 1) < this.state.attributesList.get("attributes").size)
                {
                    var resizeHandle = (
                        <td key={"resize-" + rowIndex + "-" + columnIndex}
                            className="resize-handle-td"
                            onMouseDown={this._grabResizeHandle.bind(this, columnIndex)}></td>
                    );
                    registryCells.push(resizeHandle);
                }
            }
        }, this);

        var propsButtonStyle = {
            width: "10px"
        }

        registryCells.push(
            <td key={"propsButton-" + rowIndex} style={propsButtonStyle}>
                <div className="propsButton"
                    onClick={this._showProps.bind(this, this.state.attributesList.get("attributes"))}>
                    <i className="fa fa-ellipsis-h"></i>
                </div>
            </td>);

        var rowClasses = ["registry-row"];

        if (this.props.immutableProps.get("keyboardSelected"))
        {
            rowClasses.push("keyboard-selected");
        }

        if (this.state.attributesList.get("alreadyUsed"))
        {
            rowClasses.push("already-used-point");
        }

        var visibleStyle = (!this.props.immutableProps.get("filterOn") || this.state.attributesList.get("visible") ? {} : {display: "none"});

        return ( 
            <tr key={"registry-row-" + rowIndex}
                data-row={rowIndex}
                onClickCapture={this._handleRowClick}
                className={rowClasses.join(" ")}
                style={visibleStyle}>
                <td key={"checkbox-" + rowIndex}>
                    <div className="centerContent flexContent">
                        <CheckBox
                            controlClass="registryCheckbox flexChild"
                            oncheck={this._clickCheckbox}
                            selected={this.props.immutableProps.get("selectedRow")}>
                        </CheckBox>
                    </div>
                </td>
                { registryCells }                    
            </tr>
        );
    }
};


function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

export default RegistryRow;