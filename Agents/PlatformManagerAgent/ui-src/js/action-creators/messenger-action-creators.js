'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');
var xhr = require('../lib/xhr');

var messengerActionCreators = {
    makeRequest: function (request) {
        var exchange = {
            requestSent: Date.now(),
            request: request,
        };

        dispatcher.dispatch({
            type: ACTION_TYPES.CREATE_EXCHANGE,
            exchange: exchange,
        });

        request.call()
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
            .catch(xhr.RequestError, function (error) {
                exchange.response = error;

                dispatcher.dispatch({
                    type: ACTION_TYPES.UPDATE_EXCHANGE,
                    exchange: exchange,
                });
            });
    }
};

module.exports = messengerActionCreators;
