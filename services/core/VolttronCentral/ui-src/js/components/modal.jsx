'use strict';

var React = require('react');
var $ = require('jquery');

var modalActionCreators = require('../action-creators/modal-action-creators');

var Modal = React.createClass({
    mixins: [
        require('react-onclickoutside')
    ],
    componentDidMount: function () {
        window.addEventListener('keydown', this._closeModal);
        this._focusDisabled = $('input,select,textarea,button,a', React.findDOMNode(this.refs.main)).attr('tabIndex', -1);
    },
    componentWillUnmount: function () {
        window.removeEventListener('keydown', this._closeModal);
        if (this._focusDisabled) {
            this._focusDisabled.removeAttr('tabIndex');
            delete this._focusDisabled;
        }
    },
    handleClickOutside: function () {
        modalActionCreators.closeModal();
    },
    _closeModal: function (e) {
        if (e.keyCode === 27) {
            modalActionCreators.closeModal();
        }
    },
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
