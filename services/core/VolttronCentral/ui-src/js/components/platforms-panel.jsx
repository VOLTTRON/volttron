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
        state.filteredPlatforms = null;   
        state.expanded = getExpandedFromStore();
        state.filterValue = "";

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
        this.setState({ filteredPlatforms: getFilteredPlatforms(e.target.value, "") });
    },
    _onFilterGood: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "GOOD") });
    },
    _onFilterBad: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "BAD") });
    },
    _onFilterUnknown: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "UNKNOWN") });
    },
    _onFilterOff: function (e) {
        this.setState({ filteredPlatforms: getFilteredPlatforms("", "") });
    },
    _togglePanel: function () {
        platformsPanelActionCreators.togglePanel();
    },
    render: function () {
        var platforms;
        var filteredPlatforms = this.state.filteredPlatforms;

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

        var space_right = {
            marginRight: "5px"
        };

        var searchIcon = '\f002' ;

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
            if (filteredPlatforms !== null)
            {
                platforms = filteredPlatforms
                    .sort(function (a, b) {
                        if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                        if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                        return 0;
                    })
                    .map(function (filteredPlatform) {
                        
                        var children = [];
                        filteredPlatform.children.forEach(function (childString) {
                            children.push(filteredPlatform[childString]);
                        });

                        return (
                            <PlatformsPanelItem panelItem={filteredPlatform} itemPath={filteredPlatform.path} children={children}/>
                        );
                });
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
                        <div className="filter_buttons">
                            <div className="filter_button status-good"
                                onClick={this._onFilterGood}>
                                <div className="centeredDiv">
                                    <span>&#9654;</span>
                                </div>
                            </div>
                            <div className="filter_button status-bad"
                                onClick={this._onFilterBad}>
                                <div className="centeredDiv">
                                    <i className="fa fa-minus-circle"></i>
                                </div>
                            </div>
                            <div className="filter_button status-unknown"
                                onClick={this._onFilterUnknown}>
                                <div className="centeredDiv">
                                    <span>&#9644;</span>
                                </div>
                            </div>
                            <div className="filter_button"
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

function getItemsFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getItems(parentItem, parentPath);
};

function getPlatformsFromStore() {
    return platformsPanelItemsStore.getItems("platforms", null);
};

function getExpandedFromStore() {
    return platformsPanelStore.getExpanded();
};

function getFilteredPlatforms(filterTerm, filterStatus) {

    var platformsList = [];

    if (filterTerm !== "" || filterStatus !== "")
    {
        var treeCopy = platformsPanelItemsStore.getTreeCopy();

        var platforms = treeCopy["platforms"];

        for (var key in platforms)
        {
            var filteredPlatform = platformsPanelItemsStore.getFilteredItems(platforms[key], filterTerm, filterStatus);

            if (filteredPlatform)
            {
                if ((filteredPlatform.children.length === 0) && (filteredPlatform.name.indexOf(filterTerm, filterStatus) < 0))
                {
                    filteredPlatform = null;
                }
            }

            if (filteredPlatform)
            {
                platformsList.push(filteredPlatform);
            }
        }
    }
    else
    {
        platformsList = null;
    }

    return platformsList;
}


// function filteredPlatform(platform, filterTerm) {

//     var treeCopy = platformsPanelItemsStore.getTreeCopy();

//     var filteredPlatform = platformsPanelItemsStore.getFilteredItems(treeCopy["platforms"][platform.uuid], filterTerm);


//     if (filteredPlatform)
//     {
//         if ((filteredPlatform.children.length === 0) && (filteredPlatform.name.indexOf(filterTerm) < 0))
//         {
//             filteredPlatform = null;
//         }
//     }

//     return filteredPlatform;
// };

module.exports = PlatformsPanel;
