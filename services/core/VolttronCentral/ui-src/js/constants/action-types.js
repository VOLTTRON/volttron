'use strict';

var keyMirror = require('react/lib/keyMirror');

module.exports = keyMirror({
    OPEN_MODAL: null,
    CLOSE_MODAL: null,

    OPEN_STATUS: null,
    CLOSE_STATUS: null,

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

    RECEIVE_PLATFORM_STATUSES: null,
    TOGGLE_PLATFORMS_PANEL: null,
    CLOSE_PLATFORMS_PANEL: null,
    RESET_PLATFORMS_PANEL: null,

    RECEIVE_AGENT_STATUSES: null,
    RECEIVE_DEVICE_STATUSES: null,
    RECEIVE_PERFORMANCE_STATS: null,

    START_LOADING_DATA: null,
    END_LOADING_DATA: null,

    SHOW_CHARTS: null,
    ADD_TO_CHART: null,
    REMOVE_FROM_CHART: null,
    PIN_CHART: null,
    CHANGE_CHART_TYPE: null,
    CHANGE_CHART_REFRESH: null,
    REFRESH_CHART: null,
    REMOVE_CHART: null,
    LOAD_CHARTS: null,

    EXPAND_ALL: null,
    TOGGLE_ITEM: null,
    CHECK_ITEM: null,
    FILTER_ITEMS: null,

    // ADD_CONTROL_BUTTON: null,
    // REMOVE_CONTROL_BUTTON: null,
    TOGGLE_TAPTIP: null,
    HIDE_TAPTIP: null,


    RECEIVE_PLATFORM_TOPIC_DATA: null,
    RECEIVE_CHART_TOPICS: null
});
