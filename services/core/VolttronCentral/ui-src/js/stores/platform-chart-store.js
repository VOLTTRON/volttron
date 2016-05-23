'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _chartData = {};
var _showCharts = false;
var _chartTopics = {};

var chartStore = new Store();

chartStore.getPinnedCharts = function () {
    var pinnedCharts = [];

    for (var key in _chartData)
    {
        if (_chartData[key].hasOwnProperty("pinned") && (_chartData[key].pinned === true) && (_chartData[key].data.length > 0))
        {
            pinnedCharts.push(_chartData[key]);
        }
    }

    return JSON.parse(JSON.stringify(pinnedCharts));
};

chartStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

chartStore.getData = function () {
    return JSON.parse(JSON.stringify(_chartData));
}

chartStore.getPinned = function (chartKey) {
    return (_chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].pinned : null);
}

chartStore.getType = function (chartKey) {
    var type = "line";

    if (_chartData.hasOwnProperty(chartKey))
    {
        if (_chartData[chartKey].hasOwnProperty("type"))
        {
            type = _chartData[chartKey].type;
        }
    }

    return type;
}

chartStore.getRefreshRate = function (chartKey) {
    return (_chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].refreshInterval : null);
}

chartStore.showCharts = function () {

    var showCharts = _showCharts;

    _showCharts = false;

    return showCharts;
}

chartStore.getChartTopics = function (parentUuid) {
    
    var topics = [];

    if (_chartTopics.hasOwnProperty(parentUuid))
    {
        topics = JSON.parse(JSON.stringify(_chartTopics[parentUuid]));

        if (topics.length)
        {    
            if (_chartData !== {})
            {
                // Filter out any topics that are already in charts
                topics = topics.filter(function (topic) {

                    var topicInChart = false;

                    if (_chartData.hasOwnProperty(topic.name))
                    {
                        var path = _chartData[topic.name].series.find(function (item) {
                            return item.topic === topic.path;
                        });

                        topicInChart = (path ? true : false);
                    }

                    return !topicInChart;
                });
            }
        }
    }

    return topics;
}

chartStore.getTopicInCharts = function (topic, topicName)
{
    var itemInChart;

    if (_chartData.hasOwnProperty(topicName))
    {
        _chartData[topicName].series.find(function (series) {

            itemInChart = (series.topic === topic);

            return itemInChart;
        });
    }

    return itemInChart;
}

chartStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.ADD_TO_CHART:             

            if (_chartData.hasOwnProperty(action.panelItem.name))
            {
                insertSeries(action.panelItem);
                chartStore.emitChange();
            }
            else
            {
                if (action.panelItem.hasOwnProperty("data"))
                {
                    // _chartData[action.panelItem.name] = JSON.parse(JSON.stringify(action.panelItem.data));
                    
                    var chartObj = {
                        refreshInterval: (action.panelItem.hasOwnProperty("refreshInterval") ? action.panelItem.refreshInterval :15000),
                        pinned: (action.panelItem.hasOwnProperty("pinned") ? action.panelItem.pinned : false),
                        type: (action.panelItem.hasOwnProperty("chartType") ? action.panelItem.chartType : "line"),
                        data: convertTimeToSeconds(action.panelItem.data),
                        chartKey: action.panelItem.name,
                        series: [ setChartItem(action.panelItem) ]
                    };

                    _chartData[action.panelItem.name] = chartObj;
                    chartStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.LOAD_CHARTS:           

            _chartData = {};

            action.charts.forEach(function (chart) {
                _chartData[chart.chartKey] = JSON.parse(JSON.stringify(chart));
            });
            
            chartStore.emitChange();

            break;

        case ACTION_TYPES.REMOVE_FROM_CHART:
            
            if (_chartData.hasOwnProperty(action.panelItem.name))
            {
                removeSeries(action.panelItem.name, action.panelItem.uuid);

                if (_chartData.hasOwnProperty(action.panelItem.name))
                {
                    if (_chartData[action.panelItem.name].length === 0)
                    {
                        delete _chartData[name];
                    }
                }

                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.REFRESH_CHART:

            removeSeries(action.item.name, action.item.uuid);
            insertSeries(action.item);
            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_REFRESH:

            if (_chartData[action.chartKey].hasOwnProperty("refreshInterval"))
            {
                _chartData[action.chartKey].refreshInterval = action.rate;
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.PIN_CHART:

            if (_chartData[action.chartKey].hasOwnProperty("pinned"))
            {
                _chartData[action.chartKey].pinned = !_chartData[action.chartKey].pinned;
            }
            else
            {
                _chartData[action.chartKey].pinned = true;   
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.CHANGE_CHART_TYPE:

            if (_chartData[action.chartKey].type !== action.chartType)
            {
                _chartData[action.chartKey].type = action.chartType;
            }

            chartStore.emitChange();

            break;

        case ACTION_TYPES.SHOW_CHARTS:

            if (action.emitChange)
            {
                _showCharts = true;
                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.RECEIVE_CHART_TOPICS:
            _chartTopics = {};

            var chartTopics = JSON.parse(JSON.stringify(action.topics));

            _chartTopics[action.platform.uuid] = chartTopics;            

            chartStore.emitChange();
            break;

        case ACTION_TYPES.REMOVE_CHART:

            var name = action.name;

            if (_chartData.hasOwnProperty(name))
            {

                delete _chartData[name];

                chartStore.emitChange();
            }

            break;
    }

    function setChartItem(item) {

        var chartItem = {
            name: item.name,
            uuid: item.uuid,
            path: item.path,
            parentUuid: item.parentUuid,
            parentType: item.parentType,
            parentPath: item.parentPath,
            topic: item.topic
        }

        return chartItem;
    }

    function insertSeries(item) {

        var chartItems = _chartData[item.name].data.filter(function (datum) {
            return datum.uuid === item.uuid
        });

        if (chartItems.length === 0)
        {
            if (item.hasOwnProperty("data"))
            {
                _chartData[item.name].data = _chartData[item.name].data.concat(convertTimeToSeconds(item.data));
                _chartData[item.name].series.push(setChartItem(item));
            }
        }

    }

    function removeSeries(name, uuid) {

        if (_chartData[name].data.length > 0)
        {
            for (var i = _chartData[name].data.length - 1; i >= 0; i--)
            {
                if (_chartData[name].data[i].uuid === uuid)
                {
                    _chartData[name].data.splice(i, 1);
                }                    
            }

            for (var i = 0; i < _chartData[name].series.length; i++)
            {
                if (_chartData[name].series[i].uuid === uuid)
                {
                    _chartData[name].series.splice(i, 1);

                    break;
                }
            }
        }
    }

    function convertTimeToSeconds(data) {
        var dataList = [];

        for (var key in data)
        {
            var newItem = {};

            for (var skey in data[key])
            {
                var value = data[key][skey];

                if (typeof value === 'string')
                {
                    value = value.replace('+00:00', '');
                }
                
                if (skey === "0" && typeof value === 'string' &&
                    Date.parse(value + 'Z')) {
                    value = Date.parse(value + 'Z');
                    // initialState.xDates = true;
                }

                newItem[skey] = value;    
            }

            dataList.push(newItem);
        }

        return dataList;
    }
    
});



module.exports = chartStore;
