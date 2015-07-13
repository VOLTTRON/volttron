'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');

var EditChartForm = React.createClass({
    getInitialState: function () {
        var state = {};

        for (var prop in this.props.chart) {
            state[prop] = this.props.chart[prop];
        }

        return state;
    },
    _onPropChange: function (e) {
        var state = {};

        switch (e.target.type) {
        case 'checkbox':
            state[e.target.id] = e.target.checked;
            break;
        case 'number':
            state[e.target.id] = parseFloat(e.target.value);
            break;
        default:
            state[e.target.id] = e.target.value;
        }

        this.setState(state);
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        platformActionCreators.saveChart(this.props.platform, this.props.chart, this.state);
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

        return (
            <form className="edit-chart-form" onSubmit={this._onSubmit}>
                <h1>{this.props.chart ? 'Edit' : 'Add'} chart</h1>
                {this.state.error && (
                    <div className="error">{this.state.error.message}</div>
                )}
                <div className="form__control-group">
                    <label htmlFor="topic">Platform</label>
                    {this.props.platform.name} ({this.props.platform.uuid})
                </div>
                <div className="form__control-group">
                    <label htmlFor="topic">Topic</label>
                    <input
                        className="form__control form__control--block"
                        type="text"
                        id="topic"
                        onChange={this._onPropChange}
                        value={this.state.topic}
                        placeholder="e.g. some/published/topic"
                        required
                    />
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
                        disabled={!this.state.topic || !this.state.type}
                    >
                        Save
                    </button>
                </div>
            </form>
        );
    },
});

module.exports = EditChartForm;
