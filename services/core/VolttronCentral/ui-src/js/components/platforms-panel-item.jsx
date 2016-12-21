'use strict';

import React from 'react';
import Router from 'react-router';
import BaseComponent from './base-component';
import ControlButton from './control-button';
import EditSelectButton from './control_buttons/edit-select-button';
import CheckBox from './check-box';
import Immutable from 'immutable';

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsStore = require('../stores/platforms-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');
var devicesActionCreators = require('../action-creators/devices-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var wspubsub = require('../lib/wspubsub');
var authorizationStore = require('../stores/authorization-store');


class PlatformsPanelItem extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange', '_expandAll', '_handleArrowClick', '_showCancel', 
            '_resumeLoad', '_checkItem', '_showTooltip', '_hideTooltip', '_moveTooltip',
            '_onAddDevices', '_onDeviceMethodChange', '_onDeviceConfig');

        this.state = {};
        
        this.state.showTooltip = false;
        this.state.tooltipX = null;
        this.state.tooltipY = null;
        this.state.checked = (typeof this.props.panelItem.get("checked") !== "undefined" ? this.props.panelItem.get("checked") : false);
        this.state.panelItem = this.props.panelItem;
        this.state.children = Immutable.fromJS(this.props.panelChildren);

        if (this.props.panelItem.get("type") === "platform")
        {
            this.state.notInitialized = true;
            this.state.loading = false;
            this.state.cancelButton = false;            
        }
    }

    managmentMessage(topic, message) {

        console.log("WOOO HOOO!!!");
        console.log('TOPIC: '+topic);
        console.log('MESSAGE: '+message);
   }

    componentDidMount () {
        var authorization = authorizationStore.getAuthorization();
        
        // wspubsub.WsPubSub.set_authorization_key(authorization);       
        // wspubsub.WsPubSub.open_management_socket(this.managmentMessage);

        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    }
    shouldComponentUpdate(nextProps, nextState) {

        var doUpdate = false;

        if ((this.state.showTooltip !== nextState.showTooltip) ||
            (this.state.tooltipX !== nextState.tooltipX) ||
            (this.state.tooltipY !== nextState.tooltipY) ||
            (this.state.checked !== nextState.checked) ||
            (this.state.notInitialized !== nextState.notInitialized) ||
            (this.state.loading !== nextState.loading) ||
            (this.state.cancelButton !== nextState.cancelButton) ||
            (!this.state.panelItem.equals(nextState.panelItem)))
        {
            doUpdate = true;
        }
        else
        {
            if (typeof this.state.children === "undefined")
            { 
                if (typeof nextState.children !== "undefined")
                {
                    doUpdate = true;
                }
            }
            else
            {
                if (!this.state.children.equals(nextState.children))
                {
                    doUpdate = true;
                }
            }
        }

        return doUpdate;
    }
    _onStoresChange () {

        var panelItem = Immutable.fromJS(platformsPanelItemsStore.getItem(this.props.itemPath));
        var panelChildren = Immutable.fromJS(
                                platformsPanelItemsStore.getChildren(
                                    this.props.panelItem.toJS(), 
                                    this.props.itemPath)
                                );

        var loadingComplete = 
            platformsPanelItemsStore.getLoadingComplete(this.props.panelItem.toJS());

        if (loadingComplete === true || loadingComplete === null)
        {
            this.setState({panelItem: panelItem});
            this.setState({children: panelChildren});
            this.setState({checked: panelItem.get("checked")});

            if (this.props.panelItem.get("type") === "platform")
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
    }
    _expandAll () {
        
        platformsPanelActionCreators.expandAll(this.props.itemPath);
    }
    _handleArrowClick () {
        
        if (!this.state.loading) // If not loading, treat it as just a regular toggle button
        {
            if (this.state.panelItem.get("expanded") === null && 
                this.state.panelItem.get("type") === "platform") 
            {
                this.setState({loading: true});
                platformsPanelActionCreators.loadChildren(
                    this.props.panelItem.get("type"), this.props.panelItem.toJS()
                );
            }
            else
            {
                if (this.state.panelItem.get("expanded"))
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
    }
    _showCancel () {

        if (this.state.hasOwnProperty("loading") && (this.state.loading === true))
        {
            this.setState({cancelButton: true});
        }
    }
    _resumeLoad () {

        if (this.state.hasOwnProperty("loading"))
        {
            this.setState({cancelButton: false});
        }
    }
    _checkItem (checked) {

        if (checked)
        {
            this.setState({checked: null});
            platformChartActionCreators.addToChart(this.props.panelItem.toJS());
        }
        else
        {
            this.setState({checked: null});
            platformChartActionCreators.removeFromChart(this.props.panelItem.toJS());
        }
    }
    _showTooltip (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 70});
    }
    _hideTooltip () {
        this.setState({showTooltip: false});
    }
    _moveTooltip (evt) {
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 70});
    }
    _onAddDevices (evt) {

        var bacnetProxies = platformsStore.getRunningBacnetProxies(this.state.panelItem.get("uuid"));

        if (bacnetProxies.length)
        {
            devicesActionCreators.configureDevices(this.state.panelItem.toJS());
        }
        else
        {
            statusIndicatorActionCreators.openStatusIndicator("error", 
                "To scan for devices, a BACNet proxy agent for the platform must be installed and running.", null, "left");
        }
    }
    _onDeviceMethodChange (evt) {

        var deviceMethod = evt.target.value;

        this.setState({deviceMethod: deviceMethod});

        if (deviceMethod)
        {
            devicesActionCreators.addDevices(this.state.panelItem.toJS(), deviceMethod);
            controlButtonActionCreators.hideTaptip("addDevicesButton");
        }
    }
    _onDeviceConfig (panelItem) {

        var deviceName = panelItem.getIn(["path", panelItem.get("path").size - 1]);
        var platformUuid = panelItem.getIn(["path", 1]);

        devicesActionCreators.reconfigureDevice(deviceName, platformUuid);
    }
    render () {

        var panelItem = this.state.panelItem;
        var itemPath = this.props.itemPath;
        var propChildren = this.state.children;
        var children;

        var visibleStyle = {};

        if (panelItem.get("visible") !== true)
        {
            visibleStyle = {
                display: "none"
            }
        }

        var childClass;
        var arrowClasses = [ "arrowButton", "noRotate" ];
        var arrowContent;
        var arrowContentStyle = {
            width: "14px"
        }

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

        var DevicesButton;

        if (panelItem.get("type") === "platform")
        {
            var tooltipX = 20;
            var tooltipY = 70;

            var devicesTooltip = {
                "content": "Add Devices",
                "xOffset": tooltipX,
                "yOffset": tooltipY
            };

            DevicesButton = (
                <ControlButton 
                    name="addDevicesButton"
                    tooltip={devicesTooltip}
                    controlclass="panelItemButton"
                    nocentering={true}
                    floatleft={true}
                    fontAwesomeIcon="cogs"
                    clickAction={this._onAddDevices}></ControlButton>
            );
        }

        var ConfigureButton;

        if (panelItem.get("type") === "device")
        {
            var configureTooltip = {
                content: "Reconfigure Device",
                xOffset: 40,
                yOffset: 65
            }

            ConfigureButton = (
                <ControlButton 
                    name={"config-device-" + panelItem.get("uuid")}
                    tooltip={configureTooltip}
                    fontAwesomeIcon="wrench"
                    controlclass="panelItemButton"
                    nocentering={true}
                    floatleft={true}
                    clickAction={this._onDeviceConfig.bind(this, panelItem)}></ControlButton>
            );
        }
        
        var ChartCheckbox;
        var inputStyle;
        var spinnerStyle;

        if (["point"].indexOf(panelItem.get("type")) > -1)
        {
            if (this.state.checked !== null)
            {
                spinnerStyle = {
                    display: "none"
                }
            }
            else
            {
                inputStyle = {
                    display: "none"
                }
            }

            ChartCheckbox = (
                <div>
                    <CheckBox controlClass="panelItemCheckbox" 
                        controlStyle={inputStyle}
                        oncheck={this._checkItem}
                        selected={((typeof this.state.checked === "undefined" || this.state.checked === null) ? false : this.state.checked)}></CheckBox>
                    <div className="checkboxSpinner arrowButton"
                        style={spinnerStyle}>                        
                        <span style={arrowContentStyle}><i className="fa fa-circle-o-notch fa-spin fa-fw"></i></span>
                    </div>
                </div>
            );            
        }

        var tooltipStyle = {
            display: (panelItem.get("type") !== "type" ? (this.state.showTooltip ? "block" : "none") : "none"),
            position: "absolute",
            top: this.state.tooltipY + "px",
            left: this.state.tooltipX + "px"
        };

        var toolTipClasses = (this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer");

        if (!this.state.loading)
        {
            arrowClasses.push( ((panelItem.get("status") === "GOOD") ? "status-good" :
                                ( (panelItem.get("status") === "BAD") ? "status-bad" : 
                                    "status-unknown")) );
        }

        var agentInfo;

        if (panelItem.get("type") === "agent")
        {
            agentInfo = <div>Identity:&nbsp;{panelItem.get("identity")}</div>;
        } 

        if (this.state.cancelButton)
        {
            arrowContent = <span style={arrowContentStyle}><i className="fa fa-remove"></i></span>;
        }
        else if (this.state.loading)
        {
            arrowContent = <span style={arrowContentStyle}><i className="fa fa-circle-o-notch fa-spin fa-fw"></i></span>;
        }
        else if (panelItem.get("status") === "GOOD")
        {
            arrowContent = <span style={arrowContentStyle}>&#9654;</span>;
        } 
        else if (panelItem.get("status") === "BAD") 
        {
            arrowContent = <span style={arrowContentStyle}><i className="fa fa-minus-circle"></i></span>;
        }
        else
        {
            arrowContent = <span style={arrowContentStyle}>&#9644;</span>;
        }
          
        if (this.state.panelItem.get("expanded") === true && propChildren)
        {
            children = propChildren
                .sort(function (a, b) {
                    if (a.get("name").toUpperCase() > b.get("name").toUpperCase()) { return 1; }
                    if (a.get("name").toUpperCase() < b.get("name").toUpperCase()) { return -1; }
                    return 0;
                })
                .sort(function (a, b) {
                    if (a.get("sortOrder") > b.get("sortOrder")) { return 1; }
                    if (a.get("sortOrder") < b.get("sortOrder")) { return -1; }
                    return 0;
                })
                .map(function (propChild) {
                    
                    var grandchildren = [];
                    propChild.get("children").forEach(function (childString) {
                        grandchildren.push(propChild.get(childString));
                    });

                    var itemKey = (typeof propChild.get("uuid") !== "undefined" ? 
                                    propChild.get("uuid") : 
                                        (propChild.get("name") + this.get("uuid")))

                    return (
                        <PlatformsPanelItem key={itemKey} 
                            panelItem={propChild} 
                            itemPath={propChild.get("path").toJS()} 
                            panelChildren={grandchildren}/>
                    );
                }, this.state.panelItem); 

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

        if (!panelItem.get("uuid"))
        {
            itemClasses.push("item_type");
        }
        else
        {
            itemClasses.push("item_label");
        }

        if (panelItem.get("type") === "platform" && this.state.notInitialized)
        {
            itemClasses.push("not_initialized");
        }

        var listItem = 
                <div className={itemClasses.join(' ')}>
                    {panelItem.get("name")}
                </div>;

        return (
            <li
                key={panelItem.get("uuid")}
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
                    {DevicesButton} 
                    {ConfigureButton}  
                    {ChartCheckbox}                  
                    <div className={toolTipClasses}
                        style={tooltipStyle}>
                        <div className="tooltip_inner">
                            <div className="opaque_inner">
                                {agentInfo}
                                Status:&nbsp;{(panelItem.get("context")) ? panelItem.get("context") : panelItem.get("statusLabel")}
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
    }
};

export default PlatformsPanelItem;
