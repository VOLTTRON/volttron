'use strict';

import React from 'react';
import BaseComponent from './base-component';

import ControlButton from './control-button';
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

class FilterBox extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onFilterBoxChange', '_onFilterBad', '_onFilterUnknown', '_onFilterOff',
            '_onFilterGood', '_onKeyDown');

		this.state = {};

        this.state.filterValue = "";
        this.state.filterStatus = "";
	}
    _onFilterBoxChange(e) {
        this.setState({ filterValue: e.target.value });
        
        this.setState({ filterStatus: "" });
    }
    _onKeyDown(e) {
        var filterValue = e.target.value;

        if (e.keyCode === 13) //Enter
        {
            platformsPanelActionCreators.loadFilteredItems(e.target.value, "");
        }
    }
    _onFilterGood(e) {
        platformsPanelActionCreators.loadFilteredItems("", "GOOD");
        this.setState({ filterStatus: "GOOD" });
        this.setState({ filterValue: "" });
    }
    _onFilterBad(e) {
        platformsPanelActionCreators.loadFilteredItems("", "BAD");
        this.setState({ filterStatus: "BAD" });
        this.setState({ filterValue: "" });
    }
    _onFilterUnknown(e) {
        platformsPanelActionCreators.loadFilteredItems("", "UNKNOWN");
        this.setState({ filterStatus: "UNKNOWN" });
        this.setState({ filterValue: "" });
    }
    _onFilterOff(e) {
        platformsPanelActionCreators.loadFilteredItems("", "");
        this.setState({ filterValue: "" });
        this.setState({ filterStatus: "" });
    }
    render() {
        
        var filterBoxContainer = {
            textAlign: "left"
        };

        var filterGood, filterBad, filterUnknown;
        filterGood = filterBad = filterUnknown = false;

        switch (this.state.filterStatus)
        {
            case "GOOD":
                filterGood = true;
                break;
            case "BAD":
                filterBad = true;
                break;
            case "UNKNOWN":
                filterUnknown = true;
                break;
        }

        var tooltipX = 80;
        var tooltipY = 240;

        var filterGoodIcon = (
            <div className="status-good">
                <span>&#9654;</span>
            </div>
        );

        var filterGoodTooltip = {
            "content": "Healthy",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        var filterGoodControlButton = (
            <ControlButton 
                name="filterGoodControlButton"
                icon={filterGoodIcon}
                selected={filterGood}
                tooltip={filterGoodTooltip}
                clickAction={this._onFilterGood}></ControlButton>
        );

        var filterBadIcon = (
            <div className="status-bad">
                <i className="fa fa-minus-circle"></i>
            </div>
        );

        var filterBadTooltip = {
            "content": "Unhealthy",
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        var filterBadControlButton = (
            <ControlButton 
                name="filterBadControlButton"
                icon={filterBadIcon}
                selected={filterBad}
                tooltip={filterBadTooltip}
                clickAction={this._onFilterBad}></ControlButton>
        );

        var filterUnknownIcon = (
            <div className="status-unknown moveDown">
                <span>&#9644;</span>
            </div>
        );
        var filterUnknownTooltip = {
            "content": <span>Unknown&nbsp;Status</span>,
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterUnknownControlButton = (
            <ControlButton 
                name="filterUnknownControlButton"
                icon={filterUnknownIcon}
                selected={filterUnknown}
                tooltip={filterUnknownTooltip}
                clickAction={this._onFilterUnknown}></ControlButton>
        );

        var filterOffIcon = (
            <i className="fa fa-ban"></i>
        );
        var filterOffTooltip = {
            "content": <span>Clear&nbsp;Filter</span>,
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };
        var filterOffControlButton = (
            <ControlButton 
                name="filterOffControlButton"
                icon={filterOffIcon}
                tooltip={filterOffTooltip}
                clickAction={this._onFilterOff}></ControlButton>
        );

        return (
            <div className="filter_box" style={filterBoxContainer}>
                <span className="fa fa-search"></span>
                <input
                    type="search"
                    onChange={this._onFilterBoxChange}
                    onKeyDown={this._onKeyDown}
                    value={ this.state.filterValue }
                ></input>
                <div className="inlineBlock">
                    {filterGoodControlButton}
                    {filterBadControlButton}
                    {filterUnknownControlButton}
                    {filterOffControlButton}
                </div>
            </div>
        );
    }
}

export default FilterBox;
