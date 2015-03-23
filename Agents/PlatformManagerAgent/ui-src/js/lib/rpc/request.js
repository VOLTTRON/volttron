'use strict';

var uuid = require('node-uuid');

var RpcError = require('./error');
var XhrRequest = require('../xhr/request');

function RpcRequest(opts) {
    if (!this instanceof RpcRequest) {
        return new RpcRequest(opts);
    }

    opts = opts || {};

    this._request = {
        jsonrpc: '2.0',
        method: opts.method || null,
        params: opts.params || null,
        authorization: opts.authorization || null,
        id: uuid.v1(),
    };
}

RpcRequest.prototype.method = function (method) {
    if (method === undefined) {
        return this._request.method;
    }

    this._request.method = method;
};

RpcRequest.prototype.params = function (params) {
    if (params === undefined) {
        return cloneObject(this._request.params);
    }

    this._request.params = params;
};

RpcRequest.prototype.authorization = function (authorization) {
    if (authorization === undefined) {
        return this._request.authorization;
    }

    this._request.authorization = authorization;
};

RpcRequest.prototype.toJSON = function () {
    var obj = cloneObject(this._request);

    if (obj.params === null) {
        delete obj.params;
    }

    if (obj.authorization === null) {
        delete obj.authorization;
    }

    return obj;
};

RpcRequest.prototype.call = function () {
    var request = this.toJSON();

    return new XhrRequest({
        method: 'POST',
        url: '/jsonrpc',
        contentType: 'application/json',
        data: JSON.stringify(request),
        timeout: 60000
    }).then(function (response) {
        response = ordered(response);

        if (response.error) {
            throw new RpcError(response.error);
        }

        return response.result;
    });
};

function cloneObject(obj) {
    return JSON.parse(JSON.stringify(obj));
}

function ordered(response) {
    var orderedResponse = { jsonrpc: '2.0' };

    if (response.error) {
        orderedResponse.error = {
            code: response.error.code,
            message: response.error.message,
        };

        if (response.error.data) {
            orderedResponse.error.data = response.error.data;
        }
    } else {
        orderedResponse.result = response.result;
    }

    orderedResponse.id = response.id;

    return orderedResponse;
}

module.exports = RpcRequest;
