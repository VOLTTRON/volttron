'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var platformActionCreators = require('../action-creators/platform-action-creators');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsStore = require('../stores/platforms-store');

var Platform = React.createClass({
    mixins: [Router.State],
    getInitialState: function () {
        return getStateFromStores(this);
    },
    componentDidMount: function () {
        platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
        if (this.state.error) {
            platformActionCreators.clearPlatformError(this.state.platform);
        }
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
                platformActionCreators.installAgents(platform, parsedFiles);
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
        var platform = this.state.platform;

        if (!platform) {
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
                            <th>Tag</th>
                            <th>UUID</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {platform.agents
                            .sort(function (a, b) {
                                if (a.name.toLowerCase() > b.name.toLowerCase()) { return 1; }
                                if (a.name.toLowerCase() < b.name.toLowerCase()) { return -1; }
                                return 0;
                            })
                            .map(function (agent) {
                                return (
                                    <AgentRow
                                        key={agent.uuid}
                                        platform={platform}
                                        agent={agent} />
                                );
                            })
                        }
                    </tbody>
                </table>
            );
        }

        return (
            <div className="platform-view">
                {this.state.error && (
                    <div className="view__error error">{this.state.error}</div>
                )}
                <h2>
                    <Router.Link to="platforms">Platforms</Router.Link>
                    &nbsp;/&nbsp;
                    {platform.name} ({platform.uuid})
                </h2>

                
                <br/>
                <br/>
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
        error: platformsStore.getLastError(component.getParams().uuid)
    };
}

module.exports = Platform;
