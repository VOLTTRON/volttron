'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var PlatformsPanelItem = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.expanded = (this.props.panelItem.hasOwnProperty("expanded") ? this.props.panelItem.expanded : null);

        // state.expanded = null;
        state.showTooltip = false;
        state.tooltipX = null;
        state.tooltipY = null;
        state.keepTooltip = false;

        state.children = getChildrenFromStore(this.props.panelItem, this.props.itemPath);

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillMount: function () {
        if (!this.props.hasOwnProperty("children"))
        { 
            platformsPanelActionCreators.loadChildren(this.props.panelItem.type, this.props.panelItem);
        }
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var children = getChildrenFromStore(this.props.panelItem, this.props.itemPath);

        this.setState({children: children});
    },
    _toggleItem: function () {

        if (this.state.children.length > 0)
        {
            this.setState({expanded: !this.state.expanded});
        }
        else
        {
            if (this.props.hasOwnProperty("children"))
            {
                if (this.state.expanded === null)
                {
                    this.setState({expanded: !this.props.panelItem.expanded});
                }
                else
                {
                    this.setState({expanded: !this.state.expanded});
                }
            }
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
        var panelItem = this.props.panelItem;
        var itemPath = this.props.itemPath;

        var items;
        var children;

        var propChildren = this.props.children;
        var filterTerm = this.props.filter;

        var itemClasses;
        var arrowClasses = ["arrowButton", "noRotate"];

        var checkboxClass = "panelItemCheckbox";

        var checkboxStyle = {
            display : (["point"].indexOf(panelItem.type) < 0 ? "none" : "block")
        };

        var tooltipStyle = {
            display: (panelItem.type !== "type" ? (this.state.showTooltip || this.state.keepTooltip ? "block" : "none") : "none"),
            position: "absolute",
            top: this.state.tooltipY + "px",
            left: this.state.tooltipX + "px"
        };

        // var childrenItems = [];

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
        
        if (typeof propChildren !== "undefined" && propChildren !== null)
        {   
            // if (this.state.expanded || (this.state.expanded === null && this.props.panelItem.expanded === true))
            if (this.state.expanded || this.props.panelItem.expanded === true)
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
                            <PlatformsPanelItem panelItem={propChild} itemPath={propChild.path} children={grandchildren}/>
                        );
                    }); 

                if (children.length > 0)
                {
                    // itemClasses = "showItems";

                    var classIndex = arrowClasses.indexOf("noRotate");
                    
                    if (classIndex > -1)
                    {
                        arrowClasses.splice(classIndex, 1);
                    }

                    arrowClasses.push("rotateDown");
                    itemClasses = "showItems";

                    // arrowClasses.push(this.state.expanded ? "rotateDown" : "rotateRight");
                    // itemClasses = (this.state.expanded ? "showItems" : "hideItems");
                     // : "rotateRight");

                    // this.props.panelItem.expanded = this.state.expanded;
                    
                }          
            }
        }
        else
        {
            if (this.state.expanded !== null)
            {                   
                if (this.state.expanded)
                {                
                    if (this.state.children !== null)
                    {
                        // itemClasses = "showItems";

                        var childItems = this.state.children;
                        
                        children = childItems
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
                            .map(function (child) {                            
                                return (
                                    <PlatformsPanelItem panelItem={child} itemPath={child.path}/>
                                );}, this);

                        if (children.length > 0)
                        {
                            itemClasses = "showItems";

                            var classIndex = arrowClasses.indexOf("noRotate");
                            
                            if (classIndex > -1)
                            {
                                arrowClasses.splice(classIndex, 1);
                            }

                            arrowClasses.push("rotateDown");
                             // : "rotateRight");
                        }                            
                    }
                }
                else
                {
                    if (this.state.children) 
                    {
                        itemClasses = "hideItems";

                        arrowClasses.push("rotateRight");
                    }
                }

                // if (children)
                // {
                //     if (children.length > 0)
                //     {
                //         itemClasses = "showItems";

                //         var classIndex = arrowClasses.indexOf("noRotate");
                        
                //         if (classIndex > -1)
                //         {
                //             arrowClasses.splice(classIndex, 1);
                //         }

                //         arrowClasses.push(this.state.expanded ? "rotateDown" : "rotateRight");
                //     }
                // }
            }
        }

        var listItem;

        if (!panelItem.hasOwnProperty("uuid"))
        {
            listItem = 
                <div>
                    <b>
                        {panelItem.name}
                    </b>
                </div>;
        }
        else
        {
            listItem = 
                <div className="platform-link">
                    <Router.Link
                        to="platform"
                        params={{uuid: panelItem.uuid}}
                    >
                    {panelItem.name}
                    </Router.Link>
                </div>;            
        }

        return (
            <li
                key={panelItem.uuid}
                className="panel-item"
            >
                <div className="platform-info">
                    <div className={arrowClasses.join(' ')}
                        onClick={this._toggleItem}>
                        {arrowContent}
                        </div>  
                    <input className={checkboxClass}
                        style={checkboxStyle}
                        type="checkbox"
                        onClick={this._checkItem}></input>                    
                    <div style={tooltipStyle}>
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

// function getChildren(parent, parentPath)
// {
//     return getItemsFromStore(parent, parentPath);
// }


function getChildrenFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getItems(parentItem, parentPath);
}

module.exports = PlatformsPanelItem;
