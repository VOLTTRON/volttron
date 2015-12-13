'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformsPanelActionCreators = {    
    togglePanel: function() {

        dispatcher.dispatch({
            type: ACTION_TYPES.TOGGLE_PLATFORMS_PANEL,
        });
    },

    loadPlatformsPanel: function () {
        var authorization = authorizationStore.getAuthorization();

        var platforms = [
            {
                "uuid": "0987fedc-65ba-43fe-21dc-098765bafedc",
                "name": "vc",
                "status": "GOOD"
            },
            {
                "uuid": "2291fedc-65ba-43fe-21dc-098765bafedc",
                "name": "vc1",
                "status": "BAD"
            },
            {
                "uuid": "4837fedc-65ba-43fe-21dc-098765bafedc",
                "name": "vc2",
                "status": "UNKNOWN"
            }
        ];

        // dispatcher.dispatch({
        //     type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
        //     platforms: platforms,
        // });

        // return new rpc.Exchange({
        //     method: 'list_platforms',
        //     authorization: authorization,
        // }).promise
        //     .then(function (platforms) {
        //         dispatcher.dispatch({
        //             type: ACTION_TYPES.RECEIVE_PLATFORM_STATUSES,
        //             platforms: platforms,
        //         });
                
        //     })
        //     .catch(rpc.Error, handle401);
        
    },
};


module.exports = platformsPanelActionCreators;
