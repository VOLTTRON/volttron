'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LoginForm = React.createClass({
    getInitialState: function () {
        var state = {};

        return state;
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
            </form>
        );
    }
});

module.exports = LoginForm;
