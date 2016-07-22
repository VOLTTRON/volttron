'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _authorization = sessionStorage.getItem('authorization');
var _username = sessionStorage.getItem('username');

var authorizationStore = new Store();

authorizationStore.getAuthorization = function () {
    return _authorization;
};

authorizationStore.getUsername = function () {
    return _username;
};

authorizationStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _authorization = action.authorization;
            _username = action.name;
            sessionStorage.setItem('authorization', _authorization);
            sessionStorage.setItem('username', _username);
            authorizationStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_UNAUTHORIZED:
            authorizationStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _authorization = null;
            _username = null;
            sessionStorage.removeItem('authorization');
            sessionStorage.removeItem('username');
            authorizationStore.emitChange();
            break;
    }
});

module.exports = authorizationStore;
