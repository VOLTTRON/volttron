'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var platformManagerStore = require('../stores/platform-manager-store');
var rpc = require('../lib/rpc');
var xhr = require('../lib/xhr');

var messengerActionCreators = {
    makeRequest: function (method, params) {
        var exchange = {
            requestSent: Date.now(),
            request: {
                method: method,
                params: params,
            },
        };

        dispatcher.dispatch({
            type: ACTION_TYPES.CREATE_EXCHANGE,
            exchange: exchange,
        });

        new rpc.Request({
            method: method,
            params: params,
            authorization: platformManagerStore.getAuthorization(),
        })
            .then(function (response) {
                exchange.responseReceived = Date.now();
                exchange.response = response;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            })
            .catch(rpc.Error, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            })
            .catch(xhr.Error, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            });
    }
};

module.exports = messengerActionCreators;
