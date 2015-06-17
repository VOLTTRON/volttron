'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var PercentChart = require('./percent-chart');
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
        this._initUpdateStatus();
    },
    componentDidUpdate: function () {
        this._initUpdateStatus();
    },
    componentWillUnmount: function () {
        platformsStore.removeChangeListener(this._onStoresChange);
        clearTimeout(this._updateStatusTimeout);
        if (this.state.error) {
            platformManagerActionCreators.clearPlatformError(this.state.platform);
        }
    },
    _initUpdateStatus: function () {
        if (!this.state.platform || this._updateStatusTimeout) { return; }
        this._updateStatusTimeout = setTimeout(this._updateStatus, 0);
    },
    _updateStatus: function () {
        platformManagerActionCreators.updateStatus(this.state.platform);
        this._updateStatusTimeout = setTimeout(this._updateStatus, 15000);
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

        var status;
        var agents;

        if (!platform.status) {
            status = (
                <p>Loading status...</p>
            );
        } else {
            status = [];

            for (var topic in platform.status) {
                status.push(
                    <div key={topic} className="status-chart">
                        <h4>{topic}</h4>
                        <PercentChart
                            points={platform.status[topic]}
                        />
                    </div>
                );
            }
        }

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
            <div className="view">
                {this.state.error && (
                    <div className="view__error error">{this.state.error}</div>
                )}
                <h2>
                    <Router.Link to="platforms">Platforms</Router.Link>
                    &nbsp;/&nbsp;
                    {platform.name} ({platform.uuid})
                </h2>
                <h3>Status</h3>
                {status}
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
