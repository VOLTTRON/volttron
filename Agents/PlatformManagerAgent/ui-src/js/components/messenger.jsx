'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');

var Messenger = React.createClass({
    render: function () {
        return (
            <div className="messenger">
                <Conversation />
                <Composer />
            </div>
        );
    }
});

module.exports = Messenger;
