'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var devicesStore = require('../stores/devices-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

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

            var endpoint = (window.location.protocol === "https:" ? "wss://" : "ws://");
            devicesWebsocket = endpoint + window.location.host + "/vc/ws/" + authorization + "/iam";

            if (window.WebSocket) {
                devicesWs = new WebSocket(devicesWebsocket);
            }
            else if (window.MozWebSocket) {
                devicesWs = MozWebSocket(devicesWebsocket);
            }

            devicesWs.onmessage = function(evt)
            {
                devicesActionCreators.deviceMessageReceived(evt.data, platformUuid, bacnetIdentity);
            };

            devicesWs.onclose = function (evt) 
            {
                dispatcher.dispatch({
                    type: ACTION_TYPES.DEVICE_SCAN_FINISHED
                });
            };
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
        
            var endpoint = (window.location.protocol === "https:" ? "wss://" : "ws://");
            pointsWebsocket = endpoint + window.location.host + "/vc/ws/" + authorization + "/configure";

            if (window.WebSocket) {
                pointsWs = new WebSocket(pointsWebsocket);
            }
            else if (window.MozWebSocket) {
                pointsWs = MozWebSocket(pointsWebsocket);
            }

            pointsWs.onmessage = function(evt)
            {
                var platform = null;

                devicesActionCreators.pointReceived(evt.data, platform);
            };

            pointsWs.onclose = function (evt)
            {
                dispatcher.dispatch({
                    type: ACTION_TYPES.POINT_SCAN_FINISHED,
                    device: this
                });
            }.bind(device);
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
            agent_identity: device.bacnetProxyIdentity
        };

        return new rpc.Exchange({
            method: 'list_agent_configs',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                console.log("list_agent_configs");
                console.log(result);

                result = [
                    { name: "file1" },
                    { name: "file2" },
                    { name: "file3" },
                    { name: "file4" },
                    { name: "file5" },
                ];

                dispatcher.dispatch({
                    type: ACTION_TYPES.LOAD_REGISTRY_FILES,
                    registryFiles: result,
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
            agent_identity: device.bacnetProxyIdentity,
            config_name: registryFile
        }

        return new rpc.Exchange({
            method: 'get_agent_config',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                console.log("get_agent_config");
                console.log(result);

                devicesActionCreators.unloadRegistryFiles();

                devicesActionCreators.loadRegistry(
                    device.id, 
                    device.address,
                    result,
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


        var config_name =  settings.campus + "/" + 
                settings.building + "/" + 
                settings.unit + 
                (settings.path ? + "/" + settings.path : "")

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