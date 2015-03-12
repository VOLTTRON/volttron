'use strict';

var $ = require('jquery');

var MessengerModel = function () {
    if (!this instanceof MessengerModel) {
        return new MessengerModel();
    }

    this.exchanges = [];
    this.subscribers = [];
};

MessengerModel.prototype.addSubscriber = function (subscriber) {
    if (this.subscribers.indexOf(subscriber) < 0) {
        this.subscribers.push(subscriber);
    }
};

MessengerModel.prototype.notifySubscribers = function () {
    this.subscribers.forEach(function (subscriber) {
        subscriber();
    });
};

MessengerModel.prototype.sendRequest = function (request) {
    var exchange = {
        requestSent: Date.now(),
        request: request,
    };

    this.exchanges.push(exchange);
    this.notifySubscribers();

    var model = this;

    $.ajax({
        method: 'POST',
        url: '/api/',
        data: JSON.stringify(request),
        contentType: 'application/json',
        timeout: 60000,
        success: function (response) {
            exchange.responseReceived = Date.now();
            exchange.response = response;
            model.notifySubscribers();
        },
        error: function (response, type) {
            switch (type) {
            case 'error':
                exchange.response = 'Server returned ' + response.status + ' status';
                break;
            case 'timeout':
                exchange.response = 'Request timed out';
                break;
            default:
                exchange.response = 'Request failed: ' + type;
            }

            model.notifySubscribers();
        }
    });
};

module.exports = MessengerModel;
