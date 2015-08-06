'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var modalActionCreators = {
	openModal: function (content) {
		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_MODAL,
			content: content,
		});
	},
	closeModal: function () {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_MODAL,
		});
	},
};

module.exports = modalActionCreators;
