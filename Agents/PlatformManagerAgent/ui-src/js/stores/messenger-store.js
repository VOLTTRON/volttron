'use strict';

var assign = require('react/lib/Object.assign');
var EventEmitter = require('events').EventEmitter;

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');

var CHANGE_EVENT = 'change';

var _exchanges = [];

var messengerStore = assign({}, EventEmitter.prototype, {
    emitChange: function() {
        this.emit(CHANGE_EVENT);
    },
    addChangeListener: function (callback) {
        this.on(CHANGE_EVENT, callback);
    },
    removeChangeListener: function (callback) {
        this.removeListener(CHANGE_EVENT, callback);
    },
    getExchanges: function () {
        return _exchanges;
    },
});

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
