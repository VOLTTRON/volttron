'use strict';

var React = require('react');

var LogOutButton = require('./log-out-button');

var Navigation = React.createClass({
    render: function () {
        return (
            <div className="navigation">
                <h1>PlatformManager</h1>
                <LogOutButton />
            </div>
        );
    }
});

module.exports = Navigation;
