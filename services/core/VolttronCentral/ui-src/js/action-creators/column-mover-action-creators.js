'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var columnMoverActionCreators = {
	startColumnMovement: function (positionX, top, height) {
		dispatcher.dispatch({
			type: ACTION_TYPES.START_COLUMN_MOVEMENT,
			positionX: positionX,
			top: top,
			height: height
		});
	},
	moveColumn: function (movement) {
		dispatcher.dispatch({
			type: ACTION_TYPES.MOVE_COLUMN,
			movement: movement
		});
	},
	endColumnMovement: function () {
		dispatcher.dispatch({
			type: ACTION_TYPES.END_COLUMN_MOVEMENT
		});
	},
};

module.exports = columnMoverActionCreators;
