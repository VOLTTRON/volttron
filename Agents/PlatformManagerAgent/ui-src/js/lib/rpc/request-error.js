'use strict';

function RequestError(message) {
    this.name = 'RequestError';
    this.message = message;
}
RequestError.prototype = Object.create(Error.prototype);
RequestError.prototype.constructor = RequestError;

RequestError.prototype.toJSON = function () {
    return this.message;
};

module.exports = RequestError;
