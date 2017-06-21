'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('./authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _platforms = null;
var _initialized = false;

var platformsStore = new Store();

platformsStore.getPlatform = function (uuid) {
    var foundPlatform = null;

    if (_platforms) {
        _platforms.some(function (platform) {
            if (platform.uuid === uuid) {
                foundPlatform = platform;
                return true;
            }
        });
    }

    return foundPlatform;
};

platformsStore.getPlatforms = function () {
    return _platforms;
};

platformsStore.getVcInstance = function () 
{
    var vc;

    if (_platforms)
    {
        if (_platforms.length)
        {
            vc = _platforms.find(function (platform) {

                var hasVcAgent = false;

                if (platform.agents)
                {
                    if (platform.agents.length)
                    {
                        var vcAgent = platform.agents.find(function (agent) {     
                            return agent.name.toLowerCase().indexOf("volttroncentral") > -1;
                        });

                        if (vcAgent)
                        {
                            hasVcAgent = true;
                        }
                    }
                }

                return hasVcAgent;
            });
        }
    }

    return (typeof vc === "undefined" ? null : vc);
};

platformsStore.getAgentRunning = function (platform, agentType) {

    var agentRunning = false;

    if (platform)
    {
        if (platform.hasOwnProperty("agents"))
        {
            var agentToFind = platform.agents.find(function (agent) {     
                return agent.name.toLowerCase().indexOf(agentType) > -1;
            });

            if (agentToFind)
            {
                agentRunning = ((agentToFind.process_id !== null) && (agentToFind.return_code === null));
            }
        }        
    }

    return agentRunning;
};

platformsStore.getVcHistorianRunning = function (vcInstance) {

    var platform = (vcInstance ? vcInstance : platformsStore.getVcInstance());
    var historianRunning = platformsStore.getAgentRunning(platform, "historian");

    return historianRunning;
};

platformsStore.getRunningBacnetProxies = function (uuid)
{
    var bacnetProxies = [];

    if (_platforms)
    {
        if (_platforms.length)
        {
            var foundPlatform = _platforms.find(function (platform) {
                return platform.uuid === uuid;
            });

            if (foundPlatform)
            {
                if (foundPlatform.hasOwnProperty("agents"))
                {
                    bacnetProxies = foundPlatform.agents.filter(function (agent) {

                        // var runningProxy = ((agent.name.toLowerCase().indexOf("bacnet_proxy") > -1) &&
                        //                     (agent.actionPending === false) &&
                        //                     (agent.process_id !== null) &&
                        //                     (agent.return_code === null));
                        var runningProxy = ((agent.name.toLowerCase().indexOf("bacnet_proxy") > -1) &&
                                            (agent.is_running));
                        return runningProxy;
                    });
                }
            }
        }
    }    

    return bacnetProxies;
};

platformsStore.getForwarderRunning = function (platformUuid) {

    var platform = platformsStore.getPlatform(platformUuid);
    var forwarderRunning = platformsStore.getAgentRunning(platform, "forwarderagent");

    return forwarderRunning;
};

platformsStore.getInitialized = function () {
    return _initialized;
};

platformsStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    switch (action.type) {
        case ACTION_TYPES.CLEAR_AUTHORIZATION:
            _platforms = null;
            break;

        case ACTION_TYPES.WILL_INITIALIZE_PLATFORMS:
            _initialized = true;
            break;

        case ACTION_TYPES.RECEIVE_PLATFORMS:
            _platforms = action.platforms;
            platformsStore.emitChange();
            break;

        case ACTION_TYPES.RECEIVE_PLATFORM:
            platformsStore.emitChange();
            break;
    }
});

module.exports = platformsStore;
