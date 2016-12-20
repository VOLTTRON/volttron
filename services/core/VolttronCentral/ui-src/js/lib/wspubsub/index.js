'use strict';

var wsapi = require('./wspubsub');

module.exports = {
    Error: require('./error'),

    openManagementWS: wsapi.openManagementWS,
    openConfigureWS: wsapi.openConfigureWS,
    openIAmWS: wsapi.openIAmWS,
    setAuthorization: wsapi.setAuthorization
};
