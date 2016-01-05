'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');

var _agents = {
            "0987fedc-65ba-43fe-21dc-098765bafedc":
            [
                {
                    "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "Volttron Central",
                    "status": "GOOD"
                },
                {
                    "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "Platform Agent",
                    "status": "BAD"
                },
                {
                    "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "SqlHistorian",
                    "status": "UNKNOWN"
                }
            ],
            "2291fedc-65ba-43fe-21dc-098765bafedc":
            [ 
                {
                    "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "Husky Agent",
                    "status": "GOOD"
                },
                {
                    "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "Listener Agent",
                    "status": "BAD"
                },
                {
                    "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "SqlLiteHistorian",
                    "status": "UNKNOWN"
                }
            ],
            "4837fedc-65ba-43fe-21dc-098765bafedc":
            [
                {
                    "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "Cougar Agent",
                    "status": "GOOD"
                },
                {
                    "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "Platform Agent",
                    "status": "BAD"
                },
                {
                    "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
                    "name": "SqlLiteHistorian",
                    "status": "UNKNOWN"
                }
            ]
        };

var _expanded = false;

var platformsPanelAgentStore = new Store();

platformsPanelAgentStore.getAgents = function (platform) {
    if (_agents.hasOwnProperty(platform.uuid))
    {
        return _agents[platform.uuid];
    }
    else
    {
        return [];
    }
};

platformsPanelAgentStore.dispatchToken = dispatcher.register(function (action) {

    switch (action.type) {

        case ACTION_TYPES.RECEIVE_AGENT_STATUSES:
            _agents = action.agents;
            platformsPanelStore.emitChange();
            break;
    }
});

module.exports = platformsPanelAgentStore;
