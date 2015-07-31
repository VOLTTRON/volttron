'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _lastRegisterError = null;
var _lastDeregisterError = null;

var platformRegistrationStore = new Store();

platformRegistrationStore.getLastRegisterError = function () {
    return _lastRegisterError;
};

platformRegistrationStore.getLastDeregisterError = function () {
    return _lastDeregisterError;
};

platformRegistrationStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.REGISTER_PLATFORM_ERROR:
            _lastRegisterError = action.error;
            platformRegistrationStore.emitChange();
            break;

        case ACTION_TYPES.DEREGISTER_PLATFORM_ERROR:
            _lastDeregisterError = action.error;
            platformRegistrationStore.emitChange();
            break;

        case ACTION_TYPES.CLOSE_MODAL:
            _lastRegisterError = null;
            _lastDeregisterError = null;
            platformRegistrationStore.emitChange();
            break;
    }
});

module.exports = platformRegistrationStore;
