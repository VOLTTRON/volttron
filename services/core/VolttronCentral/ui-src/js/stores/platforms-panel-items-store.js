'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _pointsOrder = 0;
var _devicesOrder = 1;
var _buildingsOrder = 2;
var _agentsOrder = 3;

var _items = {
    "platforms": {}
};

var _expanded = false;
var _itemTypes = ["platforms", "buildings", "agents", "devices", "points"];

var _badLabel = "Unhealthy";
var _goodLabel = "Healthy";
var _unknownLabel = "Unknown Status";

var _loadingDataComplete = true;

var platformsPanelItemsStore = new Store();

platformsPanelItemsStore.getItem = function (itemPath)
{
    var itemsList = [];
    var item = _items;
    
    for (var i = 0; i < itemPath.length; i++)
    {
        if (item.hasOwnProperty(itemPath[i]))
        {
            item = item[itemPath[i]];
        }
    }

    return item;
}  

platformsPanelItemsStore.getChildren = function (parent, parentPath) {

    var itemsList = [];
    var item = _items;

    if (parentPath !== null) // for everything but the top level, drill down to the parent
    {
        for (var i = 0; i < parentPath.length; i++)
        {
            if (item.hasOwnProperty(parentPath[i]))
            {
                item = item[parentPath[i]];
            }
        }
    
          
        for (var i = 0; i < item.children.length; i++)
        {           
            itemsList.push(item[item.children[i]]);
        }
            
    }
    else
    {
        for (var key in item[parent])
        {
            itemsList.push(item[parent][key]);
        }
    } 

    return itemsList;
};

platformsPanelItemsStore.loadFilteredItems = function (filterTerm, filterStatus) {

    var filterItems = function (parent, filterTerm, filterStatus) {

        var notAMatch;
        var compareTerm;

        if (filterTerm === "")
        {
            notAMatch = function (parent, filterStatus)
            {
                if (parent.hasOwnProperty("status"))
                {
                    return (parent.status !== filterStatus);                
                }
                else
                {
                    return (filterStatus !== "UNKNOWN");
                }
            }

            compareTerm = filterStatus;
        }
        else if (filterStatus === "")
        {
            notAMatch = function (parent, filterTerm)
            {
                var upperParent = parent.name.toUpperCase();;
                var filterStr = filterTerm;

                var filterParts = filterTerm.split(" ");
                var foundColon = (filterParts[0].indexOf(":") > -1);

                if (foundColon)
                {
                    var index = filterTerm.indexOf(":");
                    var filterKey = filterTerm.substring(0, index);
                    filterStr = filterTerm.substring(index + 1);

                    if (parent.hasOwnProperty(filterKey))
                    {
                        upperParent = parent[filterKey].toUpperCase();    
                    }
                    else
                    {
                        return true;
                    }
                }               

                return (upperParent.trim().indexOf(filterStr.trim().toUpperCase()) < 0);
            }

            compareTerm = filterTerm;
        }

        if (parent.children.length === 0)
        {
            parent.visible = !notAMatch(parent, compareTerm);
            parent.expanded = null;

            return parent;
        }
        else
        {
            var childrenToHide = 0;

            for (var i = 0; i < parent.children.length; i++)
            {
                var childString = parent.children[i];
                var filteredChild = filterItems(parent[childString], filterTerm, filterStatus);

                if (!filteredChild.visible)
                {
                    ++childrenToHide;
                }
            }
            
            if (childrenToHide === parent.children.length)
            {
                parent.visible = !notAMatch(parent, compareTerm);
                parent.expanded = false;
            }
            else
            {
                parent.visible = true;
                parent.expanded = true;
            }        

            return parent;
        }
    }

    for (var key in _items.platforms)
    {
        if (filterTerm !== "" || filterStatus !== "")
        {
            filterItems(_items.platforms[key], filterTerm, filterStatus);
        }
        else
        {
            expandAllChildren(_items.platforms[key], false);
            _items.platforms[key].visible = true;
        }        
    }

}

var expandAllChildren = function (parent, expanded) {
    
    for (var i = 0; i < parent.children.length; i++)
    {
        var childString = parent.children[i];
        expandAllChildren(parent[childString], expanded);
    }

    if (parent.children.length > 0)
    {
        parent.expanded = expanded;
    }
    else
    {
        parent.expanded = null;
    }

    parent.visible = true;
};


platformsPanelItemsStore.getExpanded = function () {
    return _expanded;
};

platformsPanelItemsStore.getLoadingComplete = function () {
    return _loadingDataComplete;
};

platformsPanelItemsStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.FILTER_ITEMS:

            var filterTerm = action.filterTerm;
            var filterStatus = action.filterStatus;
            platformsPanelItemsStore.loadFilteredItems(filterTerm, filterStatus);

            platformsPanelItemsStore.emitChange();

            break;
        case ACTION_TYPES.EXPAND_ALL:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            
            var expanded = (item.expanded !== null ? !item.expanded : true);

            expandAllChildren(item, expanded);

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.TOGGLE_ITEM:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            item.expanded = !item.expanded;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.CHECK_ITEM:

            var item = platformsPanelItemsStore.getItem(action.itemPath);
            item.checked = action.checked;

            platformsPanelItemsStore.emitChange();

            break;

        case ACTION_TYPES.START_LOADING_DATA:

            _loadingDataComplete = false;

            break;

        case ACTION_TYPES.RECEIVE_PLATFORM_STATUSES:
            
            var platforms = action.platforms;

            platforms.forEach(function (platform)
            {
                _items["platforms"][platform.uuid] = platform; 
                
                var platformItem = _items["platforms"][platform.uuid];
                platformItem.path = ["platforms", platform.uuid];

                platformItem.status = platform.health.status.toUpperCase();
                platformItem.statusLabel = getStatusLabel(platformItem.status);
                platformItem.context = platform.health.context;
                platformItem.children = [];
                platformItem.type = "platform";
                platformItem.visible = true;
                platformItem.expanded = null;
                // platformItem.name = (platform.name === null ? platform.uuid : platform.name);

                // loadAgents(platform);                
                // loadDevices(platform);
            });

            var platformsToRemove = [];

            for (var key in _items.platforms)
            {
                var match = platforms.find(function (platform) {
                    return key === platform.uuid;
                });

                if (!match)
                {
                    platformsToRemove.push(key);
                }
            }

            platformsToRemove.forEach(function (uuid) {
                delete _items.platforms[uuid];
            });            
            
            platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.agents.length > 0)
            {
                insertAgents(platform, action.agents);
            }

            // platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_DEVICE_STATUSES:

            var platform = _items["platforms"][action.platform.uuid];

            if (action.devices.length > 0)
            {
                insertDevices(platform, action.devices);
            }

            // platformsPanelItemsStore.emitChange();
            break;
        case ACTION_TYPES.RECEIVE_PERFORMANCE_STATS:
            
            switch (action.parent.type)
            {
                case "platform":
            
                    var platform = _items["platforms"][action.parent.uuid];

                    if (action.points.length > 0)
                    {
                        platform.expanded = true;
                        platform.points = {};
                        platform.points.path = platform.path.slice(0);
                        platform.points.path.push("points");
                        platform.points.name = "Performance";
                        platform.points.expanded = false;
                        platform.points.visible = true;
                        platform.points.children = [];
                        platform.points.type = "type";
                        platform.points.status = platform.status;
                        platform.points.statusLabel = getStatusLabel(platform.status);
                        platform.points.sortOrder = _pointsOrder;

                        if (platform.children.indexOf("points") < 0)
                        {
                            platform.children.push("points");
                        }

                        action.points.forEach(function (point)
                        {
                            //TODO: add UUID to points rpc?

                            var pointProps = point;
                            pointProps.expanded = false;
                            pointProps.visible = true;
                            pointProps.path = platform.points.path.slice(0);

                            var uuid = (point.hasOwnProperty("topic") ? point.topic : point.uuid);
                            
                            pointProps.uuid = uuid;
                            pointProps.path.push(uuid);
                            pointProps.topic = point.topic;

                            pointProps.parentPath = getParentPath(platform);
                            
                            pointProps.parentType = platform.type;
                            pointProps.parentUuid = platform.uuid;

                            point.status = platform.status;
                            point.statusLabel = getStatusLabel(platform.status);
                            pointProps.children = [];
                            pointProps.type = "point";
                            pointProps.sortOrder = 0;
                            platform.points.children.push(uuid); 
                            platform.points[uuid] = pointProps;
                        });

                    }

                    break;
            }

            _loadingDataComplete = true;

            platformsPanelItemsStore.emitChange();
            break;
    }

    function insertAgents(platform, agents)
    {
        var agentsToInsert = JSON.parse(JSON.stringify(agents));

        platform.agents = {};
        platform.agents.path = JSON.parse(JSON.stringify(platform.path));
        platform.agents.path.push("agents");
        platform.agents.name = "Agents";
        platform.agents.expanded = false;
        platform.agents.visible = true;
        platform.agents.children = [];
        platform.agents.type = "type";
        platform.agents.sortOrder = _agentsOrder;

        if (platform.children.indexOf("agents") < 0)
        {
            platform.children.push("agents");
        }

        var agentsHealth;

        agentsToInsert.forEach(function (agent)
        {
            var agentProps = agent;
            agentProps.expanded = false;
            agentProps.visible = true;
            agentProps.path = JSON.parse(JSON.stringify(platform.agents.path));
            agentProps.path.push(agent.uuid);
            agentProps.status = agent.health.status.toUpperCase();
            agentProps.statusLabel = getStatusLabel(agentProps.status);
            agentProps.context = agent.health.context;
            agentProps.children = [];
            agentProps.type = "agent";
            agentProps.sortOrder = 0;
            platform.agents.children.push(agent.uuid); 
            platform.agents[agent.uuid] = agentProps;

            agentsHealth = checkStatuses(agentsHealth, agentProps);
        });

        platform.agents.status = agentsHealth;
        platform.agents.statusLabel = getStatusLabel(agentsHealth);
    }

    // function loadAgents(platform)
    // {
    //     if (platform.agents)
    //     {
    //         if (platform.agents.length > 0)
    //         {
    //             insertAgents(platform, platform.agents);
    //         }
    //         else
    //         {
    //             delete platform.agents;
    //         }
    //     }
    // }

    function insertBuilding(platform, uuid, name)
    {
        if (platform.children.indexOf("buildings") < 0)
        {
            platform.children.push("buildings");

            platform.buildings = {};
            platform.buildings.name = "Buildings";
            platform.buildings.children = [];
            platform.buildings.path = JSON.parse(JSON.stringify(platform.path));
            platform.buildings.path.push("buildings");
            platform.buildings.expanded = false;
            platform.buildings.visible = true;
            platform.buildings.type = "type";
            platform.buildings.sortOrder = _buildingsOrder;
        }

        if (!platform.buildings.hasOwnProperty(uuid))
        {
            var buildingProps = {};
            buildingProps.name = name;
            buildingProps.uuid = uuid;

            buildingProps.expanded = false;
            buildingProps.visible = true;
            buildingProps.path = JSON.parse(JSON.stringify(platform.buildings.path));
            buildingProps.path.push(buildingProps.uuid);
            buildingProps.status = "UNKNOWN";
            buildingProps.statusLabel = getStatusLabel(buildingProps.status);
            buildingProps.children = ["devices"];
            buildingProps.type = "building";
            buildingProps.sortOrder = 0;          

            buildingProps.devices = {};
            buildingProps.devices.path = JSON.parse(JSON.stringify(buildingProps.path));
            buildingProps.devices.path.push("devices");
            buildingProps.devices.name = "Devices";
            buildingProps.devices.expanded = false;
            buildingProps.devices.visible = true;
            buildingProps.devices.children = [];
            buildingProps.devices.type = "type";
            buildingProps.devices.sortOrder = _devicesOrder;


            //TODO: add building points
            // buildingProps.children.push("points");
            // buildingProps.points = [];

            platform.buildings.children.push(buildingProps.uuid);
            platform.buildings[buildingProps.uuid] = buildingProps;            
        }

        return platform.buildings[uuid];
    }

    function insertDevices(platform, devices)
    {
        var devicesToInsert = JSON.parse(JSON.stringify(devices));

        var buildings = [];

        if (devicesToInsert.length > 0)
        {
            //Make a 2D array where each row is another level 
            // of devices and subdevices in the tree
            var nestedDevices = [];
            var level = 3;
            var deviceCount = 0;

            while (deviceCount < devicesToInsert.length)
            {
                var levelList = [];

                devicesToInsert.forEach(function (device) {

                    var deviceParts = device.path.split("/");

                    if (deviceParts.length === level)
                    {
                        levelList.push(device);
                        ++deviceCount;
                    }
                });

                if (levelList.length > 0)
                {
                    nestedDevices.push(levelList);
                }

                ++level;
            }
        }

        //Now we can add each row of devices, confident
        // that any parent devices will be added to the tree
        // before their subdevices
        nestedDevices.forEach(function (level, row) {

            level.forEach(function (device) {
                
                var pathParts = device.path.split("/");
                var buildingUuid = pathParts[0] + "_" + pathParts[1];
                var buildingName = pathParts[1];
                var legendInfo = pathParts[0] + " > " + buildingName;                

                var building = insertBuilding(platform, buildingUuid, buildingName);                

                insertDevice(device, building, legendInfo, row);

                var alreadyInTree = buildings.find(function (building) {
                    return building.uuid === buildingUuid;
                });

                if (!alreadyInTree) {
                    buildings.push(building);
                }

            });
        });

        buildings.forEach(function (blg) {
            
            var buildingHealth;

            blg.devices.children.forEach(function (device) {
                buildingHealth = checkStatuses(buildingHealth, blg.devices[device]);                
            });

            blg.devices.status = buildingHealth;   
            blg.devices.statusLabel = getStatusLabel(buildingHealth);

            blg.status = buildingHealth;
            blg.statusLabel = getStatusLabel(buildingHealth);
        });

        
        var buildingsHealth;

        buildings.forEach(function (blg) {
            buildingsHealth = checkStatuses(buildingsHealth, blg);            
        });

        platform.buildings.status = buildingsHealth;
        platform.buildings.statusLabel = getStatusLabel(buildingsHealth);
    }

    function insertDevice(device, building, legendInfo, row)
    {        
        switch (row)
        {
            case 0:
                //top-level devices

                var deviceParts = device.path.split("/");

                var deviceProps = {};
                deviceProps.name = deviceParts[deviceParts.length - 1];
                deviceProps.uuid = device.path.replace(/\//g, '_');
                deviceProps.expanded = false;
                deviceProps.visible = true;
                deviceProps.path = JSON.parse(JSON.stringify(building.devices.path));
                deviceProps.path.push(deviceProps.uuid);
                deviceProps.status = device.health.status.toUpperCase();
                deviceProps.statusLabel = getStatusLabel(deviceProps.health);
                deviceProps.context = device.health.context;
                deviceProps.children = [];
                deviceProps.type = "device";
                deviceProps.sortOrder = 0;

                deviceProps.legendInfo = legendInfo + " > " + deviceProps.name;

                checkForPoints(deviceProps, device);

                building.devices.children.push(deviceProps.uuid);
                building.devices[deviceProps.uuid] = deviceProps;

                break;
            default:
                //subdevices:
                var deviceParts = device.path.split("/");

                var subDeviceLevel = deviceParts.length - 1;

                // the top two spots in the device path are the campus and building,
                // so add 2 to the row and that should equal the subdevice's level
                if (subDeviceLevel !== row + 2)
                {
                    console.log("wrong level number");
                }
                else
                {
                    //Now find the subdevice's parent device by using the parts of its path
                    // to walk the tree
                    var parentPath = JSON.parse(JSON.stringify(building.path));
                    var parentDevice = building; // start at the building
                    var currentLevel = 2; // the level of the top-level devices

                    while (currentLevel < subDeviceLevel)
                    {
                        parentDevice = parentDevice.devices;
                        parentDevice = parentDevice[deviceParts[currentLevel]];
                        ++currentLevel;
                    }

                    //We're now at the parent device. If we haven't added any
                    // subdevices to it yet, initialize its "devices" child
                    if (parentDevice.children.indexOf("devices") < 0)
                    {
                        parentDevice.children.push("devices");

                        parentDevice.devices = {};
                        parentDevice.devices.path = JSON.parse(JSON.stringify(parentDevice.path));
                        parentDevice.devices.path.push("devices");
                        parentDevice.devices.name = "Devices";
                        parentDevice.devices.expanded = false;
                        parentDevice.devices.visible = true;
                        parentDevice.devices.children = [];
                        parentDevice.devices.type = "type";
                        parentDevice.devices.sortOrder = _devicesOrder;
                    }

                    var deviceProps = {};
                    deviceProps.name = deviceParts[subDeviceLevel];
                    deviceProps.uuid = device.path.replace(/ \/ /g, '_');
                    deviceProps.expanded = false;
                    deviceProps.visible = true;
                    deviceProps.path = JSON.parse(JSON.stringify(parentDevice.devices.path));
                    deviceProps.path.push(deviceProps.uuid);
                    deviceProps.status = parentDevice.status;
                    deviceProps.statusLabel = getStatusLabel(deviceProps.status);
                    deviceProps.context = parentDevice.context;
                    deviceProps.children = [];
                    deviceProps.type = "device";
                    deviceProps.sortOrder = 0;

                    deviceProps.legendInfo = parentDevice.legendInfo + " > " + deviceProps.name;

                    checkForPoints(deviceProps, device, building.name, campus);

                    parentDevice.devices.children.push(deviceProps.uuid);
                    parentDevice.devices[deviceProps.uuid] = deviceProps;  

                }
              
                break;
        }
    }

    function checkForPoints(item, data)
    {
        if (data.hasOwnProperty("points"))
        {
            if (item.children.indexOf("points") < 0)
            {
                item.children.push("points");

                item.points = {};
                item.points.path = JSON.parse(JSON.stringify(item.path));
                item.points.path.push("points");
                item.points.name = "Points";
                item.points.expanded = false;
                item.points.visible = true;
                item.points.status = item.status;
                item.points.statusLabel = getStatusLabel(item.status);
                item.points.children = [];
                item.points.type = "type";
                item.points.sortOrder = _pointsOrder;
            }

            data.points.forEach(function (pointName) {

                var pointPath = data.path + "/" + pointName;                
                var platformUuid = item.path[1];

                var pointProps = {}; 
                pointProps.topic = pointPath;  
                pointProps.name = pointName;
                pointProps.uuid = pointPath.replace(/\//g, '_');
                pointProps.expanded = false;
                pointProps.visible = true;
                pointProps.path = JSON.parse(JSON.stringify(item.points.path));
                pointProps.path.push(pointProps.uuid);
                pointProps.parentPath = item.legendInfo;
                pointProps.parentType = item.type;
                pointProps.parentUuid = platformUuid;
                pointProps.status = item.status;
                pointProps.statusLabel = getStatusLabel(item.status);
                pointProps.context = item.context;
                pointProps.children = [];
                pointProps.type = "point";
                pointProps.sortOrder = 0;

                item.points.children.push(pointProps.uuid);
                item.points[pointProps.uuid] = pointProps;

            });
        }
    }

    // function loadDevices(platform)
    // {
    //     // var platform = _items["platforms"][action.platform.uuid];
        
    //     if (platform.devices)
    //     {
    //         if (platform.devices.length > 0)
    //         {
    //             // var agents = [];

    //             // platform.agents.forEach(function (agent)) {
    //             //     agents.push(agent);
    //             // }

    //             // platform.expanded = true;
    //             // platform.agents = {};
    //             // platform.agents.path = platform.path.slice(0);
    //             // platform.agents.path.push("agents");
    //             // platform.agents.name = "Agents";
    //             // platform.agents.expanded = false;
    //             // platform.agents.visible = true;
    //             // platform.agents.children = [];
    //             // platform.agents.type = "type";
    //             // platform.agents.sortOrder = _agentsOrder;

    //             // if (platform.children.indexOf("agents") < 0)
    //             // {
    //             //     platform.children.push("agents");
    //             // }

    //             // agents.forEach(function (agent)
    //             // {
    //             //     var agentProps = agent;
    //             //     agentProps.expanded = false;
    //             //     agentProps.visible = true;
    //             //     agentProps.path = platform.agents.path.slice(0);
    //             //     agentProps.path.push(agent.uuid);
    //             //     // agent.status = "GOOD";
    //             //     agentProps.children = [];
    //             //     agentProps.type = "agent";
    //             //     agentProps.sortOrder = 0;
    //             //     platform.agents.children.push(agent.uuid); 
    //             //     platform.agents[agent.uuid] = agentProps;
    //             // });

    //         }
    //         else
    //         {
    //             delete platform.devices;
    //         }
    //     }
    // }

    function getParentPath(parent)
    {
        var path = parent.path;

        var pathParts = [];

        var item = _items;

        path.forEach(function (part) {
            item = item[part];
            if (_itemTypes.indexOf(part) < 0)
            {
                pathParts.push(item.name);
            } 
        });

        var pathStr = pathParts.join(" > ");

        return pathStr;
    }

    function checkStatuses(health, item)
    {
        if (typeof health === "undefined")
        {
            health = item.status;
        }
        else
        {
            switch (health)
            {
                case "UNKNOWN":

                    switch (item.status)
                    {
                        case "BAD":
                            health = "BAD";
                            break;
                    }
                    break;
                case "GOOD":
                    health = item.status;
            }
        }

        return health;
    }

    function getStatusLabel(status)
    {
        var statusLabel;

        switch (status)
        {
            case "GOOD":
                statusLabel = _goodLabel;
                break;
            case "BAD":
                statusLabel = _badLabel;
                break;
            case "UNKNOWN":
                statusLabel = _unknownLabel;
                break;
        }

        return statusLabel;
    }
});

module.exports = platformsPanelItemsStore;
