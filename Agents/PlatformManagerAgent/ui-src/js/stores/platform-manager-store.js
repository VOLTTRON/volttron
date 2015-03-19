'use strict';

var assign = require('react/lib/Object.assign');
var EventEmitter = require('events').EventEmitter;

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');

var CHANGE_EVENT = 'change';

var _authorization = sessionStorage.getItem('authorization');

var platformManagerStore = assign({}, EventEmitter.prototype, {
    emitChange: function() {
        this.emit(CHANGE_EVENT);
    },
    addChangeListener: function (callback) {
        this.on(CHANGE_EVENT, callback);
    },
    removeChangeListener: function (callback) {
        this.removeListener(CHANGE_EVENT, callback);
    },
    getAuthorization: function () {
        return _authorization;
    },
});

platformManagerStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
            _authorization = action.authorization;
            sessionStorage.setItem('authorization', _authorization);
            platformManagerStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _authorization = null;
            sessionStorage.removeItem('authorization');
            platformManagerStore.emitChange();
            break;
    }
});

module.exports = platformManagerStore;
