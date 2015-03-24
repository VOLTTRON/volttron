'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var messengerStore = require('./messenger-store');
var platformManagerStore = require('../stores/platform-manager-store');
var Request = require('../lib/rpc/request');
var Store = require('../lib/store');

var _request;

function _initRequest(method, params) {
    _request = new Request({
        method: method,
        params: params,
        authorization: platformManagerStore.getAuthorization()
    });
}

_initRequest();

var composerStore = new Store();

composerStore.getRequest = function () {
    return _request;
};

composerStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([messengerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECEIVE_AUTHORIZATION:
            _initRequest();
            composerStore.emitChange();
            break;

        case ACTION_TYPES.CREATE_EXCHANGE:
            _initRequest(action.exchange.request.method(), action.exchange.request.params());
            composerStore.emitChange();
            break;
    }
});

module.exports = composerStore;
