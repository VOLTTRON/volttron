'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var authorizationStore = require('../stores/authorization-store');
var platformChartStore = require('../stores/platform-chart-store');
var platformsStore = require('../stores/platforms-store');
var platformsPanelItemsStore = require('../stores/platforms-panel-items-store');
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
    changeDataLength: function (length, chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_LENGTH,
        length: length,
            chartKey: chartKey
        });
    },
    refreshChart: function (series, length) {
        doChartFetch(series, length, ACTION_TYPES.REFRESH_CHART);
    },
	addToChart: function(panelItem, emitChange) {

        var authorization = authorizationStore.getAuthorization();

        loadChart(panelItem, emitChange, authorization);

    },
    addToCharts: function(panelItems) {

        var authorization = authorizationStore.getAuthorization();
        var emitChange = false;

        panelItems.forEach(function (panelItem) {
            loadChart(panelItem, emitChange, authorization);            
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

function doChartFetch(series, length, callbackAction) {

    var authorization = authorizationStore.getAuthorization();

    series.forEach(function (item) { 

        var topic = prepTopic(item.topic);

        new rpc.Exchange({
            method: 'historian.query',
            params: {
                topic: topic,
                count: (length > 0 ? length : 20),
                order: 'LAST_TO_FIRST',
            },
            authorization: authorization,
        }).promise
            .then(function (result) {

                if (result.hasOwnProperty("values"))
                {
                    item.data = result.values.reverse();

                    item.data.forEach(function (datum) {
                        datum.name = item.name;
                        datum.parent = item.parentPath;
                        datum.uuid = item.uuid;
                    });
                    dispatcher.dispatch({
                        type: callbackAction,
                        item: item
                    });
                }
            })
            .catch(rpc.Error, function (error) {
                handle401(error);
            });
    });
}

function prepTopic(itemTopic) {
    var topic = itemTopic;

    var index = itemTopic.indexOf("devices/");

    if (index === 0)
    {
        topic = itemTopic.replace("devices/", "");
    }

    return topic;
}

function loadChart(panelItem, emitChange, authorization) {

    var topic = prepTopic(panelItem.topic);

    new rpc.Exchange({
        method: 'historian.query',
        params: {
            topic: topic,
            count: 20,
            order: 'LAST_TO_FIRST',
        },
        authorization: authorization,
    }).promise
        .then(function (result) {

            if (result.hasOwnProperty("values"))
            {    
                panelItem.data = result.values.reverse();

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
            }
            else
            {
                var message = "Unable to load chart: An unknown problem occurred.";
                var orientation = "center";
                var error = {};
                var highlight = null;

                if (panelItem.path && panelItem.path.length > 1)
                {
                    var platformPath = panelItem.path.slice(0, 1);
                    var uuid = panelItem.path[1];

                    var platform = platformsPanelItemsStore.getItem(platformPath);

                    message = "Unable to load chart: No data was retrieved for " + topic + ". Check for proper configuration " +
                        " of any forwarder, master driver, and platform agents on platform '" + platform[uuid].name + "'.";
                    orientation = "left";
                    highlight = topic;                        
                }

                platformsPanelActionCreators.checkItem(panelItem.path, false);
                handle401(error, message, highlight, orientation);
            }
        })
        .catch(rpc.Error, function (error) {

            var message = "Unable to load chart: " + error.message;
            var orientation;

            if (error.code === -32602)
            {
                if (error.message === "historian unavailable")
                {
                    message = "Unable to load chart: The platform historian is unavailable on the VOLTTRON Central platform.";
                    orientation = "left";
                }
            }
            else
            {
                var vcInstance = platformsStore.getVcInstance();

                if (vcInstance)
                {
                    var historianRunning = platformsStore.getVcHistorianRunning(vcInstance);

                    if (!historianRunning)
                    {
                        message = "Unable to load chart: The platform historian is unavailable on the VOLTTRON Central platform.";
                        orientation = "left";
                    }
                }
                else
                {
                    message = "Unable to load chart: An unknown problem occurred.";
                    orientation = "left";
                }
            }

            platformsPanelActionCreators.checkItem(panelItem.path, false);
            handle401(error, message, null, orientation);
       });
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
    else if (message)
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformChartActionCreators;
