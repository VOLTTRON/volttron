'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var PlatformsPanel = React.createClass({
    getInitialState: function () {
        var state = getStateFromStores();   
        state.expanded = false;

        // this.expand = false; 

        return state;
    },
    componentWillMount: function () {
        platformsPanelActionCreators.loadPlatformsPanel();
    },
    componentDidMount: function () {
        // platformsPanelStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        // platformsPanelStore.removeChangeListener(this._onStoresChange);
    },
    _expandPanel: function (evt) {
        if (!this.state.expanded)
        {
            this.setState({expanded: true});
        }
        // evt.currentTarget.addEventListener("mouseleave", this._collapsePanel);
    },
    _collapsePanel: function () {
        if (this.state.expanded)
        {
            this.setState({expanded: false});
        }
        
        // evt.currentTarget.addEventListener("mouseenter", this._expandPanel);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var platforms;
        var classes = ["platform-statuses"];

        if (!this.state.platforms) {
            platforms = (
                <p>Loading platforms...</p>
            );
        } else if (!this.state.platforms.length) {
            platforms = (
                <p>No platforms found.</p>
            );
        } else {
            platforms = this.state.platforms
                .sort(function (a, b) {
                    if (a > b) { return 1; }
                    if (a < b) { return -1; }
                    return 0;
                })
                .map(function (platform) {

                    return (
                        <li
                            key={platform.uuid}
                            className="panel-item"
                        >
                            <div>
                                <Router.Link
                                    to="platform"
                                    params={{uuid: platform.uuid}}
                                >
                                    {platform.uuid}
                                </Router.Link>
                            </div>
                            <div>{platform.status}</div>
                        </li>
                    );
                }, this);
        }

        if (this.state.expanded)
        {
            classes.push("slow-open");
        }
        else 
        {
            classes.push("slow-shut");
        }

        return (
            <div className={classes.join(' ')}
                onMouseEnter={this._expandPanel}
                onMouseLeave={this._collapsePanel}>
                <h2>Running ...</h2>
                <ul>
                {platforms}
                </ul>
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platforms: platformsPanelStore.getPlatforms(),
    };
}

module.exports = PlatformsPanel;
