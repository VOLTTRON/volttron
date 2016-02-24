'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _chartData = {};

var chartStore = new Store();

chartStore.getPinnedCharts = function () {
    var pinnedCharts = [];

    for (var key in _chartData)
    {
        if (_chartData[key].hasOwnProperty("pinned") && _chartData[key].pinned === true)
        {
            pinnedCharts.push(_chartData[key]);
        }
    }

    return pinnedCharts;
};

chartStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

chartStore.getData = function () {
    return _chartData;
}

chartStore.getPinned = function (chartKey) {
    return _chartData[chartKey].pinned;
}

chartStore.getType = function (chartKey) {
    var type = "line";

    if (_chartData[chartKey].hasOwnProperty("type"))
    {
        type = _chartData[chartKey].type;
    }

    return type;
}

chartStore.getRefreshRate = function (chartKey) {
    return _chartData[chartKey].refreshInterval;
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
                        refreshInterval: 15000,
                        pinned: false, 
                        data: convertTimeToSeconds(action.panelItem.data),
                        series: [
                            { 
                                name: action.panelItem.name, 
                                uuid: action.panelItem.uuid, 
                                parentUuid: action.panelItem.parentUuid,
                                parentType: action.panelItem.parentType,
                                parentPath: action.panelItem.parentPath,
                                topic: action.panelItem.topic 
                            }
                        ]
                    };

                    _chartData[action.panelItem.name] = chartObj;
                    chartStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.REMOVE_FROM_CHART:
            
            removeSeries(action.panelItem.name, action.panelItem.uuid);
            chartStore.emitChange();

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
                _chartData[item.name].series.push(
                    { 
                        name: item.name, 
                        uuid: item.uuid, 
                        parentUuid: item.parentUuid,
                        parentType: item.parentType,
                        parentPath: item.parentPath,
                        topic: item.topic  
                    }
                );
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
