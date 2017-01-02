'use strict';

function WsPubSubError(error) {
    this.name = 'WsPubSubError';
    this.message = error.message;

}
WsPubSubError.prototype = Object.create(Error.prototype);
WsPubSubError.prototype.constructor = WsPubSubError;

module.exports = WsPubSubError;
