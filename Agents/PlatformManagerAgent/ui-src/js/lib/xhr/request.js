'use strict';

var jQuery = require('jquery');
var Promise = require('bluebird');

var XhrError = require('./error');

function XhrRequest(opts) {
    return new Promise(function (resolve, reject) {
        opts.success = resolve;
        opts.error = function (response, type) {
            switch (type) {
            case 'error':
                reject(new XhrError('Server returned ' + response.status + ' status'));
                break;
            case 'timeout':
                reject(new XhrError('Request timed out'));
                break;
            default:
                reject(new XhrError('Request failed: ' + type));
            }
        };

        jQuery.ajax(opts);
    });
}

module.exports = XhrRequest;
