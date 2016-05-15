'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
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
		});
		
	},
	addToChart: function(panelItem, emitChange) {

        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'platforms.uuid.' + panelItem.parentUuid + '.historian.query',
            params: {
                topic: panelItem.topic,
                count: 20,
                order: 'LAST_TO_FIRST',
            },
            authorization: authorization,
        }).promise
            .then(function (result) {
                panelItem.data = result.values;

                panelItem.data.forEach(function (datum) {
                    datum.name = panelItem.name;
                    datum.parent = panelItem.parentPath;
                    datum.uuid = panelItem.uuid;
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.SHOW_CHARTS,
                    emitChange: (emitChange === null || typeof emitChange === "undefined" ? true : emitChange)
                });

                dispatcher.dispatch({
                    type: ACTION_TYPES.ADD_TO_CHART,
                    panelItem: panelItem
                });
            })
            .catch(rpc.Error, function (error) {
                
                var message = error.message;

                if (error.code === -32602)
                {
                    if (error.message === "historian unavailable")
                    {
                        message = "Data could not be fetched. The historian agent is unavailable."
                    }
                }

                statusIndicatorActionCreators.openStatusIndicator("error", message);
                handle401(error);
            });
    },
    removeFromChart: function(panelItem) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_CHART,
            panelItem: panelItem
        });  

    }
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
