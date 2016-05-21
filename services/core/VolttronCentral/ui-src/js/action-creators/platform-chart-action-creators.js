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
                .catch(rpc.Error, function (error) {

                    var message = "Error updating chart: " + error.message;

                    if (error.code === -32602)
                    {
                        if (error.message === "historian unavailable")
                        {
                            message = "Error updating chart: The historian agent is unavailable.";
                        }
                    }
                    else
                    {
                        var platform = platformsStore.getPlatform(item.parentUuid);
                        var historianRunning = platformsStore.getHistorianRunning(platform);

                        if (!historianRunning)
                        {
                            message = "Error updating chart: The historian agent is unavailable.";
                        }
                    }

                    statusIndicatorActionCreators.openStatusIndicator("error", message);

                    handle401(error);
                });
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

                var message = "Error loading chart: " + error.message;

                if (error.code === -32602)
                {
                    if (error.message === "historian unavailable")
                    {
                        message = "Error loading chart: The historian agent is unavailable.";
                    }
                }
                else
                {
                    var platform = platformsStore.getPlatform(panelItem.parentUuid);
                    var historianRunning = platformsStore.getHistorianRunning(platform);

                    if (!historianRunning)
                    {
                        message = "Error loading chart: The historian agent is unavailable.";
                    }
                }

                statusIndicatorActionCreators.openStatusIndicator("error", message);
                platformsPanelActionCreators.checkItem(panelItem.path, false);
                handle401(error);
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
