'use strict';

import React from 'react';
import BaseComponent from './base-component';
import EditPointForm from './edit-point-form';
var devicesActionCreators = require('../action-creators/devices-action-creators');
var modalActionCreators = require('../action-creators/modal-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var devicesStore = require('../stores/devices-store');


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
    componentWillReceiveProps(nextProps) {

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
        modalActionCreators.openModal(
            <EditPointForm 
                device={this.props.device} 
                attributes={this.state.attributesList}/>);
    }
    _selectForDelete() {
        
        // var pointsToDelete = this.state.pointsToDelete;

        // var index = pointsToDelete.indexOf(attributesList[0].value);

        // if (index < 0)
        // {
        //     pointsToDelete.push(attributesList[0].value);
        // }
        // else
        // {
        //     pointsToDelete.splice(index, 1);
        // }

        // this.setState({ pointsToDelete: pointsToDelete });

        this.setState({selectedForDelete: !this.state.selectedForDelete})

    }
    _handleRowClick(evt){

        if ((evt.target.nodeName !== "INPUT") && (evt.target.nodeName !== "I") && (evt.target.nodeName !== "DIV"))  
        {
            // var target;

            // if (evt.target.nodeName === "TD")
            // {
            //     target = evt.target.parentNode;
            // }
            // else if (evt.target.parentNode.nodeName === "TD")
            // {
            //     target = evt.target.parentNode.parentNode;
            // }
            // else
            // {
            //     target = evt.target;
            // }

            this.state.attributesList.selected = true;

            this.setState({attributesList: this.state.attributesList});

            // var rowIndex = target.dataset.row;

            // var pointKey = this.state.registryValues[rowIndex].attributes[0].value;
            // var selectedPoints = this.state.selectedPoints;

            // var index = selectedPoints.indexOf(pointKey);
            
            // if (index > -1)
            // {
            //     selectedPoints.splice(index, 1);
            // }
            // else
            // {
            //     selectedPoints.push(pointKey);
            // }

            // this.setState({selectedPoints: selectedPoints});
        }
    }
    render() {        
        
        var registryCells = [];
        var rowIndex = this.props.rowIndex;

        this.props.attributesList.attributes.forEach(function (item, columnIndex) {

            if (item.keyProp)
            {
                var selectedCellStyle = (item.selected ? {backgroundColor: "#F5B49D"} : {});
                var focusedCell = (this.props.selectedCellColumn === columnIndex && this.state.selectedCell ? "focusedCell" : "");

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

        // var selectedRowClass = (this.state.selectedPoints
        //                                     .indexOf(
        //                                         this.state.registryValues[rowIndex]   
        //                                             .attributes[0]
        //                                             .value) > -1 ? 
        //                                     "selectedRegistryPoint" : "");

        var selectedRowClass = (this.state.attributesList.selected ?
                                    "selectedRegistryPoint" : "");

        console.log("row " + rowIndex);

        var visibleStyle = (!this.props.filterOn || attributesList.visible ? {} : {display: "none"});

        return ( 
            <tr key={"registry-row-" + rowIndex}
                data-row={rowIndex}
                onClick={this._handleRowClick}
                className={selectedRowClass}
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