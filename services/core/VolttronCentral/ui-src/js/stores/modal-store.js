'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _modalContent = null;

var modalStore = new Store();

modalStore.getModalContent = function () {
    return _modalContent;
};

modalStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.OPEN_MODAL:
            _modalContent = action.content;
            modalStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_MODAL:
        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            _modalContent = null;
            modalStore.emitChange();
            break;
    }
});

module.exports = modalStore;
