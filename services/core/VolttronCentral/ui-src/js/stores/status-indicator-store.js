'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _statusMessage = null;
var _status = null;
var _highlight = null;
var _align = null;

var statusIndicatorStore = new Store();

statusIndicatorStore.getStatusMessage = function () {

    var status = {
        statusMessage: _statusMessage,
        status: _status
    };

    if (_highlight)
    {
        status.highlight = _highlight;
    }

    if (_align)
    {
        status.align = _align;
    }

    return status;
};

statusIndicatorStore.getStatus = function () {
    return _status;
};

statusIndicatorStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.OPEN_STATUS:
            _statusMessage = action.message;
            _status = action.status;
            _highlight = action.highlight;
            _align = action.align;

            statusIndicatorStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_STATUS:
            _statusMessage = {};
            _status = null;
            statusIndicatorStore.emitChange();
            break;
    }
});

module.exports = statusIndicatorStore;
