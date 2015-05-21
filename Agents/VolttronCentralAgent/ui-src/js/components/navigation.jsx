'use strict';

var React = require('react');

var LogOutButton = require('./log-out-button');

var Navigation = React.createClass({
    render: function () {
        return (
            <div className="navigation">
                <h1><a href="#home">VOLTTRON(TM) Platform Manager</a></h1>
                <LogOutButton />
            </div>
        );
    }
});

module.exports = Navigation;
