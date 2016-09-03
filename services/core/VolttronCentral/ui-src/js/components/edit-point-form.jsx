'use strict';

import React from 'react';
import BaseComponent from './base-component';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

class EditPointForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_toggleKeyProp", "_updateAttribute", "_onSubmit");

        this.state = {};
        this.state.attributes = this.props.attributes;
    }
    _toggleKeyProp(itemKey) {

        var itemToUpdate = this.state.attributes.find(function (item) {
            return item.key === itemKey;
        });

        if (itemToUpdate)
        {
            itemToUpdate.keyProp = !itemToUpdate.keyProp;
        }

        this.setState({ attributes: this.state.attributes });
    }
    _updateAttribute(e) {
        var itemKey = e.target.dataset.key;

        var itemToUpdate = this.state.attributes.find(function (item) {
            return item.key === itemKey;
        }); 

        if (itemToUpdate)
        {
            itemToUpdate.value = e.target.value;
        }

        this.setState({ attributes: this.state.attributes });
    }
    _onCancelClick(e) {
        modalActionCreators.closeModal();
    }
    _onSubmit(e) {
        e.preventDefault();
        devicesActionCreators.updateRegistry(this.props.device, this.state.attributes);
        modalActionCreators.closeModal();
    }
    render() {
        
        var attributes = this.state.attributes.map(function (item, index) {

            var itemRow = (
                <tr key={item.key + "-" + index}>
                    <td>{item.label}</td>
                    <td>
                        <input type="text"
                            data-key={item.key}
                            value={item.value}
                            onChange={this._updateAttribute}></input>
                    </td>
                    <td className="centerContent">
                        <input type="checkbox" 
                            checked={item.keyProp} 
                            onChange={this._toggleKeyProp.bind(this, item.key)}></input>
                    </td>
                </tr>
            );

            return itemRow;
        }, this);

        return (
            <form className="edit-registry-form" onSubmit={this._onSubmit}>
                <h1>{attributes[0].value}</h1>
                <table>
                    <thead>
                        <tr>
                            <th>Point</th>
                            <th>Value</th>
                            <th>Show in Table</th>
                        </tr>
                    </thead>
                    <tbody>
                        {attributes}
                    </tbody>
                </table>
                <div className="form__actions">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                    >
                        Cancel
                    </button>
                    <button className="button">
                        Save
                    </button>
                </div>
            </form>
        );
    }
};

export default EditPointForm;
