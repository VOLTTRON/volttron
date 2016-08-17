'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

var devicesActionCreators = {
    configureDevices: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CONFIGURE_DEVICES,
            platform: platform
        });
    },
    addDevices: function (platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.ADD_DEVICES,
            platform: platform
        });
    },
    scanForDevices: function (low, high, address) {

        var authorization = authorizationStore.getAuthorization();

        // return new rpc.Exchange({
        //     method: 'who_is',
        //     authorization: authorization,
        //     params: {
        //         low_device_id: low,
        //         high_device_id: high,
        //         target_address: address
        //     },
        // }).promise
        //     .then(function (result) {

        //         if (result)
        //         {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.LISTEN_FOR_IAMS,
                        low_device_id: low,
                        high_device_id: high,
                        target_address: address
                    });

                    //TODO: setup socket
            //     }
                
            // })
            // .catch(rpc.Error, function (error) {
            //     handle401(error, error.message);
            // });
        
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

function handle401(error, message, highlight, orientation) {
   if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformManagerActionCreators.clearAuthorization();
    }
    else if (message)
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = devicesActionCreators;