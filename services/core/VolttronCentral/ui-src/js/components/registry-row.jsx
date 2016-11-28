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
        this._bind('_handleRowClick', '_selectForDelete');

        this.state = this._resetState(this.props);  
    }
    componentWillReceiveProps(nextProps)
    {
        if ((!this.props.attributesList.equals(nextProps.attributesList)) || 
            (this.props.allSelected !== nextProps.allSelected))
        {
            var newState = this._resetState(nextProps, (this.props.allSelected !== nextProps.allSelected));
            this.setState(newState);
        }
    }
    shouldComponentUpdate(nextProps, nextState) {
        var doUpdate = false;

        if ((!this.state.attributesList.equals(nextState.attributesList)) || 
            (this.state.selectedForDelete !== nextState.selectedForDelete))
        {
            doUpdate = true;
        }
        else
        {
            doUpdate = (!this.props.immutableProps.equals(nextProps.immutableProps));
        }

        return doUpdate;
    }
    _resetState(props, updateAllSelected) {
        var state = {};

        state.attributesList = props.attributesList;

        state.deviceId = this.props.immutableProps.get("deviceId");
        state.deviceAddress = this.props.immutableProps.get("deviceAddress");
        state.rowIndex = this.props.immutableProps.get("rowIndex");

        state.devicePrefix = "dvc" + state.deviceId + "-" + state.deviceAddress + "-" + state.rowIndex + "-";

        if (updateAllSelected)
        {
            state.selectedForDelete = props.allSelected;
        }
        else
        {
            state.selectedForDelete = false;
        }

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
    _selectForDelete(checked) {
        devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));
        this.setState({selectedForDelete: checked});

        this.props.oncheckselect(this.state.attributesList.getIn(["attributes", 0]).value);
    }
    _handleRowClick(evt){

        if ((evt.target.nodeName !== "INPUT") && 
            (evt.target.nodeName !== "I") && 
            (evt.target.nodeName !== "DIV") &&
            (evt.target.className !== "resize-handle-td"))  
        {

            devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));

            if (!this.state.attributesList.get("selected"))
            {
                var attributesList = this.state.attributesList.set("selected", true);
                this.setState({attributesList: attributesList});
            }
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
        var bottom = innerTable.getClientRects()[0].bottom;
        var height = innerTable.getClientRects()[0].height;

        var view = document.querySelector(".view");
        var viewRect = view.getClientRects();
        var viewBottom = viewRect[0].bottom;

        viewBottom = (bottom > viewBottom ? viewBottom : bottom); 

        var viewTop = viewRect[0].top;

        viewTop = (top > viewTop ? top : viewTop);

        height = (viewBottom < viewTop + height ? viewBottom - viewTop : height);

        columnMoverActionCreators.startColumnMovement(originalClientX, viewTop, height);

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
                var selectedCellStyle = (item.selected ? {backgroundColor: "#F5B49D", width: "100%"} : {width: "100%"});
                var focusedCell = (this.props.immutableProps.get("selectedCellColumn") === columnIndex && this.props.immutableProps.get("selectedCell") ? "focusedCell" : "");

                var itemCell = (!item.editable ? 
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
                                    </td>);

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

        var selectedRowClasses = [];

        if (this.state.attributesList.get("selected"))
        {
            selectedRowClasses.push("selectedRegistryPoint");
        }

        if (this.props.immutableProps.get("keyboardSelected"))
        {
            selectedRowClasses.push("keyboard-selected");
        }

        var visibleStyle = (!this.props.immutableProps.get("filterOn") || this.state.attributesList.get("visible") ? {} : {display: "none"});


        return ( 
            <tr key={"registry-row-" + rowIndex}
                data-row={rowIndex}
                onClickCapture={this._handleRowClick}
                className={selectedRowClasses.join(" ")}
                style={visibleStyle}>
                <td key={"checkbox-" + rowIndex}>
                    <CheckBox
                        controlClass="registryCheckbox"
                        oncheck={this._selectForDelete}
                        selected={this.state.selectedForDelete}>
                    </CheckBox>
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