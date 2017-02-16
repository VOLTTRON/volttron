'use strict';

import React from 'react';
import Router from 'react-router';
import BaseComponent from './base-component';
import PlatformsPanelItem from './platforms-panel-item';
import FilterBox from './filter-box';
import Immutable from 'immutable';

var platformsPanelStore = require('../stores/platforms-panel-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');


class PlatformsPanel extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onPanelStoreChange', '_onPanelItemsStoreChange', '_togglePanel');

        this.state = {};
        this.state.platforms = [];     
        this.state.expanded = platformsPanelStore.getExpanded();
    }
    componentDidMount() {
        platformsPanelStore.addChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.addChangeListener(this._onPanelItemsStoreChange);

        this.exteriorPanel = document.querySelector(".panel-exterior");
        var children = this.exteriorPanel.parentNode.childNodes;
        
        for (var i = 0; i < children.length; i++)
        {
            if (children[i].classList.contains("platform-statuses"))
            {
                this.platformsPanel = children[i];
                break;
            }
        }
    }
    componentWillUnmount() {
        platformsPanelStore.removeChangeListener(this._onPanelStoreChange);
        platformsPanelItemsStore.removeChangeListener(this._onPanelItemsStoreChange);
    }
    _onPanelStoreChange() {
        var expanded = platformsPanelStore.getExpanded();

        if (expanded !== this.state.expanded)
        {
            this.setState({expanded: expanded});
        }        
        
        if (expanded !== null)
        {
            if (expanded === false)
            {
                this.platformsPanel.style.width = "";
                this.exteriorPanel.style.width = "";
            }

            var platformsList = platformsPanelItemsStore.getChildren("platforms", null);
            this.setState({platforms: platformsList});
        }
        else
        {
            this.setState({filterValue: ""});
            this.setState({filterStatus: ""});
            this.platformsPanel.style.width = "";
            this.exteriorPanel.style.width = "";
        }
    }
    _onPanelItemsStoreChange() {
        if (this.state.expanded !== null)
        {
            this.setState({platforms: platformsPanelItemsStore.getChildren("platforms", null)});
        }
    }
    _togglePanel() {
        platformsPanelActionCreators.togglePanel();
    }
    render() {
        var platforms;
        
        var classes = (this.state.expanded === null ? 
                        ["platform-statuses", "platform-collapsed"] : 
                        (this.state.expanded ? 
                            ["platform-statuses", "slow-open", "platform-expanded"] :
                            ["platform-statuses", "slow-shut", "platform-collapsed"])
                        );

        var contentsStyle = { 
            display: (this.state.expanded ? "block" : "none"),
            padding: "0px 0px 20px 10px",
            clear: "right",
            width: "100%"
        };

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
                        <PlatformsPanelItem 
                            key={platform.uuid} 
                            panelItem={platform}
                            itemPath={platform.path}/>
                    );
                });
        }

        return (
            <div className={classes.join(" ")}>
                <div className="extend-panel"
                    onClick={this._togglePanel}>{ this.state.expanded ? '\u25c0' : '\u25b6' }</div>
                <div style={contentsStyle}>
                    <br/>
                    <FilterBox />
                    <ul className="platform-panel-list">
                        {platforms}
                    </ul>
                </div>
            </div>
        );
    }
};


export default PlatformsPanel;
