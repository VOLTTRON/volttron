'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');
var Store = require('../lib/store');

var _exchanges = [];

var consoleStore = new Store();

consoleStore.getExchanges = function () {
    return _exchanges;
};

consoleStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([platformManagerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECIEVE_AUTHORIZATION:
            _exchanges = [];
            consoleStore.emitChange();
            break;

        case ACTION_TYPES.MAKE_REQUEST:
            _exchanges.push(action.exchange);
            consoleStore.emitChange();
            break;

        case ACTION_TYPES.FAIL_REQUEST:
        case ACTION_TYPES.RECEIVE_RESPONSE:
            consoleStore.emitChange();
            break;
    }
});

module.exports = consoleStore;
