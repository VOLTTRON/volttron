'use strict';

function XhrError(message) {
    this.name = 'XhrError';
    this.message = message;
}
XhrError.prototype = Object.create(Error.prototype);
XhrError.prototype.constructor = XhrError;

module.exports = XhrError;
