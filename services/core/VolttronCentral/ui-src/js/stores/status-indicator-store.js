'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _statusIndicatorContent = null;

var statusIndicatorStore = new Store();

statusIndicatorStore.getStatusIndicatorContent = function () {
    return _statusIndicatorContent;
};

statusIndicatorStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.OPEN_STATUS:
            _statusIndicatorContent = action.content;
            statusIndicatorStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_STATUS:
            _statusIndicatorContent = null;
            statusIndicatorStore.emitChange();
            break;
    }
});

module.exports = statusIndicatorStore;
