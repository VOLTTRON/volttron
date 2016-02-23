'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var controlButtonActionCreators = {
	toggleTaptip: function (name) {
		dispatcher.dispatch({
			type: ACTION_TYPES.TOGGLE_TAPTIP,
			name: name,
		});
	},
	hideTaptip: function (name) {
		dispatcher.dispatch({
			type: ACTION_TYPES.HIDE_TAPTIP,
			name: name,
		});
	},
};



module.exports = controlButtonActionCreators;
