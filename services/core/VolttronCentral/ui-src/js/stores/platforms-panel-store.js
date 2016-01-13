'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

// var _platforms = [
//             {
//                 "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
//                 "name": "PNNL",
//                 "status": "GOOD"
//             },
//             {
//                 "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
//                 "name": "UW",
//                 "status": "BAD"
//             },
//             {
//                 "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
//                 "name": "WSU",
//                 "status": "UNKNOWN"
//             }
//         ];;

var _expanded = null;

var platformsPanelStore = new Store();

// platformsPanelStore.getPlatforms = function () {
//     return _platforms;
// };

platformsPanelStore.getExpanded = function () {
    return _expanded;
};

platformsPanelStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.TOGGLE_PLATFORMS_PANEL:  
            (_expanded === null ? _expanded = true : _expanded = !_expanded);
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelStore;
