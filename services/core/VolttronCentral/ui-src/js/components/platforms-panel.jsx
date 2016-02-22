'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var PlatformsPanelItem = require('./platforms-panel-item');


var PlatformsPanel = React.createClass({
    getInitialState: function () {
        var state = {};
        state.platforms = [];     
        state.expanded = getExpandedFromStore();
        state.filterValue = "";
        state.filterStatus = "";

        return state;
    },
    componentWillMount: function () {
        platformsPanelActionCreators.loadPanelPlatforms();
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
        var expanded = getExpandedFromStore();

        this.setState({expanded: expanded});

        if (expanded !== null)
        {
            this.setState({platforms: getPlatformsFromStore()});
        }
    },
    _onPanelItemsStoreChange: function () {
        if (this.state.expanded !== null)
        {
            this.setState({platforms: getPlatformsFromStore()});
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

        var selectedColor = "#ccc";
        var filterGood, filterBad, filterUnknown = {};

        switch (this.state.filterStatus)
        {
            case "GOOD":
                filterGood = {
                    backgroundColor: selectedColor
                }
                break;
            case "BAD":
                filterBad = {
                    backgroundColor: selectedColor
                }
                break;
            case "UNKNOWN":
                filterUnknown = {
                    backgroundColor: selectedColor
                }
                break;
        }

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
                            <div className="control_button status-good"
                                onClick={this._onFilterGood}
                                style={filterGood}>
                                <div className="centeredDiv">
                                    <span>&#9654;</span>
                                </div>
                            </div>
                            <div className="control_button status-bad"
                                onClick={this._onFilterBad}
                                style={filterBad}>
                                <div className="centeredDiv">
                                    <i className="fa fa-minus-circle"></i>
                                </div>
                            </div>
                            <div className="control_button status-unknown"
                                onClick={this._onFilterUnknown}
                                style={filterUnknown}>
                                <div className="centeredDiv">
                                    <span>&#9644;</span>
                                </div>
                            </div>
                            <div className="control_button"
                                onClick={this._onFilterOff}>
                                <div className="centeredDiv">
                                    <i className="fa fa-ban"></i>
                                </div>
                            </div>
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

function getPlatformsFromStore() {
    return platformsPanelItemsStore.getChildren("platforms", null);
};

function getExpandedFromStore() {
    return platformsPanelStore.getExpanded();
};

function getFilteredPlatforms(filterTerm, filterStatus, platforms) {
    return platformsPanelItemsStore.getFilteredItems(filterTerm, filterStatus, platforms);
}


module.exports = PlatformsPanel;
