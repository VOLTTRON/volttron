'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');
var platformsStore = require('./platforms-store.js')


var _chartData = {};
var _showCharts = false;
var _chartTopics = {
    platforms: []
};

var chartStore = new Store();

chartStore.getPinnedCharts = function () {
    var pinnedCharts = [];

    var user = authorizationStore.getUsername();

    for (var key in _chartData)
    {
        if (_chartData[key].hasOwnProperty("pinned") && (_chartData[key].pinned === true) && (_chartData[key].series.length > 0))
        {
            pinnedCharts.push(_chartData[key]);
        }
    }

    return JSON.parse(JSON.stringify(pinnedCharts));
};

chartStore.getData = function () {
    return JSON.parse(JSON.stringify(_chartData));
}

chartStore.getPinned = function (chartKey) {
    return (_chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].pinned : null);
}

chartStore.getType = function (chartKey) {
    var type = "lineChart";

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

chartStore.getDataLength = function (chartKey) {
    return (_chartData.hasOwnProperty(chartKey) ? _chartData[chartKey].dataLength : null);
}

chartStore.showCharts = function () {

    var showCharts = _showCharts;

    _showCharts = false;

    return showCharts;
}

chartStore.getChartTopics = function () {
    
    var topics = [];

    if (_chartTopics.hasOwnProperty("platforms"))
    {
        topics = JSON.parse(JSON.stringify(_chartTopics.platforms));

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
                            return item.topic === topic.value;
                        });

                        topicInChart = (path ? true : false);
                    }

                    return !topicInChart;
                });
            }

            // Filter out any orphan chart topics not associated with registered platforms
            var platformUuids = platformsStore.getPlatforms().map(function (platform) {
                return platform.uuid;
            });

            topics = topics.filter(function (topic) {
                
                // This filter will keep platform topics of known platforms and any topic that
                // looks like a device topic
                var platformTopic = platformUuids.filter(function (uuid) {
                    return ((topic.value.indexOf(uuid) > -1) || (topic.value.indexOf("datalogger/platform") < 0));
                });

                return (platformTopic.length ? true : false);
            });
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
                var availableColors = ((
                        _chartData[action.panelItem.name].availableColors && 
                        _chartData[action.panelItem.name].availableColors.length
                    ) ? 
                    _chartData[action.panelItem.name].availableColors :
                    initColors()
                );

                var itemWithColor = getItemWithColor(action.panelItem, availableColors);

                // Update the chart's availableColors with the modified availableColors list
                _chartData[action.panelItem.name].availableColors = availableColors;

                insertSeries(itemWithColor);
                chartStore.emitChange();
            }
            else
            {
                if (action.panelItem.hasOwnProperty("data"))
                {
                    var availableColors = initColors();

                    var itemWithColor = getItemWithColor(action.panelItem, availableColors);

                    var chartObj = {
                        refreshInterval: (
                            action.panelItem.hasOwnProperty("refreshInterval") ?
                            action.panelItem.refreshInterval :
                            15000
                        ),
                        dataLength: (
                            action.panelItem.hasOwnProperty("dataLength") ? 
                            action.panelItem.dataLength :
                            20
                        ),
                        pinned: (
                            action.panelItem.hasOwnProperty("pinned") ?
                            action.panelItem.pinned :
                            false
                        ),
                        type: (
                            action.panelItem.hasOwnProperty("chartType") ?
                            action.panelItem.chartType :
                            "lineChart"
                        ),
                        chartKey: action.panelItem.name,
                        availableColors: availableColors,
                        series: [
                            setChartSeries(
                                itemWithColor,
                                convertTimeToSeconds(itemWithColor.data)
                            )
                        ]
                    };

                    _chartData[action.panelItem.name] = chartObj;
                    chartStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.LOAD_CHARTS:           

            _chartData = {};

            action.charts.forEach(function (chart) {

                var chartObj = chart;

                if (chartObj.series && chartObj.series.length)
                {
                    // For each series, make sure it has a color. This is 
                    // for charts that were pinned before the code update
                    // to assign colors was deployed. Eventually, we should
                    // be able to remove this forEach loop, because all 
                    // pinned charts will have been saved to the database 
                    // with colors
                    chartObj.series.forEach(function (series) {
                        var itemWithColor = series;
                        
                        if (!itemWithColor.hasOwnProperty('colors'))
                        {
                            var availableColors = ((
                                    chartObj.availableColors && 
                                    chartObj.availableColors.length
                                ) ? 
                                chartObj.availableColors :
                                initColors()
                            );

                            itemWithColor = getItemWithColor(itemWithColor, availableColors);

                            // Update the chart's availableColors with the modified availableColors list
                            chartObj.availableColors = availableColors;
                        }
                    });
                }

                _chartData[chart.chartKey] = JSON.parse(JSON.stringify(chartObj));
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
                        delete _chartData[action.panelItem.name];
                    }
                    else
                    {
                        unassignColor(
                            action.panelItem,
                            _chartData[action.panelItem.name].availableColors
                        );
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

        case ACTION_TYPES.CHANGE_CHART_LENGTH:

            if (_chartData[action.chartKey].hasOwnProperty("dataLength"))
            {
                _chartData[action.chartKey].dataLength = action.length;
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

            _chartTopics.platforms = chartTopics;            

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

        case ACTION_TYPES.REMOVE_PLATFORM_CHARTS:

            var seriesToCut = [];

            for (var name in _chartData)
            {
                _chartData[name].series.forEach(function (series) {

                    if (series.path.indexOf(this.uuid) > -1)
                    {
                        seriesToCut.push({name: series.name, uuid: series.uuid});
                    }

                }, action.platform);
            }

            seriesToCut.forEach(function (series) {
                removeSeries(series.name, series.uuid);

                if (_chartData[series.name].series.length === 0)
                {
                    delete _chartData[series.name];
                }

            }, action.platform);

            if (seriesToCut.length)
            {
                chartStore.emitChange();
            }

            break;

        case ACTION_TYPES.CLEAR_AUTHORIZATION: 

            _chartData = {};

            break;
    }

    function setChartSeries(item, data) {

        var chartItem = {
            name: item.name,
            uuid: item.uuid,
            path: item.path,
            parentUuid: item.parentUuid,
            parentType: item.parentType,
            parentPath: item.parentPath,
            topic: item.topic,
            colors: item.colors,
            data: data
        }

        return chartItem;
    }

    function insertSeries(item) {
        if (item.hasOwnProperty("data"))
        {   
            _chartData[item.name].series.push(
                setChartSeries(
                    item,
                    convertTimeToSeconds(item.data)
                )
            );
        }
    }

    function removeSeries(name, uuid) {

        for (var i = 0; i < _chartData[name].series.length; i++)
        {
            if (_chartData[name].series[i].uuid === uuid)
            {
                _chartData[name].series.splice(i, 1);

                break;
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
                }

                newItem[skey] = value;    
            }

            dataList.push(newItem);
        }

        return dataList;
    }

    function getItemWithColor(item, availableColors) {
        var assignedColor = popColor(availableColors);
        var itemWithColor = item;
        itemWithColor['colors'] = assignedColor;

        return itemWithColor;
    }

    function unassignColor(item, availableColors) {
        if (item.hasOwnProperty('colors')) // legacy series won't have colors associated
        {
            var colorFound = availableColors.find(function (color) {
                return color.name === item.colors.name
            });
    
            if (typeof colorFound === 'undefined')
            {
                availableColors.push(Object.assign({}, item.colors));
            }
        }
    }

    function popColor(colorSet) {
        var poppedColor = colorSet.splice(0, 1);

        return poppedColor[0];
    }

    function initColors() {
        var colorVal = 1;
        var lighterVal = 0.8;
        var lightestVal = 0.3;

        var colorSet = [
            {
              name: 'darkorange',
              color: `rgba(255,140,0,${colorVal})`,
              lighter: `rgba(255,140,0,${lighterVal})`,
              lightest: `rgba(255,140,0,${lightestVal})`
            },
            {
              name: 'green',
              color: `rgba(0,128,0,${colorVal})`,
              lighter: `rgba(0,128,0,${lighterVal})`,
              lightest: `rgba(0,128,0,${lightestVal})`
            },
            {
              name: 'teal',
              color: `rgba(0,128,128,${colorVal})`,
              lighter: `rgba(0,128,128,${lighterVal})`,
              lightest: `rgba(0,128,128,${lightestVal})`
            },
            {
              name: 'maroon',
              color: `rgba(128,0,0,${colorVal})`,
              lighter: `rgba(128,0,0,${lighterVal})`,
              lightest: `rgba(128,0,0,${lightestVal})`
            },
            {
              name: 'navy',
              color: `rgba(0,0,128,${colorVal})`,
              lighter: `rgba(0,0,128,${lighterVal})`,
              lightest: `rgba(0,0,128,${lightestVal})`
            },
            {
              name: 'silver',
              color: `rgba(192,192,192,${colorVal})`,
              lighter: `rgba(192,192,192,${lighterVal})`,
              lightest: `rgba(192,192,192,${lightestVal})`
            },
            {
              name: 'purple',
              color: `rgba(128,0,128,${colorVal})`,
              lighter: `rgba(128,0,128,${lighterVal})`,
              lightest: `rgba(128,0,128,${lightestVal})`
            },
            {
              name: 'red',
              color: `rgba(255,0,0,${colorVal})`,
              lighter: `rgba(255,0,0,${lighterVal})`,
              lightest: `rgba(255,0,0,${lightestVal})`
            },
            {
              name: 'lime',
              color: `rgba(0,255,0,${colorVal})`,
              lighter: `rgba(0,255,0,${lighterVal})`,
              lightest: `rgba(0,255,0,${lightestVal})`
            },
            {
              name: 'tan',
              color: `rgba(210,180,140,${colorVal})`,
              lighter: `rgba(210,180,140,${lighterVal})`,
              lightest: `rgba(210,180,140,${lightestVal})`
            },
            {
              name: 'gold',
              color: `rgba(255,215,0,${colorVal})`,
              lighter: `rgba(255,215,0,${lighterVal})`,
              lightest: `rgba(255,215,0,${lightestVal})`
            },
            {
              name: 'aqua',
              color: `rgba(0,255,255,${colorVal})`,
              lighter: `rgba(0,255,255,${lighterVal})`,
              lightest: `rgba(0,255,255,${lightestVal})`
            },
            {
              name: 'fuchsia',
              color: `rgba(255,0,255,${colorVal})`,
              lighter: `rgba(255,0,255,${lighterVal})`,
              lightest: `rgba(255,0,255,${lightestVal})`
            },
            {
              name: 'olive',
              color: `rgba(128,128,0,${colorVal})`,
              lighter: `rgba(128,128,0,${lighterVal})`,
              lightest: `rgba(128,128,0,${lightestVal})`
            }
        ];
    
        return colorSet;
    }
});



module.exports = chartStore;
