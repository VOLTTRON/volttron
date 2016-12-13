'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _columnMover = {
    style: {
        display: "none",
        left: 0
    },
    originalX: 0
};

var columnMoverStore = new Store();

columnMoverStore.getColumnMover = function () {
    return _columnMover;
};

columnMoverStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.START_COLUMN_MOVEMENT:
            _columnMover.style.display = "block";
            _columnMover.style.top = action.top;
            _columnMover.style.height = action.height;
            _columnMover.originalX = action.positionX;
            columnMoverStore.emitChange();
            break;

        case ACTION_TYPES.MOVE_COLUMN:
            _columnMover.style.left = _columnMover.originalX + action.movement;
            columnMoverStore.emitChange();
            break;

        case ACTION_TYPES.END_COLUMN_MOVEMENT:
            _columnMover.style.display = "none";
            _columnMover.style.left = 0;
            columnMoverStore.emitChange();
            break;
    }
});

module.exports = columnMoverStore;
