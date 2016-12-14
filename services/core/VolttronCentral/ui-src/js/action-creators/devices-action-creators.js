'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var devicesStore = require('../stores/devices-store');
var dispatcher = require('../dispatcher');
var wspubsub = require('../lib/wspubsub');
var rpc = require('../lib/rpc');


import {CsvParse} from '../lib/csvparse';

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
                    if (result.device.hasOwnProperty("device_id"))
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
        }
    },
    pointReceived: function (data) {
        dispatcher.dispatch({
            type: ACTION_TYPES.POINT_RECEIVED,
            data: data
        });
    },
    cancelDeviceScan: function () {
        var authorization = authorizationStore.getAuthorization();
        var topic = "/vc/ws/" + authorization + "/iam";

        wspubsub.WsPubSub.unsubscribe(topic);
    },
    handleKeyDown: function (keydown) {
        dispatcher.dispatch({
            type: ACTION_TYPES.HANDLE_KEY_DOWN,
            keydown: keydown
        });
    },
    focusOnDevice: function (deviceId, deviceAddress) {
        dispatcher.dispatch({
            type: ACTION_TYPES.FOCUS_ON_DEVICE,
            deviceId: deviceId,
            deviceAddress: deviceAddress
        });
    },
    refreshDevicePoints: function (deviceId, deviceAddress) {
        dispatcher.dispatch({
            type: ACTION_TYPES.REFRESH_DEVICE_POINTS,
            deviceId: deviceId,
            deviceAddress: deviceAddress
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLOSE_MODAL,
        });
    },
    configureDevice: function (device, bacnetIdentity) {
        
        var authorization = authorizationStore.getAuthorization();

        var params = {
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

                    console.log("closing points socket");
                }
                else{
                    var platform = null;
                    devicesActionCreators.pointReceived(message);
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
    reconfigureDevice: function (devicePath, platformUuid) {

        var deviceName = devicePath.replace(/_/g, "/" );
        var agentDriver = "platform.driver";

        devicesActionCreators.listConfigs(
            platformUuid, 
            agentDriver, 
            deviceName, 
            devicesActionCreators.getDeviceConfig
        );

    },
    listConfigs: function (platformUuid, agentDriver, deviceName, callback) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            platform_uuid: platformUuid, 
            agent_identity: agentDriver
        };

        return new rpc.Exchange({
            method: 'list_agent_configs',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {
                callback(platformUuid, agentDriver, deviceName, result);
            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to list agent configuration files. " + error.message + ".";

                handle401(error, error.message);
            });
    },
    getDeviceConfig: function (platformUuid, agentDriver, deviceName, result) {

        var deviceConfig = result.find(function (registryFile) {
            var index = registryFile.replace(/_/g, "\/").indexOf(deviceName);

            return index === 0;
        });

        if (typeof deviceConfig !== "undefined")
        {
            devicesActionCreators.getAgentConfig(
                platformUuid, 
                agentDriver,
                deviceName,
                deviceConfig, 
                devicesActionCreators.getRegistryConfig
            );
        }
    },
    getRegistryConfig: function (platformUuid, agentDriver, deviceName, deviceConfig, result) {

        var deviceConfiguration = JSON.parse(result);
        var registryConfig = deviceConfiguration.registry_config.replace("config://", "");
            
        var reloadRegistryFile = function (platform_uuid, agent_driver, device_name, registry_config, result)
        {
            deviceConfiguration.registryFile = registry_config;

            devicesActionCreators.loadRegistryFile(
                platform_uuid, 
                agent_driver, 
                device_name,
                deviceConfiguration,
                devicesActionCreators.editConfigFiles
            );
        }

        devicesActionCreators.getAgentConfig(
            platformUuid, 
            agentDriver,
            deviceName,
            registryConfig, 
            reloadRegistryFile
        );
    },
    getAgentConfig: function (platformUuid, agentDriver, deviceName, configFile, callback) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            platform_uuid: platformUuid, 
            agent_identity: agentDriver,
            config_name: configFile
        }

        return new rpc.Exchange({
            method: 'get_agent_config',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                callback(platformUuid, agentDriver, deviceName, configFile, result);

            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to retrieve configuration file: " + deviceConfig + ". " + error.message + ".";

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
    loadRegistryFile: function (platformUuid, agentDriver, deviceName, configuration, callback) {

        var authorization = authorizationStore.getAuthorization();

        var params = {
            platform_uuid: platformUuid, 
            agent_identity: agentDriver,
            config_name: configuration.registryFile
        }

        return new rpc.Exchange({
            method: 'get_agent_config',
            authorization: authorization,
            params: params,
        }).promise
            .then(function (result) {

                var csvData = CsvParse.parseCsvFile(result);

                if (csvData.warnings.length)
                {
                    console.log(csvData.warnings[0]);
                }

                if (typeof callback === "function")
                {
                    callback(
                        platformUuid,
                        agentDriver,
                        deviceName,
                        configuration, 
                        csvData.data
                    );
                }
                else // There's not a callback function when called from
                {       // RegistryFilesSelector component

                    devicesActionCreators.unloadRegistryFiles();
                    
                    devicesActionCreators.loadRegistry(
                        configuration.deviceId, 
                        configuration.deviceAddress,
                        csvData.data,
                        configuration.registryFile 
                    );
                }

            })
            .catch(rpc.Error, function (error) {

                error.message = "Unable to load selected registry file. " + error.message + ".";

                handle401(error, error.message);
            });
    },
    editConfigFiles: function (platformUuid, agentDriver, deviceName, configuration, csvData) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECONFIGURE_DEVICE,
            platformUuid: platformUuid,
            agentDriver: agentDriver,
            deviceName: deviceName,
            configuration: configuration,
            data: csvData.filter(function (row) {
                return row.length > 0;
            })
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
    updateRegistry: function (deviceId, deviceAddress, attributes) {
        dispatcher.dispatch({
            type: ACTION_TYPES.UPDATE_REGISTRY,
            deviceId: deviceId,
            deviceAddress: deviceAddress,
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