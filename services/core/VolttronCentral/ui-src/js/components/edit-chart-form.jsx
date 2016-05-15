'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
var platformChartActionCreators = require('../action-creators/platform-chart-action-creators');
var chartStore = require('../stores/platform-chart-store');
var ComboBox = require('./combo-box');

var EditChartForm = React.createClass({
    getInitialState: function () {
        var state = {};

        for (var prop in this.props.chart) {
            state[prop] = this.props.chart[prop];
        }

        state.topics = chartStore.getChartTopics(this.props.platform.uuid);

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
        this.setState({ topics: chartStore.getChartTopics(this.props.platform.uuid)});
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
    _onSubmit: function () {
        
        var selectedTopic = this.state.topics.find(function (topic) {
            return topic.path === this.state.selectedTopic;
        }, this);

        if (selectedTopic)
        {
            selectedTopic.uuid = selectedTopic.path;
            selectedTopic.topic = selectedTopic.path;
            selectedTopic.pinned = (this.state.pin ? true : false);
            selectedTopic.refreshInterval = this.state.refreshInterval;
            selectedTopic.type = this.state.type;
            selectedTopic.parentUuid = this.props.platform.uuid;
        }

        var notifyRouter = false;

        platformChartActionCreators.addToChart(selectedTopic, notifyRouter);
        platformActionCreators.saveChart(this.props.platform, null, selectedTopic);
        modalActionCreators.closeModal();
    },
    render: function () {
        var typeOptions;

        switch (this.state.type) {
        case 'line':
            typeOptions = (
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
            );
        }

        var topicsSelector;

        if (this.state.topics.length)
        {
            topicsSelector = (
                <ComboBox items={this.state.topics} itemskey="key" itemsvalue="path" itemslabel="label" onselect={this._onTopicChange}>
                </ComboBox>
            )
        }

        return (
            <form className="edit-chart-form" onSubmit={this._onSubmit}>
                <h1>{this.props.chart ? 'Edit' : 'Add'} Chart</h1>
                {this.state.error && (
                    <div className="error">{this.state.error.message}</div>
                )}
                <div className="form__control-group">
                    <label htmlFor="topic">Topic</label>
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
                    <label htmlFor="type">Chart type</label>
                    <select
                        id="type"
                        onChange={this._onPropChange}
                        value={this.state.type}
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
                {typeOptions}
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
                        disabled={!this.state.selectedTopic || !this.state.type}
                    >
                        Save
                    </button>
                </div>
            </form>
        );
    },
});

module.exports = EditChartForm;
