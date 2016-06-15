'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var devicesStore = new Store();

var _action = "get_scan_settings";
var _view = "Detect Devices";
var _device = null;
var _data = {};
var _backupData = {};
var _registryFiles = {};
var _backupFileName = {};
var _platform;

var _placeHolders = [ [
    {"key": "Point_Name", "value": "", "editable": true},
    {"key": "Volttron_Point_Name", "value": ""},
    {"key": "Units", "value": ""},
    {"key": "Units_Details", "value": "" },
    {"key": "Writable", "value": "" },
    {"key": "Starting_Value", "value": "" },
    {"key": "Type", "value": "" },
    {"key": "Notes", "value": "" }
] ];


devicesStore.getState = function () {
    return { action: _action, view: _view, device: _device, platform: _platform };
};

devicesStore.getFilteredRegistryValues = function (device, filterStr) {

    return _data[device.deviceId].filter(function (item) {
        var pointName = item.find(function (pair) {
            return pair.key === "Point_Name";
        })

        return (pointName ? (pointName.value.trim().toUpperCase().indexOf(filterStr.trim().toUpperCase()) > -1) : false);
    });
}

devicesStore.getRegistryValues = function (device) {

    return (_data[device.deviceId].length ? 
                JSON.parse(JSON.stringify(_data[device.deviceId])) : 
                    JSON.parse(JSON.stringify(_placeHolders)));
    
};

devicesStore.getDataLoaded = function (device) {
    return ( (_data.hasOwnProperty(device.deviceId) && 
                (_data.hasOwnProperty(device.deviceId))) ? _data[device.deviceId].length : false);
};

devicesStore.getRegistryFile = function (device) {

    return (_registryFiles.hasOwnProperty(device.deviceId) &&
                _data.hasOwnProperty(device.deviceId) &&
                _data[device.deviceId].length ? _registryFiles[device.deviceId] : "");
    
};

devicesStore.getDevices = function (platform) {
    return [
            [ 
                { key: "address", label: "Address", value: "Address 192.168.1.42" }, 
                { key: "deviceId", label: "Device ID", value: "548" }, 
                { key: "description", label: "Description", value: "Temperature sensor" }, 
                { key: "vendorId", label: "Vendor ID", value: "18" }, 
                { key: "vendor", label: "Vendor", value: "Siemens" },
                { key: "type", label: "Type", value: "BACnet" }
            ],
            [ 
                { key: "address", label: "Address", value: "RemoteStation 1002:11" }, 
                { key: "deviceId", label: "Device ID", value: "33" }, 
                { key: "description", label: "Description", value: "Actuator 3-pt for zone control" }, 
                { key: "vendorId", label: "Vendor ID", value: "12" }, 
                { key: "vendor", label: "Vendor", value: "Alerton" },
                { key: "type", label: "Type", value: "BACnet" }
            ]
        ];
}

devicesStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.CONFIGURE_DEVICES:
            _platform = action.platform;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.ADD_DEVICES:
        case ACTION_TYPES.CANCEL_SCANNING:
            _action = "get_scan_settings";
            _view = "Detect Devices";
            _device = null;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.SCAN_FOR_DEVICES:
            _action = "start_scan";
            _view = "Detect Devices";
            _device = null;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.LIST_DETECTED_DEVICES:
            _action = "show_new_devices";
            _view = "Configure Devices";
            _device = null;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.CONFIGURE_DEVICE:
            _action = "configure_device";
            _view = "Configure Device";
            _device = action.device;
            devicesStore.emitChange();
        case ACTION_TYPES.CANCEL_REGISTRY:
            _action = "configure_device";
            _view = "Configure Device";
            _device = action.device;
            _data[_device.deviceId] = (_backupData.hasOwnProperty(_device.deviceId) ? JSON.parse(JSON.stringify(_backupData[_device.deviceId])) : []);
            _registryFiles[_device.deviceId] = (_backupFileName.hasOwnProperty(_device.deviceId) ? _backupFileName[_device.deviceId] : "");
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.LOAD_REGISTRY:
            _action = "configure_registry";
            _view = "Registry Configuration";
            _device = action.device;
            _backupData[_device.deviceId] = (_data.hasOwnProperty(_device.deviceId) ? JSON.parse(JSON.stringify(_data[_device.deviceId])) : []);
            _backupFileName[_device.deviceId] = (_registryFiles.hasOwnProperty(_device.deviceId) ? _registryFiles[_device.deviceId] : "");
            _data[_device.deviceId] = JSON.parse(JSON.stringify(action.data));
            _registryFiles[_device.deviceId] = action.file;             
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.EDIT_REGISTRY:
            _action = "configure_registry";
            _view = "Registry Configuration";
            _device = action.device;  
            _backupData[_device.deviceId] = (_data.hasOwnProperty(_device.deviceId) ? JSON.parse(JSON.stringify(_data[_device.deviceId])) : []);                      
            _backupFileName[_device.deviceId] = (_registryFiles.hasOwnProperty(_device.deviceId) ? _registryFiles[_device.deviceId] : "");
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.GENERATE_REGISTRY:
            _action = "configure_registry";
            _view = "Registry Configuration";
            _device = action.device;
            _backupData[_device.deviceId] = (_data.hasOwnProperty(_device.deviceId) ? JSON.parse(JSON.stringify(_data[_device.deviceId])) : []);
            _backupFileName[_device.deviceId] = (_registryFiles.hasOwnProperty(_device.deviceId) ? _registryFiles[_device.deviceId] : "");
            _data[_device.deviceId] = [];
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.SAVE_REGISTRY:
            _action = "configure_device";
            _view = "Configure Device";
            _device = action.device;
            _data[_device.deviceId] = JSON.parse(JSON.stringify(action.data));
            devicesStore.emitChange();
            break;
    }
});

module.exports = devicesStore;