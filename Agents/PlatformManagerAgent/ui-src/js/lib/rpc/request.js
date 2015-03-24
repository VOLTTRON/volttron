'use strict';

var uuid = require('node-uuid');

var RpcError = require('./error');
var XhrRequest = require('../xhr/request');

function RpcRequest(opts) {
    if (!this instanceof RpcRequest) {
        return new RpcRequest(opts);
    }

    // TODO: validate opts

    opts = opts || {};

    var request = {
        jsonrpc: '2.0',
        method: opts.method || null,
        id: uuid.v1(),
    };

    if ('params' in opts) {
        request.params = opts.params;
    }

    if ('authorization' in opts) {
        request.authorization = opts.authorization;
    }

    return new XhrRequest({
        method: 'POST',
        url: '/jsonrpc',
        contentType: 'application/json',
        data: JSON.stringify(request),
        timeout: 60000
    }).then(function (response) {
        if (response.error) {
            throw new RpcError(response.error);
        }

        return response.result;
    });
}

module.exports = RpcRequest;
