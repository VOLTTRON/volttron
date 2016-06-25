'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformsStore = require('../stores/platforms-store');
var statusIndicatorActionCreators = require('../action-creators/status-indicator-action-creators');
var platformsPanelActionCreators = require('../action-creators/platforms-panel-action-creators');
var platformActionCreators = require('../action-creators/platform-action-creators');
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
            new rpc.Exchange({
                method: 'historian.query',
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
                .catch(rpc.Error, function (error) {

                    var message = "Unable to update chart: " + error.message;
                    var orientation;

                    if (error.code === -32602)
                    {
                        if (error.message === "historian unavailable")
                        {
                            message = "Unable to update chart: The VOLTTRON Central platform's historian is unavailable.";
                            orientation = "left";
                        }
                    }
                    else
                    {
                        var historianRunning = platformsStore.getVcHistorianRunning();

                        if (!historianRunning)
                        {
                            message = "Unable to update chart: The VOLTTRON Central platform's historian is unavailable.";
                            orientation = "left";
                        }
                    }

                    handle401(error, message, null, orientation);
                });
		});

	},
	addToChart: function(panelItem, emitChange) {

        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'historian.query',
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

                platformsPanelActionCreators.checkItem(panelItem.path, true);

                var savedCharts = platformChartStore.getPinnedCharts();
                var inSavedChart = savedCharts.find(function (chart) {
                    return chart.chartKey === panelItem.name;
                });

                if (inSavedChart)
                {
                    platformActionCreators.saveCharts(savedCharts);
                }
            })
            .catch(rpc.Error, function (error) {

                var message = "Unable to load chart: " + error.message;
                var orientation;

                if (error.code === -32602)
                {
                    if (error.message === "historian unavailable")
                    {
                        message = "Unable to load chart: The VOLTTRON Central platform's historian is unavailable.";
                        orientation = "left";
                    }
                }
                else
                {
                    var historianRunning = platformsStore.getVcHistorianRunning();

                    if (!historianRunning)
                    {
                        message = "Unable to load chart: The VOLTTRON Central platform's historian is unavailable.";
                        orientation = "left";
                    }
                }

                platformsPanelActionCreators.checkItem(panelItem.path, false);
                handle401(error, message, null, orientation);
           });
    },
    removeFromChart: function(panelItem) {

        var savedCharts = platformChartStore.getPinnedCharts();
        var inSavedChart = savedCharts.find(function (chart) {
            return chart.chartKey === panelItem.name;
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_FROM_CHART,
            panelItem: panelItem
        });        

        platformsPanelActionCreators.checkItem(panelItem.path, false);

        if (inSavedChart)
        {
            platformActionCreators.saveCharts();
        }

    },
    removeChart: function(chartName) {

        dispatcher.dispatch({
            type: ACTION_TYPES.REMOVE_CHART,
            name: chartName
        });
    }
};

function handle401(error, message, highlight, orientation) {
   if ((error.code && error.code === 401) || (error.response && error.response.status === 401)) {
        dispatcher.dispatch({
            type: ACTION_TYPES.RECEIVE_UNAUTHORIZED,
            error: error,
        });

        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
    else
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformChartActionCreators;
