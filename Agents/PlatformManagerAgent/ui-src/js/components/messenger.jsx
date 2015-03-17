'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');
var MessengerModel = require('../models/messenger-model');

var model = new MessengerModel();

var Messenger = React.createClass({
    componentDidMount: function () {
        model.addSubscriber(this.forceUpdate.bind(this));
    },
    render: function () {
        return (
            <div className="messenger">
                <Conversation exchanges={model.exchanges} />
                <Composer sendRequestFn={model.sendRequest.bind(model)} />
            </div>
        );
    }
});

module.exports = Messenger;
