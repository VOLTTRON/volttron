'use strict';

var React = require('react');
var Router = require('react-router');

var authorizationStore = require('../stores/authorization-store');
var Console = require('./console');
var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');
var Modal = require('./modal');
var modalActionCreators = require('../action-creators/modal-action-creators');
var modalStore = require('../stores/modal-store');
var Navigation = require('./navigation');

var PlatformManager = React.createClass({
    mixins: [Router.Navigation, Router.State],
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        authorizationStore.addChangeListener(this._onStoreChange);
        consoleStore.addChangeListener(this._onStoreChange);
        modalStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        authorizationStore.removeChangeListener(this._onStoreChange);
        consoleStore.removeChangeListener(this._onStoreChange);
        modalStore.removeChangeListener(this._onStoreChange);
        window.removeEventListener('keydown', this._closeModal);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onToggleClick: function () {
        consoleActionCreators.toggleConsole();
    },
    _closeModal: function (e) {
        if (e.keyCode === 27) {
            modalActionCreators.closeModal();
            window.removeEventListener('keydown', this._closeModal);
        }
    },
    render: function () {
        var classes = ['platform-manager'];
        var modal;

        if (this.state.consoleShown) {
            classes.push('platform-manager--console-open');
        }

        classes.push(this.state.loggedIn ?
            'platform-manager--logged-in' : 'platform-manager--not-logged-in');

        if (this.state.modalContent) {
            window.addEventListener('keydown', this._closeModal);
            classes.push('platform-manager--modal-open');
            modal = (
                <Modal>{this.state.modalContent}</Modal>
            );
        }

        return (
            <div className={classes.join(' ')}>
                {modal}
                <div className="main">
                    <Navigation />
                    <Router.RouteHandler />
                </div>
                <input
                    className="toggle"
                    type="button"
                    value={'Console ' + (this.state.consoleShown ? '\u25bc' : '\u25b2')}
                    onClick={this._onToggleClick}
                />
                {this.state.consoleShown && <Console className="console" />}
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!authorizationStore.getAuthorization(),
        modalContent: modalStore.getModalContent(),
    };
}

module.exports = PlatformManager;
