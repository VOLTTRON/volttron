'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerStore = require('../stores/platform-manager-store');

var Navigation = React.createClass({
    mixins: [Router.State],
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        platformManagerStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        platformManagerStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var component = this;
        var navItems;

        if (this.state.loggedIn) {
            navItems = ['Platforms'].map(function (navItem) {
                var page = navItem.toLowerCase();

                if (component.isActive(page)) {
                    return (
                        <span key={page} className="navigation__item navigation__item--active">
                            {navItem}
                        </span>
                    );
                }

                return (
                    <Router.Link key={page} to={page} className="navigation__item">
                        {navItem}
                    </Router.Link>
                );
            });

            navItems.push(
                <Router.Link key="logout" to="logout" className="navigation__item">
                    Log out
                </Router.Link>
            );
        }

        return (
            <nav className="navigation">
                <h1 className="logo">
                    <span className="logo__name">VOLTTRON</span>
                    <span className="logo__tm">&trade;</span>
                </h1>
                {navItems}
            </nav>
        );
    }
});

function getStateFromStores() {
    return {
        loggedIn: !!platformManagerStore.getAuthorization(),
    };
}

module.exports = Navigation;
