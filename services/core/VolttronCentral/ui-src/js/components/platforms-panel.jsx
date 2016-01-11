'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var PlatformsPanelItem = require('./platforms-panel-item');
var platformsPanelAgentStore = require('../stores/platforms-panel-agent-store');


var PlatformsPanel = React.createClass({
    getInitialState: function () {
        var state = {};
        state.platforms = getPlatformsFromStore();   
        state.expanded = getExpandedFromStore();
        state.filterValue = "";

        return state;
    },
    componentDidMount: function () {
        platformsPanelStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsPanelStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState({platforms: getPlatformsFromStore()});
        this.setState({expanded: getExpandedFromStore()});
    },
    _onFilterBoxChange: function (e) {
        this.setState({ filterValue: e.target.value });
    },
    _filterItems: function (e) {

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
            textAlign: "center"
        };

        var filterTerm = this.state.filterValue;

        if (!this.state.platforms) {
            platforms = (
                <p>Loading platforms panel ...</p>
            );
        } else if (!this.state.platforms.length) {
            platforms = (
                <p>No platforms found.</p>
            );
        } else {
            platforms = this.state.platforms
                .filter(function (platform) {
                    return ((platform.name.indexOf(this) > -1) || (this === "") || filteredChildren(platform, this).length > 0);
                }, filterTerm)                
                .sort(function (a, b) {
                    if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                    if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                    return 0;
                })
                .map(function (platform) {

                    return (

                        <PlatformsPanelItem panelItem={platform} itemPath={platform.path} children={filteredChildren(platform, filterTerm)} filter={filterTerm}/>
                        
                    );
                }, this);
        }

        return (
            <div className={classes}>
                <div className="extend-panel"
                    onClick={this._togglePanel}>{ this.state.expanded ? '\u25c0' : '\u25b6' }</div>
                <div style={contentsStyle}>
                    <br/>
                    <div style={filterBoxContainer}>
                        <input
                            className="filter_box"
                            type="text"
                            onChange={this._onFilterBoxChange}
                            value={this.state.filterValue}
                        />
                        <input
                            className="filter_button"
                            type="button"
                            onClick={this._filterItems}
                        />
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
    return platformsPanelItemsStore.getItems("platforms", null);
};

function getExpandedFromStore() {
    return platformsPanelStore.getExpanded();
};

function filteredChildren(platform, filterTerm) {

    // if (filterTerm !== "")
    // {
    //     var itemsList = [];

    //     for (var key in platform.children)
    //     {
    //         var items = platformsPanelItemsStore.getFilteredItems(platform);
    //     }
        

    //     return {"agents": agents.filter(function (agent) {
    //         return (agent.name.indexOf(this) > -1);
    //     }, filterTerm)};
    // }
    // else
    // {
    //     return [];
    // } 

    return [];
    
};

module.exports = PlatformsPanel;
