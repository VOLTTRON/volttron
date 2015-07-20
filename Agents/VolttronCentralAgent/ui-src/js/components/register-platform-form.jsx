'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformRegistrationStore = require('../stores/platform-registration-store');

var RegisterPlatformForm = React.createClass({
    getInitialState: function () {
        var state = getStateFromStores();

        state.name = state.address = '';

        return state;
    },
    componentDidMount: function () {
        platformRegistrationStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        platformRegistrationStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onNameChange: function (e) {
        this.setState({ name: e.target.value });
    },
    _onAddressChange: function (e) {
        this.setState({ address: e.target.value });
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        platformManagerActionCreators.registerPlatform(this.state.name, this.state.address);
    },
    render: function () {
        return (
            <form className="register-platform-form" onSubmit={this._onSubmit}>
                <h1>Register platform</h1>
                {this.state.error && (
                    <div className="error">{this.state.error.message}</div>
                )}
                <div className="form__control-group">
                    <label>Name</label>
                    <input
                        className="form__control form__control--block"
                        type="text"
                        onChange={this._onNameChange}
                        value={this.state.name}
                        autoFocus
                        required
                    />
                </div>
                <div className="form__control-group">
                    <label>VIP address</label>
                    <input
                        className="form__control form__control--block"
                        type="text"
                        onChange={this._onAddressChange}
                        value={this.state.address}
                        required
                    />
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
                        disabled={!this.state.name || !this.state.address}
                    >
                        Register
                    </button>
                </div>
            </form>
        );
    },
});

function getStateFromStores() {
    return { error: platformRegistrationStore.getLastDeregisterError() };
}

module.exports = RegisterPlatformForm;
