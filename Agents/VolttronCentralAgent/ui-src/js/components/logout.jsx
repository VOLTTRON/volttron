'use strict';

var React = require('react');
var Router = require('react-router');

var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var Logout = React.createClass({
	mixins: [Router.Navigation],
	componentDidMount: function () {
		platformManagerActionCreators.clearAuthorization();
        this.transitionTo('/');
	},
	render: function () {
		return (
			<div>Logging out...</div>
		);
	},
});

module.exports = Logout;
