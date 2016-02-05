'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _chartVisible = false;
var _chartData = {};

var chartStore = new Store();

chartStore.getCharts = function (uuid) {
    

    return null;
};

chartStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

chartStore.getData = function () {
    return _chartData;
}

chartStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.ADD_TO_CHART:  

            if (_chartData.hasOwnProperty(action.panelItem.name))
            {
                var chartItems = _chartData[action.panelItem.name].filter(function (item) { return item.uuid === action.panelItem.uuid });

                if (chartItems.length === 0)
                {
                    if (action.panelItem.hasOwnProperty("data"))
                    {
                        _chartData[action.panelItem.name] = _chartData[action.panelItem.name].concat(action.panelItem.data);
                    }

                    if (_chartData[action.panelItem.name].length > 0)
                    {
                        _chartVisible = true;
                    }

                    chartStore.emitChange();
                }
            }
            else
            {
                if (action.panelItem.hasOwnProperty("data"))
                {
                    _chartData[action.panelItem.name] = JSON.parse(JSON.stringify(action.panelItem.data));

                    chartStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.REMOVE_FROM_CHART:

            if (_chartData[action.panelItem.name].length > 0)
            {
                // _chartData[action.panelItem.name].forEach(function(item, index) {
                //     if (item.uuid === action.panelItem.uuid)
                //     {
                //         _chartData[action.panelItem.name].splice(index, 1);
                //     }
                // });

                for (var i = _chartData[action.panelItem.name].length - 1; i >= 0; i--)
                {
                    if (_chartData[action.panelItem.name][i].uuid === action.panelItem.uuid)
                    {
                        _chartData[action.panelItem.name].splice(i, 1);
                    }                    
                }

                if (_chartData[action.panelItem.name].length === 0)
                {
                    _chartVisible = false;
                }

                chartStore.emitChange();  
            }

            break;
    } 
    
});



module.exports = chartStore;
