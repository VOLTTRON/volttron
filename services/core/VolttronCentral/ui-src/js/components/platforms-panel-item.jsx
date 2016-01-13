'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var PlatformsPanelItem = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.expanded = null;

        state.children = getChildrenFromStore(this.props.panelItem, this.props.itemPath);

        return state;
    },
    componentDidMount: function () {
        platformsPanelItemsStore.addChangeListener(this._onStoresChange);
    },
    componentWillMount: function () {
        platformsPanelActionCreators.loadChildren(this.props.panelItem.type, this.props.panelItem);
    },
    componentWillUnmount: function () {
        platformsPanelItemsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {

        // if (this.state.expanded)
        // {
        //     this.setState({children: getItemsFromStore(this.props.panelItem, this.props.itemPath)}); 
        // }       

        var children = getChildrenFromStore(this.props.panelItem, this.props.itemPath);

        this.setState({children: children});

        // if (children.length > 0)
        // {
        //     this.setState({expanded: true});
        // }
    },
    _toggleItem: function () {

        // if (this.state.expanded === null)
        // {
        //     this.setState({expanded: true});

        //     var panelItem = this.props.panelItem;

        //     platformsPanelActionCreators.loadChildren(panelItem.type, panelItem);
            


        //     // var children = [];

        //     // if (this.state.children.length === 0)
        //     // {
        //     //     // children = getItemsFromStore(this.props.panelItem, this.props.itemPath);
        //     //     // this.setState({children: children});

        //     //     // var panelItem = this.props.panelItem;

        //     //     // platformsPanelActionCreators.loadPanelItems(panelItem.type, panelItem);

        //     //     // this.props.panelItem.children.forEach(function (child) {
                    
        //     //     //     platformsPanelActionCreators.loadPanelItems(panelItem[child], panelItem);
        //     //     // });
                
        //     // }
        //     // else
        //     // {
        //     //     children = this.state.children;
        //     // }

        //     // if (children.length > 0)
        //     // {
        //     //     this.setState({expanded: true});
        //     // }
        // }
        // else
        // {
        //     if (this.state.children.length > 0)
        //     {
        //         this.setState({expanded: !this.state.expanded});
        //     }
        // }

        if (this.state.children.length > 0)
        {
            this.setState({expanded: !this.state.expanded});
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
            display : (["point"].indexOf(panelItem.type) < 0 ? "none" : "block")
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
                            <b>
                                {panelItem.name}
                            </b>
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

// function getChildren(parent, parentPath)
// {
//     return getItemsFromStore(parent, parentPath);
// }


function getChildrenFromStore(parentItem, parentPath) {
    return platformsPanelItemsStore.getItems(parentItem, parentPath);
}

module.exports = PlatformsPanelItem;
