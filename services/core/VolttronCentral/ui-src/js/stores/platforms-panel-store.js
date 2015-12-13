'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _platforms = [
            {
                "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
                "name": "vc",
                "status": "GOOD"
            },
            {
                "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
                "name": "vc1",
                "status": "BAD"
            },
            {
                "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
                "name": "vc2",
                "status": "UNKNOWN"
            }
        ];;

var _expanded;

var platformsPanelStore = new Store();

platformsPanelStore.getPlatforms = function () {
    return _platforms;
};

platformsPanelStore.getExpanded = function () {
    return _expanded;
};

platformsPanelStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            _platforms = action.platforms;
            platformsPanelStore.emitChange();
            break;
        case ACTION_TYPES.EXTEND_PLATFORMS_PANEL:        
            _expanded = true;
            platformsPanelStore.emitChange();
            break;
        case ACTION_TYPES.COLLAPSE_PLATFORMS_PANEL:
            _expanded = false;
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;
