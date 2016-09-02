'use strict';

var React = require('react');

var ControlButton = require('../control-button');
var EditColumnButton = require('./edit-columns-button');
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');
// var controlButtonStore = require('../../stores/control-button-store');

var EditSelectButton = React.createClass({
    componentDidMount: function () {
        // this.opSelector = document.getElementsByClassName("opSelector")[0];
        // this.opSelector.selectedIndex = -1;
    },
    componentDidUpdate: function () {
    },
    _onClose: function () {

    },
    _onCloneColumn: function () {
        this.props.onclone(this.props.column);
        controlButtonActionCreators.hideTaptip("editSelectButton" + this.props.column);
    },
    _onAddColumn: function () {
        this.props.onadd(this.props.column);
        controlButtonActionCreators.hideTaptip("editSelectButton" + this.props.column);
    },
    _onRemoveColumn: function () {
        this.props.onremove(this.props.column);
        controlButtonActionCreators.hideTaptip("editSelectButton" + this.props.column);
    },
    _onEditColumn: function () {
        controlButtonActionCreators.hideTaptip("editSelectButton" + this.props.column);
        controlButtonActionCreators.toggleTaptip("editControlButton" + this.props.column);
    },
    render: function () {

        var cogBoxContainer = {
            position: "relative"
        };

        var cogBox = (
            <div style={cogBoxContainer}>
                <ul
                    className="opList">
                    <li 
                        className="opListItem edit"
                        onClick={this._onEditColumn}>Find and Replace</li>
                    <li 
                        className="opListItem clone"
                        onClick={this._onCloneColumn}>Duplicate</li>
                    <li 
                        className="opListItem add"
                        onClick={this._onAddColumn}>Add</li>
                    <li 
                        className="opListItem remove"
                        onClick={this._onRemoveColumn}>Remove</li>
                </ul>
            </div> 
        );

        var cogTaptip = { 
            "content": cogBox,
            "x": 100,
            "y": 24,
            "styles": [{"key": "width", "value": "120px"}],
            "break": "",
            "padding": "0px"
        };

        var columnIndex = this.props.column;

        var cogIcon = (<i className={"fa fa-cog "}></i>);

        return (
            <ControlButton
                name={"editSelectButton" + columnIndex}
                taptip={cogTaptip}
                controlclass="cog_button"
                fontAwesomeIcon="pencil"
                closeAction={this._onClose}/>
        );
    },
});

module.exports = EditSelectButton;