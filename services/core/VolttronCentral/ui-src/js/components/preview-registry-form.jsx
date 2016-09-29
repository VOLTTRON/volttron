'use strict';

import React from 'react';
import BaseComponent from './base-component';

var modalActionCreators = require('../action-creators/modal-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');

class PreviewRegistryForm extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_toggleLayout", "_updateFileName", "_onSubmit");

        this.state = {};
        this.state.csvlayout = true;
        this.state.fileName = "";
    }
    _toggleLayout(itemKey) {

        this.setState({ csvlayout: !this.state.csvlayout });
    }
    _updateFileName(e) {

        this.setState({ fileName: e.target.value})
    }
    _onCancelClick(e) {
        modalActionCreators.closeModal();
    }
    _onSubmit(e) {
        e.preventDefault();
        modalActionCreators.closeModal();
        this.props.onsaveregistry();
    }
    render() {

        var content;

        var layoutToggle;

        if (this.state.csvlayout)
        {
            layoutToggle = (

                        <div className="displayBlock">
                            <div className="inlineBlock">csv</div>&nbsp;/&nbsp;
                            <div className="form__link inlineBlock"
                                onClick={this._toggleLayout}>
                                <a>table</a>
                            </div>
                        </div>);

            var attributes = [];

            this.props.attributes[0].forEach(function (item, index) {

                attributes.push(
                    <span key={item.key + "-header-" + index}>
                        {item.label}
                    </span>
                );

                if (index < this.props.attributes[0].length -1)
                {
                    attributes.push(<span key={"comma-header-" + index}>,</span>)
                }

            }, this);

            attributes.push(<br key={"br-header-" + this.props.device.id}/>)

            this.props.attributes.forEach(function (attributeRow, rowIndex) {

                attributeRow.forEach(function (columnCell, columnIndex) {

                    attributes.push(
                            <span key={columnCell.key + "-cell-" + rowIndex + "-" + columnIndex}>
                                {columnCell.value}
                            </span>);

                    if (columnIndex < attributeRow.length -1)
                    {
                        attributes.push(<span key={"comma-" + rowIndex + "-" + columnIndex}>,</span>)
                    }
                });

                attributes.push(<br key={"br-" + rowIndex}/>);
            });

            content = (<div>
                            {attributes}
                        </div>);
        }
        else
        {
            layoutToggle = (
                        <div className="displayBlock">
                            <div className="form__link inlineBlock"
                                onClick={this._toggleLayout}>
                                <a>csv</a>
                            </div>&nbsp;/&nbsp;
                            <div className="inlineBlock">table</div>
                        </div>);

            var headerRow = this.props.attributes[0].map(function (item, index) {

                return (
                    <th key={item.key + "-header-" + index}>
                        {item.label}
                    </th>
                );

            });

            var attributes = this.props.attributes.map(function (attributeRow, rowIndex) {

                var attributeCells = attributeRow.map(function (columnCell, columnIndex) {

                    return (<td key={columnCell.key + "-cell-" + rowIndex + "-" + columnIndex}>
                                {columnCell.value}
                            </td>);
                });

                var registryRow = (
                    <tr key={this.props.device.id + "-row-" + rowIndex}>
                        {attributeCells}
                    </tr>
                );

                return registryRow;
            }, this);


            content = (<table>
                            <thead>
                                <tr>
                                    {headerRow}
                                </tr>
                            </thead>
                            <tbody>
                                {attributes}
                            </tbody>
                        </table>);
        }

        return (
            <form className="preview-registry-form" onSubmit={this._onSubmit}>
                <h1>Save this registry configuration?</h1>
                <h4>{this.props.device.address} / {this.props.device.name} / {this.props.device.id}</h4>
                { layoutToggle }
                { content }

                <br/>
                <div className="displayBlock">
                    <div className="inlineBlock">CSV File Name: </div>
                    &nbsp;
                    <div className="inlineBlock">
                        <input 
                            onChange={this._updateFileName}
                            value={this.state.fileName}
                            type="text">
                        </input>
                    </div>
                </div>
                <div className="form__actions">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                    >
                        Cancel
                    </button>
                    <button 
                        className="button"
                        disabled={this.state.fileName === ""}>
                        Save
                    </button>
                </div>
            </form>
        );
    }
};

export default PreviewRegistryForm;
