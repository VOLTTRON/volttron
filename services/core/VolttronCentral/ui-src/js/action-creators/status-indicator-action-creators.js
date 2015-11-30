'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var actionStatusCreators = {
	openStatusIndicator: function (content) {
		dispatcher.dispatch({
			type: ACTION_TYPES.OPEN_STATUS,
			content: content,
		});
	},
	closeStatusIndicator: function () {
		dispatcher.dispatch({
			type: ACTION_TYPES.CLOSE_STATUS,
		});
	},
};

module.exports = actionStatusCreators;
