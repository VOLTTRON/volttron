'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');
var Store = require('../lib/store');

var _exchanges = [];

var messengerStore = new Store();

messengerStore.getExchanges = function () {
    return _exchanges;
};

messengerStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([platformManagerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
            _exchanges = [];
            messengerStore.emitChange();
            break;

        case ACTION_TYPES.CREATE_EXCHANGE:
            _exchanges.push(action.exchange);
            messengerStore.emitChange();
            break;

        case ACTION_TYPES.UPDATE_EXCHANGE:
            messengerStore.emitChange();
            break;
    }
});

module.exports = messengerStore;
