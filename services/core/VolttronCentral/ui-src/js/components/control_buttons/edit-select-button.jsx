'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';

var EditColumnButton = require('./edit-columns-button');
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');

class EditSelectButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_onCloneColumn", "_onAddColumn", "_onRemoveColumn", "_onEditColumn");

        this.state = {};

        this.state.buttonName = "editSelect-" + this.props.name + "-controlButton";
        this.state.editColumnButton = "editColumn-" + this.props.name + "-controlButton";
    }
    _onClose() {

    }
    _onCloneColumn() {
        this.props.onclone(this.props.column);
        controlButtonActionCreators.hideTaptip(this.state.buttonName);
    }
    _onAddColumn() {
        this.props.onadd(this.props.column);
        controlButtonActionCreators.hideTaptip(this.state.buttonName);
    }
    _onRemoveColumn() {
        this.props.onremove(this.props.column);
        controlButtonActionCreators.hideTaptip(this.state.buttonName);
    }
    _onEditColumn() {
        controlButtonActionCreators.hideTaptip(this.state.buttonName);
        controlButtonActionCreators.toggleTaptip(this.state.editColumnButton);
    }
    render() {

        var editBoxContainer = {
            position: "relative"
        };

        var editBox = (
            <div style={editBoxContainer}>
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

        var editSelectTaptip = { 
            "content": editBox,
            "x": 80,
            "y": -80,
            "styles": [{"key": "width", "value": "120px"}],
            "break": "",
            "padding": "0px"
        };

        var editSelectTooltip = {
            content: "Edit Column",
            "x": 80,
            "y": -60
        }

        return (
            <ControlButton
                name={this.state.buttonName}
                taptip={editSelectTaptip}
                tooltip={editSelectTooltip}
                controlclass="edit_button"
                fontAwesomeIcon="pencil"
                closeAction={this._onClose}/>
        );
    }
};

export default EditSelectButton;