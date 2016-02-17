'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');


var PlatformsPanelItem = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.showTooltip = false;
        state.tooltipX = null;
        state.tooltipY = null;
        state.keepTooltip = false;
        state.checked = false;
        state.panelItem = this.props.panelItem;
        state.children = this.props.panelChildren;

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var panelItem = getItemFromStore(this.props.itemPath);
        var panelChildren = getChildrenFromStore(this.props.panelItem, this.props.itemPath)

        this.setState({panelItem: panelItem});
        this.setState({children: panelChildren});
    },
    _expandAll : function () {
        
        platformsPanelActionCreators.expandAll(this.props.itemPath);
    },
    _toggleItem: function () {

        if (this.state.panelItem.expanded === null)
        {
            platformsPanelActionCreators.loadChildren(this.props.panelItem.type, this.props.panelItem);
        }
        else
        {
            if (this.state.panelItem.expanded)
            {
                platformsPanelActionCreators.expandAll(this.props.itemPath);
            }
            else
            {
                platformsPanelActionCreators.toggleItem(this.props.itemPath);    
            }
        }
    },
    _checkItem: function (e) {

        var checked = e.target.checked;

        this.setState({checked: checked});

        if (checked)
        {
            platformsPanelActionCreators.addToChart(this.props.panelItem);
            window.location = '/#/platform-charts';
        }
        else
        {
            platformsPanelActionCreators.removeFromChart(this.props.panelItem);
        }
    },
    _showTooltip: function (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - 20});
        this.setState({tooltipY: evt.clientY - 70});
    },
    _hideTooltip: function () {
        this.setState({showTooltip: false});
    },
    _moveTooltip: function (evt) {
        this.setState({tooltipX: evt.clientX - 20});
        this.setState({tooltipY: evt.clientY - 70});
    },
    _keepTooltip: function () {
        this.setState({keepTooltip: true});
    },
    _unkeepTooltip: function () {
        this.setState({keepTooltip: false});
    },
    render: function () {
        var panelItem = this.state.panelItem;
        var itemPath = this.props.itemPath;
        var propChildren = this.state.children;
        var children;

        var visibleStyle = {};

        if (panelItem.visible !== true)
        {
            visibleStyle = {
                display: "none"
            }
        }

        var itemClasses;
        var arrowClasses = ["arrowButton", "noRotate"];

        var ChartCheckbox;

        if (["point"].indexOf(panelItem.type) > -1)
        {
            ChartCheckbox = (<input className="panelItemCheckbox"
                                    type="checkbox"
                                    onChange={this._checkItem}></input>);
        }

        var tooltipStyle = {
            display: (panelItem.type !== "type" ? (this.state.showTooltip || this.state.keepTooltip ? "block" : "none") : "none"),
            position: "absolute",
            top: this.state.tooltipY + "px",
            left: this.state.tooltipX + "px"
        };

        arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) );

        var arrowContent;

        if (panelItem.status === "GOOD")
        {
            arrowContent = <span>&#9654;</span>;
        } 
        else if (panelItem.status === "BAD") 
        {
            arrowContent = <i className="fa fa-minus-circle"></i>;
        }
        else
        {
            arrowContent = <span>&#9644;</span>;
        }
          
        if (this.state.panelItem.expanded === true )
        {
            children = propChildren
                .sort(function (a, b) {
                    if (a.name.toUpperCase() > b.name.toUpperCase()) { return 1; }
                    if (a.name.toUpperCase() < b.name.toUpperCase()) { return -1; }
                    return 0;
                })
                .sort(function (a, b) {
                    if (a.sortOrder > b.sortOrder) { return 1; }
                    if (a.sortOrder < b.sortOrder) { return -1; }
                    return 0;
                })
                .map(function (propChild) {
                    
                    var grandchildren = [];
                    propChild.children.forEach(function (childString) {
                        grandchildren.push(propChild[childString]);
                    });

                    return (
                        <PlatformsPanelItem panelItem={propChild} itemPath={propChild.path} panelChildren={grandchildren}/>
                    );
                }); 

            if (children.length > 0)
            {
                var classIndex = arrowClasses.indexOf("noRotate");
                
                if (classIndex > -1)
                {
                    arrowClasses.splice(classIndex, 1);
                }

                arrowClasses.push("rotateDown");
                itemClasses = "showItems";                    
            }          
        }

        var itemClass = (!panelItem.hasOwnProperty("uuid") ? "item_type" : "item_label ");

        var listItem = 
                <div className={itemClass}>
                    {panelItem.name}
                </div>;

        return (
            <li
                key={panelItem.uuid}
                className="panel-item"
                style={visibleStyle}
            >
                <div className="platform-info">
                    <div className={arrowClasses.join(' ')}
                        onDoubleClick={this._expandAll}
                        onClick={this._toggleItem}>
                        {arrowContent}
                    </div>  
                    {ChartCheckbox}
                    <div className="tooltip_outer" 
                        style={tooltipStyle}>
                        <div className="tooltip_inner">
                            {panelItem.uuid}
                        </div>
                        <div className="tooltip_point">
                            &#9654;
                        </div>
                    </div>
                    <div className="tooltip_target"
                        onMouseEnter={this._showTooltip}
                        onMouseLeave={this._hideTooltip}
                        onMouseMove={this._moveTooltip}>
                        {listItem}
                    </div>
                </div>
                <div className={itemClasses}>
                    <ul className="platform-panel-list">
                        {children}
                    </ul>
                </div>
            </li>
        );
    },
});

function getChildrenFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getChildren(parentItem, parentPath);
}

function getItemFromStore(itemPath) {
    return platformsPanelItemsStore.getItem(itemPath);
}

module.exports = PlatformsPanelItem;
