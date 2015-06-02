'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformManagerStore = require('../stores/platform-manager-store');

var Platform = React.createClass({
    mixins: [Router.State],
    getInitialState: getStateFromStores,
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores.call(this));
    },
    _onFileChange: function (e) {
        if (!e.target.files.length) { return; }

        var reader = new FileReader();
        var platform = this.state.platform;
        var files = e.target.files;
        var parsedFiles = [];

        function doFile(index) {
            if (index === files.length) {
                platformManagerActionCreators.installAgents(platform, parsedFiles);
                return;
            }

            reader.onload = function () {
                parsedFiles.push({
                    file_name: files[index].name,
                    file: reader.result,
                });
                doFile(index + 1);
            };

            reader.readAsDataURL(files[index]);
        }

        doFile(0);
    },
    render: function () {
        if (!this.state.platform) {
            return (
                <p>Platform not found.</p>
            );
        }

        var platform = this.state.platform;
        var agents;

        if (!platform.agents) {
            agents = (
                <p>Loading agents...</p>
            );
        } else if (!platform.agents.length) {
            agents = (
                <p>No agents installed.</p>
            );
        } else {
            agents = (
                <table>
                    <thead>
                        <tr>
                            <th>Agent</th>
                            <th>UUID</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {platform.agents.map(function (agent) {
                            return (
                                <AgentRow
                                    key={agent.uuid}
                                    platform={platform}
                                    agent={agent} />
                            );
                        })}
                    </tbody>
                </table>
            );
        }

        return (
            <div className="view" key={platform.uuid}>
                <h2>
                    <Router.Link to="platforms">Platforms</Router.Link>
                    &nbsp;/&nbsp;
                    {platform.name} ({platform.uuid})
                </h2>
                <h3>Agents</h3>
                {agents}
                <h3>Install agents</h3>
                <input type="file" multiple onChange={this._onFileChange} />
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platform: platformManagerStore.getPlatform(this.getParams().uuid),
    };
}

module.exports = Platform;
