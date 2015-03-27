'use strict';

var React = require('react');

var Console = require('./console');
var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');
var Home = require('./home');
var LoginForm = require('./login-form');
var Navigation = require('./navigation');
var platformManagerStore = require('../stores/platform-manager-store');

var PlatformManager = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onChange);
        consoleStore.addChangeListener(this._onChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onChange);
        consoleStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    _onButtonClick: function () {
        consoleActionCreators.toggleConsole();
    },
    render: function () {
        var classes = ['platform-manager'];

        if (!this.state.consoleShown) {
            classes.push('platform-manager--console-hidden');
        }

        return (
            <div className={classes.join(' ')}>
                <div className="main">
                    {!this.state.loggedIn && <LoginForm />}
                    {this.state.loggedIn && <Navigation />}
                    {this.state.loggedIn && <Home />}
                </div>
                <input
                    className="toggle button"
                    type="button"
                    value={'Console ' + (this.state.consoleShown ? '\u25bc' : '\u25b2')}
                    onClick={this._onButtonClick}
                />
                {this.state.consoleShown && <Console className="console" />}
            </div>
        );
    }
});

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!platformManagerStore.getAuthorization(),
    };
}

module.exports = PlatformManager;
