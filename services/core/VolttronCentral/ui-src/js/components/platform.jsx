'use strict';

var React = require('react');
var Router = require('react-router');

var AgentRow = require('./agent-row');
var Chart = require('./chart');
var EditChartForm = require('./edit-chart-form');
var ConfirmForm = require('./confirm-form');
var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
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
    _onEditChartClick: function (platform, chart) {
        modalActionCreators.openModal(<EditChartForm platform={platform} chart={chart} />);
    },
    _onDeleteChartClick: function (platform, chart) {
        modalActionCreators.openModal(
            <ConfirmForm
                promptTitle="Delete chart"
                promptText={'Delete ' + chart.type + ' chart for ' + chart.topic + '?'}
                confirmText="Delete"
                onConfirm={platformActionCreators.deleteChart.bind(null, platform, chart)}
            />
        );
    },
    _onAddChartClick: function (platform) {
        modalActionCreators.openModal(<EditChartForm platform={platform} />);
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

        var charts;
        var agents;

        if (!platform.charts) {
            charts = (
                <p>Loading charts...</p>
            );
        } else {
            charts = platform.charts.map(function (chart) {
                var key = [
                    platform.uuid,
                    chart.topic,
                    chart.type,
                ].join('::');

                return (
                    <div key={key} className="view__item view__item--tile chart">
                        <h4 className="chart__title">{chart.topic}</h4>
                        <Chart
                            platform={platform}
                            chart={chart}
                        />
                        <div className="chart__actions">
                            <a onClick={this._onEditChartClick.bind(this, platform, chart)}>
                                Edit
                            </a>
                            <a onClick={this._onDeleteChartClick.bind(this, platform, chart)}>
                                Delete
                            </a>
                        </div>
                    </div>
                );
            }, this);
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
            <div className="platform-view">
                {this.state.error && (
                    <div className="view__error error">{this.state.error}</div>
                )}
                <h2>
                    <Router.Link to="platforms">Platforms</Router.Link>
                    &nbsp;/&nbsp;
                    {platform.name} ({platform.uuid})
                </h2>
                <h3>Charts</h3>
                {charts}
                <div>
                    <button
                        className="button"
                        onClick={this._onAddChartClick.bind(null, this.state.platform)}
                    >
                        Add chart
                    </button>
                </div>
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
