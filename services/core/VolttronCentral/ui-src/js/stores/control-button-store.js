'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var _controlButtons = {};

var controlButtonStore = new Store();



controlButtonStore.getTaptip = function (name) {
    
    var showTaptip = null;

    if (_controlButtons.hasOwnProperty([name]))
    {
        if (_controlButtons[name].hasOwnProperty("showTaptip"))
        {
            showTaptip = _controlButtons[name].showTaptip;
        }
    }

    return showTaptip;
}

controlButtonStore.dispatchToken = dispatcher.register(function (action) {
    switch (action.type) {

        case ACTION_TYPES.TOGGLE_TAPTIP:             

            var showTaptip;

            if (_controlButtons.hasOwnProperty(action.name))
            {
                _controlButtons[action.name].showTaptip = showTaptip = !_controlButtons[action.name].showTaptip;
            }
            else
            {
                _controlButtons[action.name] = { "showTaptip": true };
                showTaptip = true;
            }

            if (showTaptip === true) 
            {            
                //close other taptips    
                for (var key in _controlButtons)
                {
                    if (key !== action.name)
                    {
                        _controlButtons[key].showTaptip = false;
                    }
                }
            }

            controlButtonStore.emitChange();

            break;

        case ACTION_TYPES.HIDE_TAPTIP:             

            if (_controlButtons.hasOwnProperty(action.name))
            {
                if (_controlButtons[action.name].hasOwnProperty("showTaptip"))
                {
                    _controlButtons[action.name].showTaptip = false;
                    // delete _controlButtons[action.name];   
                }
            }

            controlButtonStore.emitChange();

            break;
    } 

    
    
});



module.exports = controlButtonStore;
