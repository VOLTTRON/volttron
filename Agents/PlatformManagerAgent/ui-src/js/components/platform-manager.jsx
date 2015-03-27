'use strict';

var React = require('react');

var Console = require('./console');
var Home = require('./home');
var LoginForm = require('./login-form');
var Navigation = require('./navigation');
var platformManagerStore = require('../stores/platform-manager-store');

var PlatformManager = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        if (!this.state.loggedIn) {
            return (
                <LoginForm />
            );
        }

        return (
            <div>
                <Navigation />
                {this.state.page === 'home' ? <Home /> : <Console />}
            </div>
        );
    }
});

function getStateFromStores() {
    return {
        loggedIn: !!platformManagerStore.getAuthorization(),
        page: platformManagerStore.getPage(),
    };
}

module.exports = PlatformManager;
