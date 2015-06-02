'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platform = React.createClass({
    mixins: [Router.State],
    getInitialState: function () {
        return getStateFromStores(this);
    },
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
        platformManagerActionCreators.clearPlatformError(this.state.platform);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores(this));
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
                <div className="view">
                    <h2>
                        <Router.Link to="platforms">Platforms</Router.Link>
                        &nbsp;/&nbsp;
                        {this.getParams().uuid}
                    </h2>
                    <p>Platform not found.</p>
                </div>
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
            <div className="view platform">
                {this.state.error && (
                    <div className="platform__error error">{this.state.error}</div>
                )}
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

function getStateFromStores(component) {
    return {
        platform: platformsStore.getPlatform(component.getParams().uuid),
        error: platformsStore.getLastError(component.getParams().uuid),
    };
}

module.exports = Platform;
