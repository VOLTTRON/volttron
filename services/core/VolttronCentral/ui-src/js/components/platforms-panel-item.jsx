'use strict';

var React = require('react');
var Router = require('react-router');

var platformsPanelAgentStore = require('../stores/platforms-panel-agent-store');
var PlatformsPanelAgent = require('./platforms-panel-agent');
// var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');

var PlatformsPanelItem = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.expanded = null;

        state.agents = [];

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
            this.setState({agents: getAgentsFromStore(this.props.platform)}); 
        }       
    },
    _toggleItem: function () {

        if (this.state.expanded === null)
        {
            this.setState({expanded: true});

            if (this.props.agents.length === 0)
            {
                this.setState({agents: getAgentsFromStore(this.props.platform)});
            }
        }
        else
        {
            this.setState({expanded: !this.state.expanded})    
        }
    },
    render: function () {
        var platform = this.props.platform;
        var agents;

        var propAgents = this.props.agents;
        var filterTerm = this.props.filter;

        var agentClasses = [];
        var arrowClasses = ["arrowButton"];

        arrowClasses.push( ((platform.status === "GOOD") ? "status-good" :
                                ( (platform.status === "BAD") ? "status-bad" : 
                                    "status-unknown")) )
        if (propAgents.length > 0)
        {
            arrowClasses.push("rotateDown");
            agentClasses = ["showAgents"];

            agents = propAgents
                .filter(function (agent) {
                    return (agent.name.indexOf(this) > -1);
                }, filterTerm) 
                .sort(function (a, b) {
                    if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                    if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                    return 0;
                })
                .map(function (agent) {

                    return (

                        <PlatformsPanelAgent agent={agent}/>
                        
                    );
                }, this);
        }
        else if (this.state.expanded !== null)
        {
            arrowClasses.push( (this.state.expanded ? "rotateDown" : "rotateRight") );

            if (this.state.expanded)
            {                
                if (this.state.agents) 
                {
                    agentClasses = ["showAgents"];
                    agents = this.state.agents
                        .sort(function (a, b) {
                            if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                            if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                            return 0;
                        })
                        .map(function (agent) {

                            return (

                                <PlatformsPanelAgent agent={agent}/>
                                
                            );
                        }, this);
                }
            }
            else
            {
                if (this.state.agents) 
                {
                    agentClasses = ["hideAgents"];
                }
            }
        }

        return (
            <li
                key={platform.uuid}
                className="panel-item"
            >
                <div className="platform-info">
                    <div className={arrowClasses.join(' ')}
                        onClick={this._toggleItem}>&#9654;</div>                    
                    <div className="platform-link">
                        <Router.Link
                            to="platform"
                            params={{uuid: platform.uuid}}
                        >
                        {platform.name}
                        </Router.Link>
                    </div>
                    
                </div>
                <div className={agentClasses}>
                    <ul className="platform-panel-list">
                        {agents}
                    </ul>
                </div>
            </li>
        );
    },
});

function getAgentsFromStore(platform) {
    return platformsPanelAgentStore.getAgents(platform);
}

module.exports = PlatformsPanelItem;
