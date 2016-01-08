'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');

var PlatformsPanelItem = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.expanded = null;

        state.children = [];

        return state;
    },
    // componentDidMount: function () {
    //     platformsPanelStore.addChangeListener(this._onStoresChange);
    // },
    // componentWillUnmount: function () {
    //     platformsPanelStore.removeChangeListener(this._onStoresChange);
    // },
    _onStoresChange: function () {

        if (this.state.expanded)
        {
            this.setState({children: getItemsFromStore(this.props.panelItem)}); 
        }       
    },
    _toggleItem: function () {

        if (this.state.expanded === null)
        {
            var children = [];

            if (this.state.children.length === 0)
            {
                children = getItemsFromStore(this.props.panelItem);
                this.setState({children: children});
            }
            else
            {
                children = this.state.children;
            }

            if (children.length > 0)
            {
                this.setState({expanded: true});
            }
        }
        else
        {
            if (this.state.children.length > 0)
            {
                this.setState({expanded: !this.state.expanded});
            }
        }
    },
    _checkItem: function () {

    },
    render: function () {
        var panelItem = this.props.panelItem;
        var items;
        var agents;
        var devices;
        var renderItems;

        var propChildren = this.props.children;
        var filterTerm = this.props.filter;

        var itemClasses;
        var arrowClasses = ["arrowButton", "noRotate"];

        var checkboxClass = "panelItemCheckbox";
        var checkboxStyle = {
            display : (["agent", "device", "point"].indexOf(panelItem.type) < 0 ? "none" : "block")
        };

        var childrenItems = [];

        arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) )
        if (propChildren.length > 0)
        {
            arrowClasses.push("rotateDown");
            itemClasses = "showItems";

            items = propChildren
                .filter(function (item) {
                    return (item.name.indexOf(this) > -1);
                }, filterTerm) 
                .sort(function (a, b) {
                    if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                    if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                    return 0;
                })
                .map(function (item) {

                    return (

                        <PlatformsPanelItem panelItem={item} children={childrenItems}/>
                        
                    );
                }, this);
        }
        else if (this.state.expanded !== null)
        {
            var classIndex = arrowClasses.indexOf("noRotate");
            if (classIndex > -1)
            {
                arrowClasses.splice(classIndex, 1);
            }

            arrowClasses.push(this.state.expanded ? "rotateDown" : "rotateRight");

            if (this.state.expanded)
            {                
                if (this.state.children)
                {
                    itemClasses = "showItems";

                    var agentItems = findAgentsOrDevices(this.state.children, "agents");
                    
                    if (agentItems.length > 0)
                    {
                        agents = agentItems.map(function (item) {
                            return (
                                <PlatformsPanelItem panelItem={item} children={childrenItems}/>
                            );
                        }, this);
                    }

                    var deviceItems = findAgentsOrDevices(this.state.children, "devices");

                    if (deviceItems.length > 0)
                    {
                        devices = deviceItems.map(function (item) {
                            return (
                                <PlatformsPanelItem panelItem={item} children={childrenItems}/>
                            );
                        }, this);
                    }

                    if (!agents && !devices)
                    {
                        items = this.state.children
                            .sort(function (a, b) {
                                if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                                if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                                return 0;
                            })
                            .map(function (item) {

                                return (

                                    <PlatformsPanelItem panelItem={item} children={childrenItems}/>
                                    
                                );
                            }, this);
                    }
                }
            }
            else
            {
                if (this.state.children) 
                {
                    itemClasses = "hideItems";
                }
            }
        }

        if (items)
        {
            renderItems = <ul className="platform-panel-list">{items}</ul>;
        }
        else
        {
            if (agents && devices)
            {
                renderItems = <ul className="platform-panel-list">
                                <li><ul className="platform-panel-sublist"><span className="boldText">Agents</span> {agents}</ul></li>
                                <li><ul className="platform-panel-sublist"><span className="boldText">Devices</span> {devices}</ul></li>
                               </ul>;
            }
            else if (agents)
            {
                renderItems = <ul className="platform-panel-list">Agents {agents}</ul>;
            }
            else if (devices)
            {
                renderItems = <ul className="platform-panel-list">Devices {devices}</ul>;
            }
        }


        return (
            <li
                key={panelItem.uuid}
                className="panel-item"
            >
                <div className="platform-info">
                    <div className={arrowClasses.join(' ')}
                        onClick={this._toggleItem}>&#9654;</div>  
                    <input className={checkboxClass}
                        style={checkboxStyle}
                        type="checkbox"
                        onClick={this._checkItem}></input>                    
                    <div className="platform-link">
                        <Router.Link
                            to="platform"
                            params={{uuid: panelItem.uuid}}
                        >
                        {panelItem.name}
                        </Router.Link>
                    </div>
                    
                </div>
                <div className={itemClasses}>
                    {renderItems}
                </div>
            </li>
        );
    },
});

function findAgentsOrDevices(item, filterTerm)
{
    var agentsOrDevices = [];

    var items = item.filter(function(child) {
        return (child.hasOwnProperty(this) && !child.hasOwnProperty("children"));
    }, filterTerm);

    if (items.length !== 0)
    {
        items = items[0][filterTerm];

        for (var key in items)
        {
            agentsOrDevices.push(items[key]);
        }
    }

    return agentsOrDevices;
}


function getItemsFromStore(parentItem) {
    return platformsPanelItemsStore.getItems(parentItem);
}

module.exports = PlatformsPanelItem;
