'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
var chartStore = require('../stores/platform-chart-store');
var ComboBox = require('./combo-box');

var NewChartForm = React.createClass({
    getInitialState: function () {
        var state = {};

        state.refreshInterval = 15000;

        state.topics = chartStore.getChartTopics();

        state.selectedTopic = "";

        return state;
    },
    componentDidMount: function () {
        chartStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        chartStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState({ topics: chartStore.getChartTopics()});
    },
    _onPropChange: function (e) {
        var state = {};

        for (key in this.state)
        {
            state[key] = this.state[key];
        }

        var key = e.target.id;

        switch (e.target.type) {
        case 'checkbox':
            state[key] = e.target.checked;
            break;
        case 'number':
            state[key] = parseFloat(e.target.value);
            break;
        default:
            state[key] = e.target.value;
        }

        this.setState(state);
    },
    _onTopicChange: function (value) {
        this.setState({ selectedTopic: value });
    },
    _onCancelClick: function () {
        modalActionCreators.closeModal();
    },
    _onSubmit: function (e) {

        e.preventDefault();

        var selectedTopic = this.state.topics.find(function (topic) {
            return topic.value === this.state.selectedTopic;
        }, this);

        if (selectedTopic)
        {
            selectedTopic.uuid = selectedTopic.value;
            selectedTopic.topic = selectedTopic.value;
            selectedTopic.pinned = (this.state.pin ? true : false);
            selectedTopic.refreshInterval = this.state.refreshInterval;
            selectedTopic.chartType = this.state.chartType;
            selectedTopic.path = platformsPanelItemsStore.findTopicInTree(selectedTopic.topic);
            selectedTopic.max = this.state.max;
            selectedTopic.min = this.state.min;

            if (selectedTopic.path && selectedTopic.path.length > 1)
            {
                selectedTopic.parentUuid = selectedTopic.path[selectedTopic.path.length - 2];
            }
        }

        var notifyRouter = false;

        platformChartActionCreators.addToChart(selectedTopic, notifyRouter);

        if (selectedTopic.path)
        {
            platformsPanelActionCreators.checkItem(selectedTopic.path, true);
        }

        modalActionCreators.closeModal();
    },
    render: function () {
        var topicsSelector;

        if (this.state.topics.length)
        {
            topicsSelector = (
                <ComboBox items={this.state.topics} itemskey="key" itemsvalue="value" itemslabel="label" onselect={this._onTopicChange}>
                </ComboBox>
            )
        }
        else
        {
            topicsSelector = <div>Loading topics ...</div>
        }

        return (
            <form className="edit-chart-form" onSubmit={this._onSubmit}>
                <h1>Add Chart</h1>
                {this.state.error && (
                    <div className="error">{this.state.error.message}</div>
                )}
                <div className="form__control-group">
                    <label htmlFor="topic">Topics</label>
                    {topicsSelector}
                </div>
                <div className="form__control-group">
                    <label>Dashboard</label>
                    <input
                        className="form__control form__control--inline"
                        type="checkbox"
                        id="pin"
                        onChange={this._onPropChange}
                        checked={this.state.pin}
                    />&nbsp;
                    <label htmlFor="pin">Pin to dashboard</label>
                </div>
                <div className="form__control-group">
                    <label htmlFor="refreshInterval">Refresh interval (ms)</label>
                    <input
                        className="form__control form__control--inline"
                        type="number"
                        id="refreshInterval"
                        onChange={this._onPropChange}
                        value={this.state.refreshInterval}
                        min="250"
                        step="1"
                        placeholder="disabled"
                    />
                    <span className="form__control-help">
                        Omit to disable
                    </span>
                </div>
                <div className="form__control-group">
                    <label htmlFor="chartType">Chart type</label>
                    <select
                        id="chartType"
                        onChange={this._onPropChange}
                        value={this.state.chartType}
                        autoFocus
                        required
                    >
                        <option value="">-- Select type --</option>
                        <option value="line">Line</option>
                        <option value="lineWithFocus">Line with View Finder</option>
                        <option value="stackedArea">Stacked Area</option>
                        <option value="cumulativeLine">Cumulative Line</option>
                    </select>
                </div>
                <div className="form__control-group">
                    <label>Y-axis range</label>
                    <label htmlFor="min">Min:</label>&nbsp;
                    <input
                        className="form__control form__control--inline"
                        type="number"
                        id="min"
                        onChange={this._onPropChange}
                        value={this.state.min}
                        placeholder="auto"
                    />&nbsp;
                    <label htmlFor="max">Max:</label>&nbsp;
                    <input
                        className="form__control form__control--inline"
                        type="number"
                        id="max"
                        onChange={this._onPropChange}
                        value={this.state.max}
                        placeholder="auto"
                    /><br />
                    <span className="form__control-help">
                        Omit either to determine from data
                    </span>
                </div>
                <div className="form__actions">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                    >
                        Cancel
                    </button>
                    <button
                        className="button"
                        disabled={!this.state.selectedTopic || !this.state.chartType}
                    >
                        Load Chart
                    </button>
                </div>
            </form>
        );
    },
});

module.exports = NewChartForm;
