'use strict';

var React = require('react');

var Home = require('./home');
var LoginForm = require('./login-form');
var Navigation = require('./navigation');
var Messenger = require('./messenger');

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
                {this.state.page === 'home' ? <Home /> : <Messenger />}
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
