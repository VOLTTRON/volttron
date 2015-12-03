'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var actionStatusCreators = {
	openStatusIndicator: function (status, message) {
		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_STATUS,
			status: status,
			message: message,
		});
	},
	closeStatusIndicator: function () {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_STATUS,
		});
	},
};

module.exports = actionStatusCreators;
