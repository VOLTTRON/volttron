'use strict';

import React from 'react';
import BaseComponent from './base-component';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import EditPointForm from './edit-point-form';
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');

var registryWs, registryWebsocket;
class RegistryRow extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_updateCell', '_showProps', '_handleRowClick', '_selectForDelete', '_grabResizeHandle');

        this.state = this._resetState(this.props);  

        // this.shouldComponentUpdate = PureRenderMixin.shouldComponentUpdate.bind(this);
    }
    componentDidMount() {
    }
    componentWillUnmount() {
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
            console.log("state's not equal");
        }
        else
        {
            doUpdate = (!this.props.immutableProps.equals(nextProps.immutableProps));

            if (doUpdate)
            {
                console.log("immutable props not equal");
            }
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
        
        var newValues = this.state.attributesList.updateIn(["attributes", column, "value"], function (item) {

            return currentTarget.value;
        });

        this.setState({ attributesList: newValues });
    }
    _showProps(attributesList) {
        
        devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));

        modalActionCreators.openModal(
            <EditPointForm 
                deviceId={this.props.immutableProps.get("deviceId")} 
                deviceAddress={this.props.immutableProps.get("deviceAddress")}
                attributes={this.state.attributesList.get("attributes")}/>);
    }
    _selectForDelete() {
        devicesActionCreators.focusOnDevice(this.props.immutableProps.get("deviceId"), this.props.immutableProps.get("deviceAddress"));
        this.setState({selectedForDelete: !this.state.selectedForDelete});

        this.props.oncheckselect(this.state.attributesList.getIn(["attributes", 0]).value);
    }
    _handleRowClick(evt){

        if ((evt.target.nodeName !== "INPUT") && (evt.target.nodeName !== "I") && (evt.target.nodeName !== "DIV"))  
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
        var target = evt.target;

        var targetColumn = this.refs[this.state.devicePrefix + columnIndex];        

        var onMouseMove = function (evt)
        {            
            // console.log(evt.clientX);
        };                    

        var onMouseUp = function (evt)
        {
            var clientRect = targetColumn.getClientRects();

            var targetWidth = evt.clientX - clientRect[0].left;

            this.props.onresizecolumn(columnIndex, targetWidth + "px");

            document.removeEventListener("mousemove", onMouseMove);
            document.removeEventListener("mouseup", onMouseUp);

            
        }.bind(this);                  

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);

        evt.preventDefault();
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
                        <td 
                            className="resize-handle-td"
                            onMouseDown={this._grabResizeHandle.bind(this, columnIndex)}></td>
                    );
                    registryCells.push(resizeHandle);
                }
            }
        }, this);

        registryCells.push(
            <td key={"propsButton-" + rowIndex}>
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


        console.log("row " + rowIndex + " visible is " + this.state.attributesList.get("visible"));

        var visibleStyle = (!this.props.immutableProps.get("filterOn") || this.state.attributesList.get("visible") ? {} : {display: "none"});


        return ( 
            <tr key={"registry-row-" + rowIndex}
                data-row={rowIndex}
                onClick={this._handleRowClick}
                className={selectedRowClasses.join(" ")}
                style={visibleStyle}>
                <td key={"checkbox-" + rowIndex}>
                    <input type="checkbox"
                        onChange={this._selectForDelete}
                        checked={this.state.selectedForDelete}>
                    </input>
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