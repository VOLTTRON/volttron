'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _expanded = null;

var platformsPanelStore = new Store();

platformsPanelStore.getExpanded = function () {
    return _expanded;
};

platformsPanelStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.TOGGLE_PLATFORMS_PANEL:  
            (_expanded === null ? _expanded = true : _expanded = !_expanded);
            platformsPanelStore.emitChange();
            break;
        case ACTION_TYPES.CLOSE_PLATFORMS_PANEL:  
            _expanded = false;
            platformsPanelStore.emitChange();
            break;
        case ACTION_TYPES.RESET_PLATFORMS_PANEL:  
            _expanded = null;
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;
