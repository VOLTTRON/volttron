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
    setMin: function (min, chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_MIN,
            min: min,
            chartKey: chartKey
        });
    },
    setMax: function (max, chartKey) {
        dispatcher.dispatch({
            type: ACTION_TYPES.CHANGE_CHART_MAX,
            max: max,
            chartKey: chartKey
        });
    },
	refreshChart: function (series, length) {

		var authorization = authorizationStore.getAuthorization();

		series.forEach(function (item) {            
            new rpc.Exchange({
                method: 'historian.query',
                params: { // TODO
                    topic: item.topic,
                    count: (length > 0 ? length : 20),
                    order: 'LAST_TO_FIRST',
                },
                authorization: authorization,
            }).promise
                .then(function (result) {

                    if (result.hasOwnProperty("values"))
                    {
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
                    }
                    else
                    {
                        console.log("chart " + item.name + " isn't being refreshed");
                    }
                })
                .catch(rpc.Error, function (error) {
                    handle401(error);
                });
		});

	},
	addToChart: function(panelItem, emitChange) {

        var authorization = authorizationStore.getAuthorization();

        new rpc.Exchange({
            method: 'historian.query',
            params: { // TODO
                topic: panelItem.topic,
                count: (length > 0? length:20),
                order: 'LAST_TO_FIRST',
            },
            authorization: authorization,
        }).promise
            .then(function (result) {

                if (result.hasOwnProperty("values"))
                {    
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
                }
                else
                {
                    var message = "Unable to load chart: An unknown problem occurred.";
                    var orientation = "center";
                    var error = {};

                    if (panelItem.path && panelItem.path.length > 1)
                    {
                        var platformUuid = panelItem.path[1];

                        var vcInstance = platformsStore.getVcInstance();

                        if (vcInstance.uuid === platformUuid)
                        {
                            message = "Unable to load chart: The master driver agent is unavailable on the VOLTTRON Central platform.";
                            orientation = "left";
                        }  
                        else
                        {
                            var forwarderRunning = platformsStore.getForwarderRunning(platformUuid);

                            if (!forwarderRunning)
                            {
                                message = "Unable to load chart: The forwarder agent for the device's platform isn't available.";
                                orientation = "left";
                            } 
                        }           
                    }

                    platformsPanelActionCreators.checkItem(panelItem.path, false);
                    handle401(error, message, null, orientation);
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
    },
    addToCharts: function(panelItems) {

        var authorization = authorizationStore.getAuthorization();

        panelItems.forEach(function (panelItem) {

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

                    if (result.hasOwnProperty("values"))
                    {    
                        panelItem.data = result.values;

                        panelItem.data.forEach(function (datum) {
                            datum.name = panelItem.name;
                            datum.parent = panelItem.parentPath;
                            datum.uuid = panelItem.uuid;
                        });

                        dispatcher.dispatch({
                            type: ACTION_TYPES.SHOW_CHARTS,
                            emitChange: false
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

                        if (panelItem.path && panelItem.path.length > 1)
                        {
                            var platformUuid = panelItem.path[1];
                            var forwarderRunning = platformsStore.getForwarderRunning(platformUuid);

                            if (!forwarderRunning)
                            {
                                message = "Unable to load chart: The forwarder agent for the device's platform isn't available.";
                                orientation = "left";
                            }             
                        }

                        platformsPanelActionCreators.checkItem(panelItem.path, false);
                        handle401(error, message, null, orientation);
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
    else if (message)
    {
        statusIndicatorActionCreators.openStatusIndicator("error", message, highlight, orientation);
    }
}

module.exports = platformChartActionCreators;
