'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var Modal = React.createClass({
    _onClick: function (e) {
		if (e.target === e.currentTarget) {
			modalActionCreators.closeModal();
		}
	},
	render: function () {
		return (
			<div className="modal__overlay" onClick={this._onClick}>
				<div className="modal__dialog">
					{this.props.children}
				</div>
			</div>
		);
	},
});

module.exports = Modal;
