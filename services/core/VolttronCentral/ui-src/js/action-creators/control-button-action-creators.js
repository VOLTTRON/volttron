'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var controlButtonActionCreators = {
	// addControlButton: function (name) {
	// 	dispatcher.dispatch({
	// 		type: ACTION_TYPES.ADD_CONTROL_BUTTON,
	// 		name: name,
	// 	});
	// },
	// removeControlButton: function (name) {
	// 	dispatcher.dispatch({
	// 		type: ACTION_TYPES.REMOVE_CONTROL_BUTTON,
	// 		name: name,
	// 	});
	// },
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
