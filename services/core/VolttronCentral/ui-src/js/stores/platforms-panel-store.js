'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _platforms = [
            {
                "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
                "status": "GOOD"
            },
            {
                "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
                "status": "BAD"
            },
            {
                "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
                "status": "UNKNOWN"
            }
        ];;

var _panelAction;

var platformsPanelStore = new Store();

platformsPanelStore.getPlatforms = function () {
    return _panelAction;
};

// platformsPanelStore.getPanelAction = function () {
//     return _panelAction;
// };

platformsPanelStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            _platforms = action.platforms;
            platformsPanelStore.emitChange();
            break;
        // case ACTION_TYPES.CLOSE_PLATFORMS_PANEL:
        //     _panelAction = "close";
        //     platformsPanelStore.emitChange();
        //     break;
        // case ACTION_TYPES.OPEN_PLATFORMS_PANEL:
        //     _panelAction = "open";
        //     platformsPanelStore.emitChange();
        //     break;
    }
});

module.exports = platformsPanelStore;
