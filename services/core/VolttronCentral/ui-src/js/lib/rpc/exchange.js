'use strict';

var uuid = require('node-uuid');

var ACTION_TYPES = require('../../constants/action-types');
var dispatcher = require('../../dispatcher');
var RpcError = require('./error');
var xhr = require('../xhr');

function RpcExchange(request, redactedParams) {
    if (!(this instanceof RpcExchange)) {
        return new RpcExchange(request);
    }

    var exchange = this;

    // TODO: validate request
    request.jsonrpc = '2.0';
    request.id = uuid.v1();

    // stringify before redacting params
    var data = JSON.stringify(request);

    if (redactedParams && redactedParams.length) {
        redactedParams.forEach(function (paramPath) {
            paramPath = paramPath.split('.');

            var paramParent = request.params;

            while (paramPath.length > 1) {
                paramParent = paramParent[paramPath.shift()];
            }

            paramParent[paramPath[0]] = '[REDACTED]';
        });
    }

    exchange.initiated = Date.now();
    exchange.request = request;

    dispatcher.dispatch({
        type: ACTION_TYPES.MAKE_REQUEST,
        exchange: exchange,
        request: exchange.request,
    });

    exchange.promise = new xhr.Request({
        method: 'POST',
        url: './jsonrpc',
        contentType: 'application/json',
        data: data,
        timeout: 60000,
    })
        .finally(function () {
            exchange.completed = Date.now();
        })
        .then(function (response) {
            exchange.response = response;

            dispatcher.dispatch({
                type: ACTION_TYPES.RECEIVE_RESPONSE,
                exchange: exchange,
                response: response,
            });

            if (response.error) {
                throw new RpcError(response.error);
            }

            return JSON.parse(JSON.stringify(response.result));
        })
        .catch(xhr.Error, function (error) {
            exchange.error = error;

            dispatcher.dispatch({
                type: ACTION_TYPES.FAIL_REQUEST,
                exchange: exchange,
                error: error,
            });

            throw new RpcError(error);
        });
}

module.exports = RpcExchange;
