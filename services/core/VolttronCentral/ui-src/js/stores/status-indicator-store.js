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

            if (_statusMessage === null)
            {
                _statusMessage = action.message;
                _status = action.status;
                _highlight = action.highlight;
                _align = action.align;
            }
            else
            {
                if (_status === "success" || _status === action.status) // don't update indicator if 
                {                                                       // we're already showing an error,
                                                                        // unless we have another error 
                                                                        // message to add to it    
                    
                    if (_statusMessage !== action.message) // don't update indicator if the next
                    {                                     // message is the same as the first
                        
                        _statusMessage = _statusMessage + "; " + action.message;
                    }
                }                
            }

            statusIndicatorStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_STATUS:
            _statusMessage = null;
            _status = null;
            statusIndicatorStore.emitChange();
            break;
    }
});

module.exports = statusIndicatorStore;
