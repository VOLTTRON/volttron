'use strict';

var React = require('react');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var LogOutButton = React.createClass({
    _onClick: function () {
        platformManagerActionCreators.clearAuthorization();
    },
    render: function () {
        return (
            <button className="button" onClick={this._onClick}>Log out</button>
        );
    }
});

module.exports = LogOutButton;
