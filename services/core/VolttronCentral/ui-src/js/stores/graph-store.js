'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _graphVisible = false;
var _graphData = [];

var graphStore = new Store();

graphStore.getGraphs = function (uuid) {
    

    return null;
};

graphStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

graphStore.getData = function () {
    return _graphData;
}

graphStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.ADD_TO_GRAPH:  

            var graphItems = _graphData.filter(function (item) { return item.uuid === action.panelItem.uuid });

            if (graphItems.length === 0)
            {
                if (action.panelItem.hasOwnProperty("data"))
                {
                    _graphData = _graphData.concat(action.panelItem.data);
                }

                if (_graphData.length > 0)
                {
                    _graphVisible = true;
                }

                graphStore.emitChange();
            }

            break;

        case ACTION_TYPES.REMOVE_FROM_GRAPH:

            if (_graphData.length > 0)
            {
                _graphData.forEach(function(item, index) {
                    if (item.uuid === action.panelItem.uuid)
                    {
                        _graphData.splice(index, 1);
                    }
                });

                for (var i = _graphData.length - 1; i >= 0; i--)
                {
                    if (_graphData[i].uuid === action.panelItem.uuid)
                    {
                        _graphData.splice(i, 1);
                    }                    
                }

                if (_graphData.length === 0)
                {
                    _graphVisible = false;
                }

                graphStore.emitChange();  
            }

            break;
    } 
    
});



module.exports = graphStore;
