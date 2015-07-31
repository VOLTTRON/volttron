'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var topicData = {};

var topicDataStore = new Store();

topicDataStore.getTopicData = function (platform, topic) {
    if (topicData[platform.uuid] && topicData[platform.uuid][topic]) {
        return topicData[platform.uuid][topic];
    }

    return null;
};

topicDataStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.RECEIVE_PLATFORM_TOPIC_DATA:
            topicData[action.platform.uuid] = topicData[action.platform.uuid] || {};
            topicData[action.platform.uuid][action.topic] = action.data;
            topicDataStore.emitChange();
            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            topicData= {};
            topicDataStore.emitChange();
            break;
    }
});

module.exports = topicDataStore;
