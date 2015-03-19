'use strict';

var ACTION_TYPES = require('../constants/action-types');
var dispatcher = require('../dispatcher');
var rpc = require('../lib/rpc');

var platformManagerActionCreators = {
    requestAuthorization: function (username, password) {
        var request = new rpc.Request({
            method: 'getAuthorization',
            params: {
                username: username,
                password: password,
            },
        });

        request.call()
            .then(function (response) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REQUEST_AUTHORIZATION_SUCCESS,
                    authorization: response.result,
                });
            })
            .catch(rpc.ResponseError, function (error) {
                dispatcher.dispatch({
                    type: ACTION_TYPES.REQUEST_AUTHORIZATION_FAIL,
                    error: error.response.error,
                });
            });
    },
    clearAuthorization: function () {
        dispatcher.dispatch({
            type: ACTION_TYPES.CLEAR_AUTHORIZATION,
        });
    }
};

module.exports = platformManagerActionCreators;
