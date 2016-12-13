'use strict';

var keyMirror = require('keymirror');

module.exports = keyMirror({
    HANDLE_KEY_DOWN: null,
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

    WILL_INITIALIZE_PLATFORMS: null,
    RECEIVE_PLATFORMS: null,
    RECEIVE_PLATFORM: null,

    RECEIVE_PLATFORM_STATUSES: null,
    TOGGLE_PLATFORMS_PANEL: null,

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
    CHANGE_CHART_MIN: null,
    CHANGE_CHART_MAX: null,
    CHANGE_CHART_REFRESH: null,
    CHANGE_CHART_LENGTH: null,
    REFRESH_CHART: null,
    REMOVE_CHART: null,
    LOAD_CHARTS: null,
    REMOVE_PLATFORM_CHARTS: null,

    EXPAND_ALL: null,
    TOGGLE_ITEM: null,
    CHECK_ITEM: null,
    FILTER_ITEMS: null,

    CONFIGURE_DEVICES: null,
    FOCUS_ON_DEVICE: null,
    ADD_DEVICES: null,
    LISTEN_FOR_IAMS: null,
    DEVICE_DETECTED: null,
    DEVICE_SCAN_FINISHED: null,
    POINT_SCAN_FINISHED: null,
    POINT_RECEIVED: null,
    CANCEL_SCANNING: null,
    CONFIGURE_DEVICE: null,
    REFRESH_DEVICE_POINTS: null,
    TOGGLE_SHOW_POINTS: null,
    EDIT_REGISTRY_CONFIG: null,
    EDIT_DEVICE_CONFIG: null,
    RECONFIGURE_REGISTRY_FILE: null,
    UPDATE_REGISTRY: null,
    LOAD_REGISTRY: null,
    LOAD_REGISTRY_FILES: null,
    UNLOAD_REGISTRY_FILES: null,
    CANCEL_REGISTRY: null,
    SAVE_REGISTRY: null,
    SAVE_CONFIG: null,

    TOGGLE_TAPTIP: null,
    HIDE_TAPTIP: null,
    SHOW_TAPTIP: null,
    CLEAR_BUTTON: null,

    START_COLUMN_MOVEMENT: null,
    END_COLUMN_MOVEMENT: null,
    MOVE_COLUMN: null,

    RECEIVE_CHART_TOPICS: null
});
