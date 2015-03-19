'use strict';

var assign = require('react/lib/Object.assign');
var EventEmitter = require('events').EventEmitter;

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('./platform-manager-store');

var CHANGE_EVENT = 'change';

var _lastError = null;

var loginFormStore = assign({}, EventEmitter.prototype, {
    emitChange: function() {
        this.emit(CHANGE_EVENT);
    },
    addChangeListener: function (callback) {
        this.on(CHANGE_EVENT, callback);
    },
    removeChangeListener: function (callback) {
        this.removeListener(CHANGE_EVENT, callback);
    },
    getLastError: function () {
        return _lastError;
    },
});

loginFormStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([platformManagerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
            _lastError = null;
            loginFormStore.emitChange();
            break;

        case ACTION_TYPES.REQUEST_AUTHORIZATION_FAIL:
            _lastError = action.error;
            loginFormStore.emitChange();
            break;
    }
});

module.exports = loginFormStore;
