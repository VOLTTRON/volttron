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
	setType: function (chartKey, chartType) {
		dispatcher.dispatch({
			type: ACTION_TYPES.CHANGE_CHART_TYPE,
			chartKey: chartKey,
			chartType: chartType
		});
	},
	changeRefreshRate: function (rate, chartKey) {
		dispatcher.dispatch({
			type: ACTION_TYPES.CHANGE_CHART_REFRESH,
			rate: rate,
			chartKey: chartKey
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
	            if (item.uuid === "5461fedc-65ba-43fe-21dc-098765bafedl")
	            {
	                item.data = [['2016-02-19T01:00:31.630626',31.4],['2016-02-19T01:00:16.632151',23],['2016-02-19T01:00:01.627188',16.5],['2016-02-19T00:59:46.641500',42.8],['2016-02-19T00:59:31.643573',21.2],['2016-02-19T00:59:16.643254',9.3],['2016-02-19T00:59:01.639104',8.5],['2016-02-19T00:58:46.638238',16],['2016-02-19T00:58:31.633733',12.4],['2016-02-19T00:58:16.632418',23],['2016-02-19T00:58:01.630463',16.7],['2016-02-19T00:57:46.648439',9.1],['2016-02-19T00:57:31.640824',10.5],['2016-02-19T00:57:16.636578',8.2],['2016-02-19T00:57:01.644842',2.2],['2016-02-19T00:56:46.635059',2.5],['2016-02-19T00:56:31.639332',2.4],['2016-02-19T00:56:16.647604',2.3],['2016-02-19T00:56:01.643571',11.2],['2016-02-19T00:55:46.644522',9.8]];
	                item.data.forEach(function (datum) {
	                    datum.name = item.name;
	                    datum.parent = item.parentPath;
	                    datum.uuid = item.uuid;
	                });

	                dispatcher.dispatch({
	                    type: ACTION_TYPES.REFRESH_CHART,
	                    item: item
	                });
	            }
	            else if (item.uuid === "5461fedc-65ba-43fe-21dc-111765bafedl")
	            {
	                item.data = [['2016-02-19T01:00:31.630626',73.6],['2016-02-19T01:00:16.632151',71],['2016-02-19T01:00:01.627188',69.4],['2016-02-19T00:59:46.641500',60],['2016-02-19T00:59:31.643573',67],['2016-02-19T00:59:16.643254',68.6],['2016-02-19T00:59:01.639104',77],['2016-02-19T00:58:46.638238',83.5],['2016-02-19T00:58:31.633733',57.2],['2016-02-19T00:58:16.632418',78.7],['2016-02-19T00:58:01.630463',90.7],['2016-02-19T00:57:46.648439',91.5],['2016-02-19T00:57:31.640824',84],['2016-02-19T00:57:16.636578',87.6],['2016-02-19T00:57:01.644842',77],['2016-02-19T00:56:46.635059',83.3],['2016-02-19T00:56:31.639332',90.9],['2016-02-19T00:56:16.647604',89.5],['2016-02-19T00:56:01.643571',91.8],['2016-02-19T00:55:46.644522',97.7]];
	                item.data.forEach(function (datum) {
	                    datum.name = item.name;
	                    datum.parent = item.parentPath;
	                    datum.uuid = item.uuid;
	                });

	                dispatcher.dispatch({
	                    type: ACTION_TYPES.REFRESH_CHART,
	                    item: item
	                });
	            }
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
