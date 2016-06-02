'use strict';

var React = require('react');

var ControlButton = require('../control-button');
// var controlButtonStore = require('../../stores/control-button-store');

var FilterPointsButton = React.createClass({
    getInitialState: function () {
        return getStateFromStores();
    },
    // componentDidMount: function () {
    //     controlButtonStore.addChangeListener(this._onStoresChange);
    // },
    // componentWillUnmount: function () {
    //     controlButtonStore.removeChangeListener(this._onStoresChange);
    // },
    // _onStoresChange: function () {

    //     if (controlButtonStore.getClearButton(this.props.name))
    //     {
    //         this.setState({ filterValue: "" });
    //     }
    // },
    _onFilterBoxChange: function (e) {
        var filterValue = e.target.value;

        this.setState({ filterValue: filterValue });

        if (filterValue !== "")
        {
            this.props.onfilter(e.target.value);
        }
        else
        {
            this.props.onclear();
        }
    },
    _onClearFilter: function (e) {
        this.setState({ filterValue: "" });
        this.props.onclear();
    },
    render: function () {

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
                            value={ this.state.filterValue }
                        />
                    </div>
                </div>
            </div> 
        );

        var filterTaptip = { 
            "title": "Filter Points", 
            "content": filterBox,
            "xOffset": 60,
            "yOffset": 120,
            "styles": [{"key": "width", "value": "200px"}]
        };

        var filterIcon = (
            <i className="fa fa-filter"></i>
        );
        
        var holdSelect = this.state.filterValue !== "";

        return (
            <ControlButton 
                name={"filterControlButton"}
                taptip={filterTaptip} 
                tooltip={this.props.tooltipMsg}
                controlclass="filter_button"
                staySelected={holdSelect}
                icon={filterIcon}></ControlButton>
        );
    },
});

function getStateFromStores() {
    return {
        filterValue: ""
    };
}

module.exports = FilterPointsButton;