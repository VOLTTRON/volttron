'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var graphStore = new Store();

graphStore.getGraphs = function (uuid) {
    

    return null;
};

graphStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

graphStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    
});

module.exports = graphStore;
