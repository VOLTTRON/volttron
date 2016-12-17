'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';

var EditColumnButton = require('./edit-columns-button');
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');

class EditSelectButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_handleAction");

        this.state = {
            buttonName: "editSelect-" + this.props.name + "-controlButton"
        };
    }
    _handleAction(callback, evt) {
        
        if (typeof callback === "function")
        {
            callback(this, evt.target);    
        }

        controlButtonActionCreators.hideTaptip(this.state.buttonName);
    }
    render() {

        var editBoxContainer = {
            position: "relative"
        };

        var listItems = this.props.listItems.map(function (listItem, index) {
            return (
                <li key={"li-" + listItem.label + "-" + index}
                    className={"opListItem " + listItem.position}
                    onClick={this._handleAction.bind(this, listItem.action)}>{listItem.label}</li>
            )
        }, this);

        var editBox = (
            <div style={editBoxContainer}>
                <ul
                    className="opList">
                    {listItems}
                </ul>
            </div> 
        );

        var editSelectTaptip = { 
            "content": editBox,
            "styles": [{"key": "width", "value": "120px"}],
            "break": "",
            "padding": "0px"
        };

        if (this.props.taptip.hasOwnProperty("taptipX"))
        {
            editSelectTaptip.x = this.props.taptip.taptipX;
        }
        else if (this.props.taptip.hasOwnProperty("xOffset"))
        {
            editSelectTaptip.xOffset = this.props.taptip.xOffset;
        } 

        if (this.props.taptip.hasOwnProperty("taptipY"))
        {
            editSelectTaptip.y = this.props.taptip.taptipY;
        }
        else if (this.props.taptip.hasOwnProperty("yOffset"))
        {
            editSelectTaptip.yOffset = this.props.taptip.yOffset;
        } 

        var editSelectTooltip;

        if (this.props.hasOwnProperty("tooltip"))
        {
            editSelectTooltip = {
                content: this.props.tooltip.content
            }

            if (this.props.tooltip.hasOwnProperty("tooltipX"))
            {
                editSelectTooltip.x = this.props.tooltip.tooltipX;
            }
            else if (this.props.tooltip.hasOwnProperty("xOffset"))
            {
                editSelectTooltip.xOffset = this.props.tooltip.xOffset;
            } 

            if (this.props.tooltip.hasOwnProperty("tooltipY"))
            {
                editSelectTooltip.y = this.props.tooltip.tooltipY;
            }
            else if (this.props.tooltip.hasOwnProperty("yOffset"))
            {
                editSelectTooltip.yOffset = this.props.tooltip.yOffset;
            }   
        } 

        return (
            <ControlButton
                name={this.state.buttonName}
                taptip={editSelectTaptip}
                tooltip={editSelectTooltip}
                controlclass={this.props.buttonClass}
                nocentering={this.props.hasOwnProperty("nocentering") ? this.props.nocentering : false}
                floatleft={this.props.hasOwnProperty("floatleft") ? this.props.floatleft : false}
                fontAwesomeIcon={this.props.iconName}/>
        );
    }
};

export default EditSelectButton;