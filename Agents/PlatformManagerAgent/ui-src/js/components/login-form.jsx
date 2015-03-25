'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var loginFormStore = require('../stores/login-form-store');

var LoginForm = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        loginFormStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        loginFormStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    _onSubmit: function (e) {
        e.preventDefault();
        platformManagerActionCreators.requestAuthorization(
            this.refs.username.getDOMNode().value,
            this.refs.password.getDOMNode().value
        );
    },
    render: function () {
        return (
            <form className="login-form" onSubmit={this._onSubmit}>
                <h1>VOLTTRON(TM) Platform Manager</h1>
                <input ref="username" placeholder="Username" type="text" />
                <input ref="password" placeholder="Password" type="password" />
                <input className="button" type="submit" value="Log in" />
                {this.state.error ? (
                    <div className="error">
                        {this.state.error.message} ({this.state.error.code})
                    </div>
                ) : null }
            </form>
        );
    }
});

function getStateFromStores() {
    return { error: loginFormStore.getLastError() };
}

module.exports = LoginForm;
