'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var PlatformsPanel = React.createClass({
    getInitialState: function () {
        var state = {};
        state.platforms = getPlatformsFromStore();   
        state.expanded = false;

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
    _togglePanel: function () {
        platformsPanelActionCreators.togglePanel(this.state.expanded);
    },
    render: function () {
        var platforms;
        var classes = (this.state.expanded ? 
                        "platform-statuses slow-open platform-expanded" :
                        "platform-statuses slow-shut platform-collapsed");

        var contentsStyle = { 
            display: (this.state.expanded ? "block" : "none"),
            padding: "0px 20px 20px 10px",
            clear: "right"
        };

        var arrowStyle = {
            float: "left",
            marginRight: "10px",
            color: "#707070",
            cursor: "pointer"
        }

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
                .sort(function (a, b) {
                    if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                    if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                    return 0;
                })
                .map(function (platform) {

                    return (
                        <li
                            key={platform.uuid}
                            className="panel-item"
                        >
                            <div className="platform-info">
                                <div className="arrowButton"
                                    style={arrowStyle}>&#9654;</div>
                                <div className={
                                        ( (platform.status === "GOOD") ? "status-good" :
                                            ( (platform.status === "BAD") ? "status-bad" : 
                                                "status-unknown") )
                                    }>
                                </div>
                                <div className="platform-link">
                                    <Router.Link
                                        to="platform"
                                        params={{uuid: platform.uuid}}
                                    >
                                    {platform.name}
                                    </Router.Link>
                                </div>
                                
                            </div>
                        </li>
                    );
                }, this);
        }

        return (
            <div className={classes}>
                <div className="extend-panel"
                    onClick={this._togglePanel}>{ this.state.expanded ? '\u25c0' : '\u25b6' }</div>
                <div style={contentsStyle}>
                    <h4>Running ...</h4>
                    <ul className="platform-panel-list">
                    {platforms}
                    </ul>
                </div>
            </div>
        );
    },
});

function getPlatformsFromStore() {
    return platformsPanelStore.getPlatforms();
};

function getExpandedFromStore() {
    return platformsPanelStore.getExpanded();
};

module.exports = PlatformsPanel;
