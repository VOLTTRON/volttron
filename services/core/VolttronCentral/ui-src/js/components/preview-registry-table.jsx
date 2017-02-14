'use strict';

import React from 'react';
import BaseComponent from './base-component';

class PreviewRegistryTable extends BaseComponent {
    constructor(props) {
        super(props);
    }
    shouldComponentUpdate(nextProps, nextState)
    {
        return this.props.csvlayout !== nextProps.csvlayout;
    }
    render() {

        var content;

        if (this.props.csvlayout)
        {
            var attributes = [];

            var headerRow = [];

            this.props.attributes[0].forEach(function (item, index) {
                headerRow.push(item.label);
            });

            attributes.push(<span key={"header-" + this.props.deviceId}>{headerRow.join()}</span>);
            attributes.push(<br key={"br-header-" + this.props.deviceId}/>)

            this.props.attributes.forEach(function (attributeRow, rowIndex) {

                var newRow = [];

                attributeRow.forEach(function (columnCell, columnIndex) {
                    newRow.push(columnCell.value);
                });

                attributes.push(<span key={"row-" + rowIndex + "-" + this.props.deviceId}>{newRow.join()}</span>);
                attributes.push(<br key={"br-" + rowIndex + "-" + this.props.deviceId}/>);
            }, this);

            content = (
                <div className="preview-registry-csv">
                    {attributes}
                </div>
            );
        }
        else
        {
            var headerRow = this.props.attributes[0].map(function (item, index) {
                return (
                    <th key={item.key + "-header-" + index}>
                        {item.label}
                    </th>
                );
            });

            var attributes = this.props.attributes.map(function (attributeRow, rowIndex) {
                var attributeCells = attributeRow.map(function (columnCell, columnIndex) {

                    var cellWidth = {
                        minWidth: (columnCell.value.toString().length * 5) + "px"
                    }

                    return (<td key={columnCell.key + "-cell-" + rowIndex + "-" + columnIndex}
                                style={cellWidth}>
                                {columnCell.value}
                            </td>);
                });

                var registryRow = (
                    <tr key={this.props.deviceId + "-row-" + rowIndex}>
                        {attributeCells}
                    </tr>
                );

                return registryRow;
            }, this);

            content = (
                <table className="preview-registry-table">
                    <thead>
                        <tr>
                            {headerRow}
                        </tr>
                    </thead>
                    <tbody>
                        {attributes}
                    </tbody>
                </table>
            );
        }

        return (
            <div>
                { content }
            </div>
        );
    }
};

export default PreviewRegistryTable;
