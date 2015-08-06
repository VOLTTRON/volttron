'use strict';

var React = require('react');
var Router = require('react-router');

var loginFormStore = require('../stores/login-form-store');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LoginForm = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        loginFormStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        loginFormStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _onUsernameChange: function (e) {
        this.setState({
            username: e.target.value,
            error: null,
        });
    },
    _onPasswordChange: function (e) {
        this.setState({
            password: e.target.value,
            error: null,
        });
    },
    _onSubmit: function (e) {
        e.preventDefault();
        platformManagerActionCreators.requestAuthorization(
            this.state.username,
            this.state.password
        );
    },
    render: function () {
        return (
            <form className="login-form" onSubmit={this._onSubmit}>
                <input
                    className="login-form__field"
                    type="text"
                    placeholder="Username"
                    autoFocus
                    onChange={this._onUsernameChange}
                />
                <input
                    className="login-form__field"
                    type="password"
                    placeholder="Password"
                    onChange={this._onPasswordChange}
                />
                <input
                    className="button login-form__submit"
                    type="submit"
                    value="Log in"
                    disabled={!this.state.username || !this.state.password}
                />
                {this.state.error ? (
                    <span className="login-form__error error">
                        {this.state.error.message} ({this.state.error.code})
                    </span>
                ) : null }
            </form>
        );
    }
});

function getStateFromStores() {
    return { error: loginFormStore.getLastError() };
}

module.exports = LoginForm;
