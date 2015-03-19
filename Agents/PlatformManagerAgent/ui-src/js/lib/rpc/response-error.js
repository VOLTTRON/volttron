'use strict';

function ResponseError(response) {
    this.name = 'RequestError';
    this.message = response.error.message;
    this.response = response;
}
ResponseError.prototype = Object.create(Error.prototype);
ResponseError.prototype.constructor = ResponseError;

ResponseError.prototype.toJSON = function () {
    return this.response;
};

module.exports = ResponseError;
