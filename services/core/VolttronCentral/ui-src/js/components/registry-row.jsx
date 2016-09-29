'use strict';

import React from 'react';
import BaseComponent from './base-component';
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
    }
    componentDidMount() {
        
    }
    componentWillUnmount() {
        
    }
    shouldComponentUpdate(nextProps, nextState) {
        var doUpdate = false;

        if (objectListsAreDifferent(this.props.attributesList, nextProps.attributesList))
        {
            var newState = this._resetState(nextProps);

            this.setState(newState);
            doUpdate = true;
        }
        else
        {
            doUpdate = ((this.props.rowIndex !== nextProps.rowIndex) ||
                (this.props.selectedCell !== nextProps.selectedCell) ||
                (this.props.selectedCellColumn !== nextProps.selectedCellColumn) ||
                (this.props.filterOn !== nextProps.filterOn) ||
                (this.props.keyboardSelected !== nextProps.keyboardSelected))
        }

        if (!doUpdate)
        {
            doUpdate = this.state.attributesList.selected !== nextState.attributesList.selected;
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
        
        devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);

        modalActionCreators.openModal(
            <EditPointForm 
                device={this.props.device} 
                attributes={this.state.attributesList.attributes}/>);
    }
    _selectForDelete() {
        devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);
        this.setState({selectedForDelete: !this.state.selectedForDelete})

    }
    _handleRowClick(evt){

        if ((evt.target.nodeName !== "INPUT") && (evt.target.nodeName !== "I") && (evt.target.nodeName !== "DIV"))  
        {
            devicesActionCreators.focusOnDevice(this.props.device.id, this.props.device.address);

            if (!this.state.attributesList.selected)
            {
                this.state.attributesList.selected = true;
                this.setState({attributesList: this.state.attributesList});
            }
        }
    }
    render() {        
        
        var registryCells = [];
        var rowIndex = this.props.rowIndex;

        this.state.attributesList.attributes.forEach(function (item, columnIndex) {

            if (item.keyProp)
            {
                var selectedCellStyle = (item.selected ? {backgroundColor: "#F5B49D"} : {});
                var focusedCell = (this.props.selectedCellColumn === columnIndex && this.props.selectedCell ? "focusedCell" : "");

                var itemCell = (!item.editable ? 
                                    <td key={item.key + "-" + rowIndex + "-" + columnIndex}><label>{ item.value }</label></td> : 
                                    <td key={item.key + "-" + rowIndex + "-" + columnIndex}><input 
                                        id={this.state.attributesList.attributes[columnIndex].key + "-" + columnIndex + "-" + rowIndex}
                                        type="text"
                                        className={focusedCell}
                                        style={selectedCellStyle}
                                        onChange={this._updateCell.bind(this, columnIndex)} 
                                        value={ this.state.attributesList.attributes[columnIndex].value }/>
                                    </td>);

                registryCells.push(itemCell);
            }
        }, this);

        registryCells.push(
            <td key={"propsButton-" + rowIndex}>
                <div className="propsButton"
                    onClick={this._showProps.bind(this, this.state.attributesList.attributes)}>
                    <i className="fa fa-ellipsis-h"></i>
                </div>
            </td>);

        var selectedRowClasses = [];

        if (this.state.attributesList.selected)
        {
            selectedRowClasses.push("selectedRegistryPoint");
        }

        if (this.props.keyboardSelected)
        {
            selectedRowClasses.push("keyboard-selected");
        }


        console.log("row " + rowIndex);

        var visibleStyle = (!this.props.filterOn || attributesList.visible ? {} : {display: "none"});

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


function objectListsAreDifferent(listA, listB)
{
    var diff = false;

    if (listA.length !== listB.length)
    {
        diff = true;
    }
    else 
    {
        for (var i = 0; i < listA.length; i++)
        {
            for (var key in listA[i])
            {
                if (!listB[i].hasOwnProperty(key))
                {
                    diff = true;
                    break;
                }
                else
                {
                    if (listA[i][key] !== listB[i][key])
                    {
                        diff = true;
                        break;
                    }
                }
            }    
        }
    }

    return diff;
}


function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

export default RegistryRow;