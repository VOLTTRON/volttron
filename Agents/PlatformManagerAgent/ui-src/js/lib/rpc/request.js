'use strict';

var jQuery = require('jquery');
var Promise = require('bluebird');
var uuid = require('node-uuid');

var RequestError = require ('./request-error');
var ResponseError = require ('./response-error');

function Request(opts) {
    if (!this instanceof Request) {
        return new Request(opts);
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

Request.prototype.method = function (method) {
    if (method === undefined) {
        return this._request.method;
    }

    this._request.method = method;
};

Request.prototype.params = function (params) {
    if (params === undefined) {
        return clone(this._request.params);
    }

    this._request.params = params;
};

Request.prototype.authorization = function (authorization) {
    if (authorization === undefined) {
        return this._request.authorization;
    }

    this._request.authorization = authorization;
};

Request.prototype.toJSON = function () {
    var obj = clone(this._request);

    if (obj.params === null) {
        delete obj.params;
    }

    if (obj.authorization === null) {
        delete obj.authorization;
    }

    return obj;
};

Request.prototype.call = function () {
    var self = this;

    return new Promise(function (resolve, reject) {
        var request = self.toJSON();

        jQuery.ajax({
            method: 'POST',
            url: '/jsonrpc',
            contentType: 'application/json',
            data: JSON.stringify(request),
            timeout: 60000,
            success: function (response) {
                response = ordered(response);

                if (response.error) {
                    reject(new ResponseError(response));
                }

                resolve(response);
            },
            error: function (response, type) {
                switch (type) {
                case 'error':
                    reject(new RequestError('Server returned ' + response.status + ' status'));
                    break;
                case 'timeout':
                    reject(new RequestError('Request timed out'));
                    break;
                default:
                    reject(new RequestError('Request failed: ' + type));
                }
            }
        });
    });
};

function clone(obj) {
    // stringify + parse for deep clone
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

module.exports = Request;
