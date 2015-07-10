'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
    OPEN_MODAL: null,
    CLOSE_MODAL: null,

    TOGGLE_CONSOLE: null,

    UPDATE_COMPOSER_VALUE: null,

    MAKE_REQUEST: null,
    FAIL_REQUEST: null,
    RECEIVE_RESPONSE: null,

    RECEIVE_AUTHORIZATION: null,
    RECEIVE_UNAUTHORIZED: null,
    CLEAR_AUTHORIZATION: null,

    REGISTER_PLATFORM_ERROR: null,
    DEREGISTER_PLATFORM_ERROR: null,

    RECEIVE_PLATFORMS: null,
    RECEIVE_PLATFORM: null,
    RECEIVE_PLATFORM_ERROR: null,
    CLEAR_PLATFORM_ERROR: null,

    RECEIVE_PLATFORM_TOPIC_DATA: null,
});
