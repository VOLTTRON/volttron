'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var PlatformsPanelItem = require('./platforms-panel-item');
var ControlButton = require('./control-button');


var PlatformsPanel = React.createClass({
    getInitialState: function () {
        var state = {};
        state.platforms = [];     
        state.expanded = platformsPanelStore.getExpanded();
        state.filterValue = "";
        state.filterStatus = "";

        return state;
    },
    componentDidMount: function () {
        platformsPanelStore.addChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.addChangeListener(this._onPanelItemsStoreChange);
    },
    componentWillUnmount: function () {
        platformsPanelStore.removeChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.removeChangeListener(this._onPanelItemsStoreChange);
    },
    _onPanelStoreChange: function () {
        var expanded = platformsPanelStore.getExpanded();

        if (expanded !== this.state.expanded)
        {
            this.setState({expanded: expanded});
        }        
        
        if (expanded !== null)
        {
            var platformsList = platformsPanelItemsStore.getChildren("platforms", null);
            this.setState({platforms: platformsList});
        }
        else
        {
            this.setState({filterValue: ""});
            this.setState({filterStatus: ""});
        }
    },
    _onPanelItemsStoreChange: function () {
        if (this.state.expanded !== null)
        {
            this.setState({platforms: platformsPanelItemsStore.getChildren("platforms", null)});
        }
    },
    _onFilterBoxChange: function (e) {
        this.setState({ filterValue: e.target.value });
        platformsPanelActionCreators.loadFilteredItems(e.target.value, "");
        this.setState({ filterStatus: "" });
    },
    _onFilterGood: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "GOOD");
        this.setState({ filterStatus: "GOOD" });
        this.setState({ filterValue: "" });
    },
    _onFilterBad: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "BAD");
        this.setState({ filterStatus: "BAD" });
        this.setState({ filterValue: "" });
    },
    _onFilterUnknown: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "UNKNOWN");
        this.setState({ filterStatus: "UNKNOWN" });
        this.setState({ filterValue: "" });
    },
    _onFilterOff: function (e) {
        platformsPanelActionCreators.loadFilteredItems("", "");
        this.setState({ filterValue: "" });
        this.setState({ filterStatus: "" });
    },
    _togglePanel: function () {
        platformsPanelActionCreators.togglePanel();
    },
    render: function () {
        var platforms;
        
        var classes = (this.state.expanded === null ? 
                        "platform-statuses platform-collapsed" : 
                        (this.state.expanded ? 
                            "platform-statuses slow-open platform-expanded" :
                            "platform-statuses slow-shut platform-collapsed")
                        );

        var contentsStyle = { 
            display: (this.state.expanded ? "block" : "none"),
            padding: "0px 20px 20px 10px",
            clear: "right",
            width: "100%"
        };

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

        var tooltipX = 60;
        var tooltipY = 190;

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
            <div className="status-unknown">
                <span>&#9644;</span>
            </div>
        );
        var filterUnknownTooltip = {
            "content": "Unknown Status",
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
            "content": "Clear Filter",
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

        if (!this.state.platforms) {
            platforms = (
                <p>Loading platforms panel ...</p>
            );
        } else if (!this.state.platforms.length) {
            platforms = (
                <p>No platforms found.</p>
            );
        } 
        else 
        {            
            platforms = this.state.platforms
                .sort(function (a, b) {
                    if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                    if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                    return 0;
                })
                .map(function (platform) {
                    return (
                        <PlatformsPanelItem panelItem={platform} itemPath={platform.path}/>
                    );
                });
        }

        return (
            <div className={classes}>
                <div className="extend-panel"
                    onClick={this._togglePanel}>{ this.state.expanded ? '\u25c0' : '\u25b6' }</div>
                <div style={contentsStyle}>
                    <br/>
                    <div className="filter_box" style={filterBoxContainer}>
                        <span className="fa fa-search"></span>
                        <input
                            type="search"
                            onChange={this._onFilterBoxChange}
                            value={ this.state.filterValue }
                        />
                        <div className="inlineBlock">
                            {filterGoodControlButton}
                            {filterBadControlButton}
                            {filterUnknownControlButton}
                            {filterOffControlButton}
                        </div>
                    </div>
                    <ul className="platform-panel-list">
                        {platforms}
                    </ul>
                </div>
            </div>
        );
    },
});


module.exports = PlatformsPanel;
