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
            this.setState({children: getChildren(this.props.panelItem, this.props.itemPath)}); 
        }       
    },
    _toggleItem: function () {

        if (this.state.expanded === null)
        {
            var children = [];

            if (this.state.children.length === 0)
            {
                children = getChildren(this.props.panelItem, this.props.itemPath);
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
        var itemPath = this.props.itemPath;

        var items;
        var children;

        var propChildren = this.props.children;
        var filterTerm = this.props.filter;

        var itemClasses;
        var arrowClasses = ["arrowButton", "noRotate"];

        var checkboxClass = "panelItemCheckbox";

        var checkboxStyle = {
            display : (["device", "point"].indexOf(panelItem.type) < 0 ? "none" : "block")
        };

        // var childrenItems = [];

        arrowClasses.push( ((panelItem.status === "GOOD") ? "status-good" :
                                ( (panelItem.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) )
        // if (propChildren.length > 0)
        // {
        //     arrowClasses.push("rotateDown");
        //     itemClasses = "showItems";

        //     items = propChildren
        //         .filter(function (item) {
        //             return (item.name.indexOf(this) > -1);
        //         }, filterTerm) 
        //         .sort(function (a, b) {
        //             if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
        //             if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
        //             return 0;
        //         })
        //         .map(function (item) {

        //             return (

        //                 <PlatformsPanelItem panelItem={item} children={childrenItems}/>
                        
        //             );
        //         }, this);
        // }
        // else 

        var listItem;

        if (!panelItem.hasOwnProperty("uuid"))
        {
            listItem = <div>
                        {panelItem.name}
                    </div>;
                
            
        }
        else
        {
            listItem = <div className="platform-link">
                        <Router.Link
                            to="platform"
                            params={{uuid: panelItem.uuid}}
                        >
                        {panelItem.name}
                        </Router.Link>
                    </div>;
            
        }
        

        if (this.state.expanded !== null)
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

                    var childItems = this.state.children;
                    
                    if (childItems.length > 0)
                    {
                        children = childItems.map(function (child) {                            
                            return (
                                <PlatformsPanelItem panelItem={child} itemPath={child.path}/>
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
                    {listItem}
                    
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

function getChildren(parent, parentPath)
{
    // var childList = [];

    
    // if (parent.hasOwnProperty("children")) //parent is an actual object and its children are object types
    // {
    //     var children = parent.children.slice(0);

    //     for (var i = 0; i < children.length; i++) // for each child, create an object with a path property
    //     {
    //         var child = children[i];
    //         var childPath = parentPath.slice(0);
    //         childPath.push(child);

    //         childList.push({child: {"path": childPath, "name": child} });
    //     }        
    // }
    // else // parent is an object type and its children are actual objects
    // {
    //     childList = getItemsFromStore(parent, parentPath);
    // }

    
    return getItemsFromStore(parent, parentPath);
}


function getItemsFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getItems(parentItem, parentPath);
}

module.exports = PlatformsPanelItem;
