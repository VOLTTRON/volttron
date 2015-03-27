'use strict';

var RpcExchange = require('../lib/rpc/exchange');

var consoleActionCreators = {
    makeRequest: function (opts) {
        new RpcExchange(opts).promise.catch(function ignore() {});
    }
};

module.exports = consoleActionCreators;
