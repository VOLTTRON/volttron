'use strict';

var assign = require('react/lib/Object.assign');
var EventEmitter = require('events').EventEmitter;

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var messengerStore = require('./messenger-store');
var platformManagerStore = require('../stores/platform-manager-store');
var Request = require('../lib/rpc/request');

var CHANGE_EVENT = 'change';

var _request;

function _initRequest(method, params) {
    _request = new Request({
        method: method,
        params: params,
        authorization: platformManagerStore.getAuthorization()
    });
}

_initRequest();

var composerStore = assign({}, EventEmitter.prototype, {
    emitChange: function() {
        this.emit(CHANGE_EVENT);
    },
    addChangeListener: function (callback) {
        this.on(CHANGE_EVENT, callback);
    },
    removeChangeListener: function (callback) {
        this.removeListener(CHANGE_EVENT, callback);
    },
    getRequest: function () {
        return _request;
    },
});

composerStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([messengerStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS:
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
