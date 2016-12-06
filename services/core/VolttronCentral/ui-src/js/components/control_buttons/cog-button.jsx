'use strict';

var React = require('react');

import ControlButton from './control-button';

var EditColumnButton = require('./edit-columns-button');
// var controlButtonStore = require('../../stores/control-button-store');

var CogButton = React.createClass({
    _onClose: function () {

    },
    _onCloneColumn: function (column) {
        this.props.onclone(column);
    },
    _onAddColumn: function (item) {
        this.props.onadd(item);
    },
    _onRemoveColumn: function (item) {
        this.props.onremove(item);
    },
    render: function () {

        var cogBoxContainer = {
            position: "relative"
        };

        var clearTooltip = {
            content: "Clear Search",
            x: 50,
            y: 0
        }

        var cloneColumnTooltip = {
            content: "Duplicate Column",
            "x": 180,
            "y": 0
        }

        var cloneColumnButton = <ControlButton 
                            name="clonePointColumn" 
                            tooltip={cloneColumnTooltip}
                            fontAwesomeIcon="clone"
                            clickAction={this._onCloneColumn.bind(this, this.props.column)}/>

        var addColumnTooltip = {
            content: "Add New Column",
            "x": 180,
            "y": 0
        }

        var addColumnButton = <ControlButton 
                            name="addPointColumn" 
                            tooltip={addColumnTooltip}
                            fontAwesomeIcon="plus"
                            clickAction={this._onAddColumn.bind(this, this.props.item)}/>


        var removeColumnTooltip = {
            content: "Remove Column",
            "x": 200,
            "y": 0
        }

        var removeColumnButton = <ControlButton 
                            name="removePointColumn" 
                            fontAwesomeIcon="minus"
                            tooltip={removeColumnTooltip}
                            clickAction={this._onRemoveColumn.bind(this, this.props.item)}/> 

        var editColumnButton = <EditColumnButton 
                            name={"searchPointColumns" + this.props.column}
                            column={this.props.column} 
                            tooltipMsg="Edit Column"
                            findnext={this.props.onfindnext}
                            replace={this.props.onreplace}
                            replaceall={this.props.onreplaceall}
                            onfilter={this.props.onfilterboxchange} 
                            onclear={this.props.onclearfind}/>
        

        var cogBox = (
            <div style={cogBoxContainer}>
                { editColumnButton }
                { cloneColumnButton } 
                { addColumnButton } 
                { removeColumnButton }
            </div> 
        );

        var cogTaptip = { 
            "title": "Column Operations", 
            "content": cogBox,
            "x": 100,
            "y": 24,
            "styles": [{"key": "width", "value": "250px"}]
        };
        
        var cogTooltip = {
            "content": "Column Operations",
            "x": 160,
            "y": 0
        };

        var columnIndex = this.props.column;

        return (
            <ControlButton
                name={"cogControlButton" + columnIndex}
                taptip={cogTaptip}
                tooltip={cogTooltip}
                fontAwesomeIcon="cog"
                closeAction={this._onClose}/>
        );
    },
});

module.exports = CogButton;