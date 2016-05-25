'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');


var PlatformsPanelItem = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.showTooltip = false;
        state.tooltipX = null;
        state.tooltipY = null;
        state.checked = (this.props.panelItem.hasOwnProperty("checked") ? this.props.panelItem.checked : false);
        state.panelItem = this.props.panelItem;
        state.children = this.props.panelChildren;

        if (this.props.panelItem.type === "platform")
        {
            state.notInitialized = true;
            state.loading = false;
            state.cancelButton = false;
        }

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        var panelItem = platformsPanelItemsStore.getItem(this.props.itemPath);
        var panelChildren = platformsPanelItemsStore.getChildren(this.props.panelItem, this.props.itemPath);

        var loadingComplete = platformsPanelItemsStore.getLoadingComplete(this.props.panelItem);

        if (loadingComplete === true || loadingComplete === null)
        {
            this.setState({panelItem: panelItem});
            this.setState({children: panelChildren});
            this.setState({checked: panelItem.checked});

            if (this.props.panelItem.type === "platform")
            {
                if (loadingComplete === true)
                {
                    this.setState({loading: false});
                    this.setState({notInitialized: false});
                }
                else if (loadingComplete === null)
                {
                    this.setState({loading: false});
                    this.setState({notInitialized: true});
                }
            }
        }
    },
    _expandAll: function () {
        
        platformsPanelActionCreators.expandAll(this.props.itemPath);
    },
    _handleArrowClick: function () {
        
        if (!this.state.loading) // If not loading, treat it as just a regular toggle button
        {
            if (this.state.panelItem.expanded === null && this.state.panelItem.type === "platform") 
            {
                this.setState({loading: true});
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
        }
        else if (this.state.hasOwnProperty("loading")) // it's a platform and it's loading
        {
            if (this.state.loading || this.state.cancelButton) // if either loading or cancelButton is still
            {                                                   // true, either way, the user wants to 
                this.setState({loading: false});                // get out of the loading state, so turn
                this.setState({cancelButton: false});           // the toggle button back to an arrow icon
            }
        }
    },
    _showCancel: function () {

        if (this.state.hasOwnProperty("loading") && (this.state.loading === true))
        {
            this.setState({cancelButton: true});
        }
    },
    _resumeLoad: function () {

        if (this.state.hasOwnProperty("loading"))
        {
            this.setState({cancelButton: false});
        }
    },
    _checkItem: function (e) {

        var checked = e.target.checked;

        platformsPanelActionCreators.checkItem(this.props.itemPath, checked);

        this.setState({checked: checked});

        if (checked)
        {
            platformChartActionCreators.addToChart(this.props.panelItem);
        }
        else
        {
            platformChartActionCreators.removeFromChart(this.props.panelItem);
        }
    },
    _showTooltip: function (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 70});
    },
    _hideTooltip: function () {
        this.setState({showTooltip: false});
    },
    _moveTooltip: function (evt) {
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 70});
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

        var childClass;
        var arrowClasses = [ "arrowButton", "noRotate" ];

        if (this.state.hasOwnProperty("loading"))
        {
            if (this.state.cancelButton)
            {
                arrowClasses.push("cancelLoading");
            }
            else if (this.state.loading)
            {
                arrowClasses.push("loadingSpinner");
            }
        }
        
        var ChartCheckbox;

        if (["point"].indexOf(panelItem.type) > -1)
        {
            ChartCheckbox = (<input className="panelItemCheckbox"
                                    type="checkbox"
                                    onChange={this._checkItem}
                                    checked={this.state.checked}></input>);
        }

        var tooltipStyle = {
            display: (panelItem.type !== "type" ? (this.state.showTooltip ? "block" : "none") : "none"),
            position: "absolute",
            top: this.state.tooltipY + "px",
            left: this.state.tooltipX + "px"
        };

        var toolTipClasses = (this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer");

        if (!this.state.loading)
        {
            arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) );
        }

        var arrowContent;
        var arrowContentStyle = {
            width: "14px"
        }

        if (this.state.cancelButton)
        {
            arrowContent = <span style={arrowContentStyle}><i className="fa fa-remove"></i></span>;
        }
        else if (this.state.loading)
        {
            arrowContent = <span style={arrowContentStyle}><i className="fa fa-circle-o-notch fa-spin fa-fw"></i></span>;
        }
        else if (panelItem.status === "GOOD")
        {
            arrowContent = <span style={arrowContentStyle}>&#9654;</span>;
        } 
        else if (panelItem.status === "BAD") 
        {
            arrowContent = <span style={arrowContentStyle}><i className="fa fa-minus-circle"></i></span>;
        }
        else
        {
            arrowContent = <span style={arrowContentStyle}>&#9644;</span>;
        }
          
        if (this.state.panelItem.expanded === true && propChildren)
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
                childClass = "showItems";                    
            }          
        }

        var itemClasses = [];

        if (!panelItem.hasOwnProperty("uuid"))
        {
            itemClasses.push("item_type");
        }
        else
        {
            itemClasses.push("item_label");
        }

        if (panelItem.type === "platform" && this.state.notInitialized)
        {
            itemClasses.push("not_initialized");
        }

        var listItem = 
                <div className={itemClasses.join(' ')}>
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
                        onClick={this._handleArrowClick}
                        onMouseEnter={this._showCancel}
                        onMouseLeave={this._resumeLoad}>
                        {arrowContent}
                    </div>  
                    {ChartCheckbox}                  
                    <div className={toolTipClasses}
                        style={tooltipStyle}>
                        <div className="tooltip_inner">
                            <div className="opaque_inner">
                                {panelItem.name}:&nbsp;{(panelItem.context ? panelItem.context : panelItem.statusLabel)}
                            </div>
                        </div>
                    </div>
                    <div className="tooltip_target"
                        onMouseEnter={this._showTooltip}
                        onMouseLeave={this._hideTooltip}
                        onMouseMove={this._moveTooltip}>
                        {listItem}
                    </div>
                </div>
                <div className={childClass}>
                    <ul className="platform-panel-list">
                        {children}
                    </ul>
                </div>
            </li>
        );
    },
});

module.exports = PlatformsPanelItem;
