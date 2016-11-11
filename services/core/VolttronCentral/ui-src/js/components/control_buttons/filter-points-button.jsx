'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';

class FilterPointsButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_onFilterBoxChange", "_onKeyDown", "_onClearFilter");

        this.state = getStateFromStores();
    }
    _onFilterBoxChange(e) {
        var filterValue = e.target.value;

        this.setState({ filterValue: filterValue });
    }
    _onKeyDown(e) {

        var filterValue = e.target.value;

        if (e.keyCode === 13) //Enter
        {
            if (filterValue !== "")
            {
                this.props.onfilter(e.target.value, this.props.column);
            }
            else
            {
                this.props.onclear();
            }
        }
    }
    _onClearFilter(e) {
        this.setState({ filterValue: "" });
        this.props.onclear();
    }
    render() {

        var filterBoxContainer = {
            position: "relative"
        };

        var inputStyle = {
            width: "100%",
            marginLeft: "10px",
            fontWeight: "normal"
        }

        var divWidth = {
            width: "85%"
        }

        var clearTooltip = {
            content: "Clear Filter",
            "x": 80,
            "y": 0
        }

        var filterBox = (
            <div style={filterBoxContainer}>
                <ControlButton 
                    fontAwesomeIcon="ban"
                    tooltip={clearTooltip}
                    clickAction={this._onClearFilter}/>
                <div className="inlineBlock">
                    <div className="inlineBlock">
                        <span className="fa fa-filter"></span>
                    </div>
                    <div className="inlineBlock" style={divWidth}>
                        <input
                            type="search"
                            style={inputStyle}
                            onChange={this._onFilterBoxChange}
                            onKeyDown={this._onKeyDown}
                            value={ this.state.filterValue }
                        />
                    </div>
                </div>
            </div> 
        );

        var filterTaptip = { 
            "title": "Filter Points", 
            "content": filterBox,
            "x": 80,
            "y": -150,
            "styles": [{"key": "width", "value": "200px"}]
        };

        var filterIcon = (
            <i className="fa fa-filter"></i>
        );
        
        var holdSelect = this.state.filterValue !== "";

        return (
            <ControlButton 
                name={this.props.name + "-ControlButton"}
                taptip={filterTaptip} 
                tooltip={this.props.tooltipMsg}
                controlclass="filter_button"
                staySelected={holdSelect}
                icon={filterIcon}></ControlButton>
        );
    }
};

function getStateFromStores() {
    return {
        filterValue: ""
    };
}

export default FilterPointsButton;