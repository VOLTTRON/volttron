'use strict';

import React from 'react';
import BaseComponent from './base-component';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

class NewColumnForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_onNameChange", "_onCancelClick", "_onSubmit");

        this.state = {
            columnName: "",
            warningMessage: ""
        };
    }
    _onNameChange(evt) {

        if (this.state.warningMessage !== "")
        {
            this.setState({warningMessage: ""});
        }

        var newName = evt.target.value;
        this.setState({columnName: newName});
    }
    _onCancelClick(e) {
        modalActionCreators.closeModal();
    }
    _onSubmit(e) {
        e.preventDefault();

        var alreadyInList = this.props.columnNames.find(function (name) {
            return name === this.state.columnName.toLowerCase().replace(/ /g, "_");
        }, this);

        if (typeof alreadyInList !== "undefined")
        {
            this.setState({warningMessage: "Column names must be unique."});
        }
        else
        {
            this.props.onConfirm(this.state.columnName, this.props.column);
            modalActionCreators.closeModal();
        }
    }
    render() {   

        var warningMessage;

        if (this.state.warningMessage)
        {
            var warningStyle = {
                color: "red",
                textAlign: "center"
            };

            warningMessage = (
                <div style={warningStyle}>{this.state.warningMessage}</div>
            );
        }

        return (
            <form className="new-registry-column-form" onSubmit={this._onSubmit}>
                <div className="centerContent"><h3>New Column</h3></div>
                <div className="newColumnContainer">
                    <div>Column Name: </div>
                    <div><input 
                            type="text"
                            value={this.state.columnName}
                            onChange={this._onNameChange}></input></div>
                </div>
                { warningMessage }
                <div className="form__actions">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                    >
                        Cancel
                    </button>
                    <button 
                        disabled={((this.state.warningMessage) || (!this.state.columnName))}
                        className="button">
                        Add Column
                    </button>
                </div>
            </form>
        );
    }
};

export default NewColumnForm;
