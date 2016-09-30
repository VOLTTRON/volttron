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
        this._bind('_updateCell', '_showProps', '_handleRowClick', '_selectForDelete');

        this.state = this._resetState(this.props);  

        // this.shouldComponentUpdate = PureRenderMixin.shouldComponentUpdate.bind(this);
    }
    componentDidMount() {
        
    }
    componentWillUnmount() {
        
    }
    shouldComponentUpdate(nextProps, nextState) {
        var doUpdate = false;

        // if (objectListsAreDifferent(this.props.attributesList, nextProps.attributesList))
        if (!this.props.attributesList.equals(nextProps.attributesList))
        {
            var newState = this._resetState(nextProps);

            this.setState(newState);
            doUpdate = true;
        }
        else if (!this.state.attributesList.equals(nextState.attributesList))
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
        state.selectedForDelete = false;

        return state;
    }
    _updateCell(column, e) {

        var currentTarget = e.currentTarget;
        var newValues = JSON.parse(JSON.stringify(this.state.attributesList));

        newValues.attributes[column].value = currentTarget.value;

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
        this.setState({selectedForDelete: !this.state.selectedForDelete})

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
    render() {        
        
        var registryCells = [];
        var rowIndex = this.props.immutableProps.get("rowIndex");

        this.state.attributesList.get("attributes").forEach(function (item, columnIndex) {

            if (item.keyProp)
            {
                var selectedCellStyle = (item.selected ? {backgroundColor: "#F5B49D"} : {});
                var focusedCell = (this.props.immutableProps.get("selectedCellColumn") === columnIndex && this.props.immutableProps.get("selectedCell") ? "focusedCell" : "");

                var itemCell = (!item.editable ? 
                                    <td key={item.key + "-" + rowIndex + "-" + columnIndex}><label>{ item.value }</label></td> : 
                                    <td key={item.key + "-" + rowIndex + "-" + columnIndex}><input 
                                        id={this.state.attributesList.get("attributes").get(columnIndex).key + "-" + columnIndex + "-" + rowIndex}
                                        type="text"
                                        className={focusedCell}
                                        style={selectedCellStyle}
                                        onChange={this._updateCell.bind(this, columnIndex)} 
                                        value={ this.state.attributesList.get("attributes").get(columnIndex).value }/>
                                    </td>);

                registryCells.push(itemCell);
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


        console.log("row " + rowIndex);

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