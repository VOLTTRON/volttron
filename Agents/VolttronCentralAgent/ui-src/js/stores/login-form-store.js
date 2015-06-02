'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _lastError = null;

var loginFormStore = new Store();

loginFormStore.getLastError = function () {
    return _lastError;
};

loginFormStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _lastError = null;
            loginFormStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            _lastError = action.error;
            loginFormStore.emitChange();
            break;
    }
});

module.exports = loginFormStore;
