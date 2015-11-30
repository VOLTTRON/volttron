'use strict';

var React = require('react');
// var ReactCSSTransitionGroup = require('react-addons-css-transition-group');

var statusIndicatorCreators = require('../action-creators/status-indicator-action-creators');

var StatusIndicator = React.createClass({
	render: function () {
		return (
		
        	<div className="status-indicator">
				<label>Status Indicator</label>
				<br/>
				{this.props.children}
			</div>
        
			
		);
	},
});

module.exports = StatusIndicator;
