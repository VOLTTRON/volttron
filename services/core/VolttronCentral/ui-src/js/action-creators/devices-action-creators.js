'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var devicesStore = require('../stores/devices-store');
var dispatcher = require('../dispatcher');
var wspubsub = require('../lib/wspubsub');
var rpc = require('../lib/rpc');


var CsvParse = require('babyparse');

var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');

var pointsWs, pointsWebsocket, devicesWs, devicesWebsocket;

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
    scanForDevices: function (platformUuid, bacnetProxyIdentity, low, high, address, scan_length) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            proxy_identity: bacnetProxyIdentity,
            platform_uuid: platformUuid
        };

        if (low)
        {
            params.low_device_id = Number(low);
        }

        if (high)
        {
            params.high_device_id = Number(high);
        }

        if (address)
        {
            params.target_address = address;
        }

        if (scan_length)
        {
            params.scan_length = scan_length;
        }

        var setUpDevicesSocket = function(platformUuid, bacnetIdentity) {
            var topic = "/vc/ws/" + authorization + "/iam";
            wspubsub.WsPubSub.subscribe(topic, function(topic, message){
                // Special CLOSING method happens when socket is closed.
                if (message === "CLOSING") {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.DEVICE_SCAN_FINISHED
                    });
                }
                else{
                    devicesActionCreators.deviceMessageReceived(message, platformUuid, bacnetIdentity);
                }
            });
        }   

        return new rpc.Exchange({
            method: 'start_bacnet_scan',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.LISTEN_FOR_IAMS,
                    platformUuid: platformUuid,
                    bacnetProxyIdentity: bacnetProxyIdentity,
                    low_device_id: low,
                    high_device_id: high,
                    target_address: address
                });

                setUpDevicesSocket(platformUuid, bacnetProxyIdentity);        
            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to scan for devices. " + error.message + ".";

                handle401(error, error.message);
            });
        
    },
    deviceMessageReceived: function (data, platform, bacnet) {
        
        if (data)
        {
            var device = JSON.parse(data);
            
            var result = checkDevice(device, platform);

            if (!objectIsEmpty(result))
            {            
                if (!objectIsEmpty(result.warning))
                {
                    statusIndicatorActionCreators.openStatusIndicator(
                        "error", 
                        result.warning.message + "ID: " + result.warning.value, 
                        result.warning.value, 
                        "left"
                    );
                }

                if (bacnet)
                {
                    result.device.type = "bacnet";
                    result.device.agentDriver = "platform.driver";
                }

                if (!objectIsEmpty(result.device))
                {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.DEVICE_DETECTED,
                        platform: platform,
                        bacnet: bacnet,
                        device: result.device
                    });
                }
            }
        }
    },
    pointReceived: function (data, platform) {
        dispatcher.dispatch({
            type: ACTION_TYPES.POINT_RECEIVED,
            platform: platform,
            data: data
        });
    },
    cancelDeviceScan: function () {
        if (typeof devicesWs !== "undefined" && devicesWs !== null)
        {
            devicesWs.close();
            devicesWs = null;
        }
    },
    handleKeyDown: function (keydown) {
        dispatcher.dispatch({
            type: ACTION_TYPES.HANDLE_KEY_DOWN,
            keydown: keydown
        });
    },
    focusOnDevice: function (deviceId, address) {
        dispatcher.dispatch({
            type: ACTION_TYPES.FOCUS_ON_DEVICE,
            deviceId: deviceId,
            address: address
        });

        console.log("focused on device");
    },
    configureDevice: function (device, bacnetIdentity) {
        
        var authorization = authorizationStore.getAuthorization();

        var params = {
            // expanded:false, 
            // "filter":[3000124], 
            proxy_identity: bacnetIdentity, 
            platform_uuid: device.platformUuid,
            device_id: Number(device.id), 
            address: device.address
        }

        var setUpPointsSocket = function() {

            var topic = "/vc/ws/" + authorization + "/configure";
            wspubsub.WsPubSub.subscribe(topic, function(topic, message){
                // Special CLOSING method happens when socket is closed.
                if (message === "CLOSING") {
                    dispatcher.dispatch({
                        type: ACTION_TYPES.POINT_SCAN_FINISHED,
                        device: this
                    });
                }
                else{
                    var platform = null;
                    devicesActionCreators.pointReceived(message, platform);
                }
            }.bind(device));

        }

        return new rpc.Exchange({
            method: 'publish_bacnet_props',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                dispatcher.dispatch({
                    type: ACTION_TYPES.CONFIGURE_DEVICE,
                    device: device,
                    bacnet: bacnetIdentity
                });

                setUpPointsSocket();
            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to receive points. " + error.message + ".";

                handle401(error, error.message);
            });

        
    },
    toggleShowPoints: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_SHOW_POINTS,
            device: device
        });
    },
    cancelRegistry: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CANCEL_REGISTRY,
            device: device
        });
    },
    loadRegistryFiles: function (device) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            platform_uuid: device.platformUuid, 
            agent_identity: device.agentDriver
        };

        return new rpc.Exchange({
            method: 'list_agent_configs',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                console.log("list_agent_configs");
                console.log(result);

                dispatcher.dispatch({
                    type: ACTION_TYPES.LOAD_REGISTRY_FILES,
                    registryFiles: result.filter(function (registryFile) {
                        var index = registryFile.indexOf("devices/");

                        return index !== 0;
                    }),
                    deviceId: device.id,
                    deviceAddress: device.address
                });

            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to load saved registry files. " + error.message + ".";

                handle401(error, error.message);
            });
    },
    unloadRegistryFiles: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.UNLOAD_REGISTRY_FILES
        });
    },
    loadRegistryFile: function (registryFile, device) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            platform_uuid: device.platformUuid, 
            agent_identity: device.agentDriver,
            config_name: registryFile
        }

        return new rpc.Exchange({
            method: 'get_agent_config',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                devicesActionCreators.unloadRegistryFiles();

                console.log("get_agent_config");
                console.log(result);

                var csvData = parseCsvFile(result);

                if (csvData.warnings.length)
                {
                    console.log(csvData.warnings[0]);
                }
                
                devicesActionCreators.loadRegistry(
                    device.id, 
                    device.address,
                    csvData.data,
                    registryFile 
                );

            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to load selected registry file. " + error.message + ".";

                handle401(error, error.message);
            });
    },
    loadRegistry: function (deviceId, deviceAddress, csvData, fileName) {
        dispatcher.dispatch({
            type: ACTION_TYPES.LOAD_REGISTRY,
            deviceId: deviceId,
            deviceAddress: deviceAddress,
            data: csvData.filter(function (row) {
                return row.length > 0;
            }),
            file: fileName
        });
    },
    editRegistry: function (device) {
        dispatcher.dispatch({
            type: ACTION_TYPES.EDIT_REGISTRY,
            device: device
        });
    },
    updateRegistry: function (deviceId, deviceAddress, selectedPoints, attributes) {
        dispatcher.dispatch({
            type: ACTION_TYPES.UPDATE_REGISTRY,
            deviceId: deviceId,
            deviceAddress: deviceAddress,
            selectedPoints: selectedPoints,
            attributes: attributes
        });
    },
    saveRegistry: function (device, fileName, values) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            platform_uuid: device.platformUuid, 
            agent_identity: "platform.driver", 
            config_name: fileName,
            config_type: "csv",
            raw_contents: values
        };

        return new rpc.Exchange({
            method: 'store_agent_config',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                dispatcher.dispatch({
                    type: ACTION_TYPES.SAVE_REGISTRY,
                    fileName: fileName,
                    deviceId: device.id,
                    deviceAddress: device.address,
                    data: values
                });

            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to save registry configuration. " + error.message + ".";

                handle401(error, error.message);
            });
        
    },
    saveConfig: function (device, settings) {

        var authorization = authorizationStore.getAuthorization();

        var config_name =  "devices/" +
            settings.campus + "/" + 
            settings.building + "/" + 
            settings.unit + 
            (settings.path ? "/" + settings.path : "")

        var config = {};

        for (var key in settings.config)
        {
            config[key] = (settings.config[key].hasOwnProperty("value") ? settings.config[key].value : settings.config[key]);
        }

        var params = {
            platform_uuid: device.platformUuid, 
            agent_identity: "platform.driver", 
            config_name: config_name,
            config_type: "json",
            raw_contents: JSON.stringify(config)
        };

        return new rpc.Exchange({
            method: 'store_agent_config',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                dispatcher.dispatch({
                    type: ACTION_TYPES.SAVE_CONFIG,
                    settings: settings
                });

            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to save device configuration. " + error.message + ".";

                handle401(error, error.message);
            });
        
    },
};

function checkDevice(device, platformUuid) 
{
    var result = {};

    if (device.hasOwnProperty("device_id") && !device.hasOwnProperty("results"))
    {
        result = {
            device: {},
            warning: {}
        }

        var deviceIdStr = device.device_id.toString();
        var addDevice = true;

        var alreadyInList = devicesStore.getDeviceByID(deviceIdStr);

        if (alreadyInList)
        {
            if (alreadyInList.address !== device.address)
            {
                // If there are multiple devices with same ID, see if there's another one
                // with this same address
                var sameDevice = devicesStore.getDeviceRef(deviceIdStr, device.address);

                if (sameDevice)
                {
                    addDevice = false;
                }
                else
                {
                    result.warning = { 
                        key: "duplicate_id", 
                        message: "Duplicate device IDs found. Your network may not be set up correctly. ",
                        value: deviceIdStr 
                    };
                }                
            }
            else // Same ID and same address means the device is already in the list, so don't add it
            {
                addDevice = false;
            }
        }
        
        if (addDevice) 
        {
            result.device = device;
        }
    }

    return result;
}

var parseCsvFile = (contents) => {

    var results = CsvParse.parse(contents);

    var registryValues = [];

    var header = [];

    var data = results.data;

    results.warnings = [];

    if (data.length)
    {
        header = data.slice(0, 1);
    }

    var template = [];

    if (header[0].length)
    {
        header[0].forEach(function (column) {
            template.push({ "key": column.replace(/ /g, "_"), "value": null, "label": column });
        });

        var templateLength = template.length;

        if (data.length > 1)
        {
            var rows = data.slice(1);

            var rowsCount = rows.length;

            rows.forEach(function (r, num) {

                if (r.length)
                {   
                    if (r.length !== templateLength) 
                    {                           
                        if ((num === (rowsCount - 1)) && (r.length === 0 || ((r.length === 1) && (r[0] === "") )))
                        {
                            // Suppress the warning message if the out-of-sync row is the last one and it has no elements
                            // or all it has is an empty point name -- which can happen naturally when reading the csv file
                        }
                        else
                        {
                            results.warnings.push({ message: "Row " +  num + " was omitted for having the wrong number of columns."});
                        }
                    }
                    else
                    {
                        if (r.length === templateLength) // Have to check again, to keep from adding the empty point name
                        {                                // in the last row
                            var newTemplate = JSON.parse(JSON.stringify(template));

                            var newRow = [];

                            r.forEach( function (value, i) {
                                newTemplate[i].value = value;

                                newRow.push(newTemplate[i]);
                            });

                            registryValues.push(newRow);
                        }
                    }
                }
            });
        }
        else
        {
            registryValues = template;
        }
    }

    results.data = registryValues;

    return results;
}

function objectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

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