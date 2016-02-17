'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var rpc = require('../lib/rpc');

var platformChartActionCreators = {
	pinChart: function (chartKey) {
		dispatcher.dispatch({
			type: ACTION_TYPES.PIN_CHART,
			chartKey: chartKey,
		});
	},
	refreshChart: function (series) {

		var authorization = authorizationStore.getAuthorization();

		series.forEach(function (item) {

			if (item.parentType === "platform")
	        {
	            var authorization = authorizationStore.getAuthorization();

	            new rpc.Exchange({
	                method: 'platforms.uuid.' + item.parentUuid + '.historian.query',
	                params: {
	                    topic: item.topic,
	                    count: 20,
	                    order: 'LAST_TO_FIRST',
	                },
	                authorization: authorization,
	            }).promise
	                .then(function (result) {
	                	item.data = result.values;

	                    item.data.forEach(function (datum) {
	                        datum.name = item.name;
	                        datum.parent = item.parentPath;
                        	datum.uuid = item.uuid;
	                    });
	                    dispatcher.dispatch({
	                        type: ACTION_TYPES.REFRESH_CHART,
	                        item: item
	                    });
	                })
	                .catch(rpc.Error, handle401);
	        }  
	        else
	        {
	            dispatcher.dispatch({
	                type: ACTION_TYPES.REFRESH_CHART,
	                item: item
	            });
	        }
		});
		
	},
};

function handle401(error) {
    if (error.code && error.code === 401) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        platformManagerActionCreators.clearAuthorization();
    }
};

module.exports = platformChartActionCreators;
