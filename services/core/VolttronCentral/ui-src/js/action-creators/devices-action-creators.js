'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var devicesActionCreators = {
    addDevices: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.ADD_DEVICES,
            platform: platform
        });
    },
    scanForDevices: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.SCAN_FOR_DEVICES,
            platform: platform
        });
    },
    cancelScan: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CANCEL_SCANNING,
            platform: platform
        });
    },
    listDetectedDevices: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.LIST_DETECTED_DEVICES,
            platform: platform
        });
    },
    configureDevice: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CONFIGURE_DEVICE,
            device: device
        });
    },
    // configureRegistry: function (device) {
    //     dispatcher.dispatch({
    //         type: ACTION_TYPES.CONFIGURE_REGISTRY,
    //         device: device
    //     });
    // },
    generateRegistry: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.GENERATE_REGISTRY,
            device: device
        });
    },
    cancelRegistry: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CANCEL_REGISTRY,
            device: device
        });
    },
    loadRegistry: function (device, csvData, fileName) {
        dispatcher.dispatch({
            type: ACTION_TYPES.LOAD_REGISTRY,
            device: device,
            data: csvData,
            file: fileName
        });
    },
    editRegistry: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.EDIT_REGISTRY,
            device: device
        });
    },
    saveRegistry: function (device, values) {
        dispatcher.dispatch({
            type: ACTION_TYPES.SAVE_REGISTRY,
            device: device,
            data: values
        });
    },
};



module.exports = devicesActionCreators;