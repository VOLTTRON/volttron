'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');

var Console = React.createClass({
    render: function () {
        return (
            <div className="console">
                <Conversation />
                <Composer />
            </div>
        );
    }
});

module.exports = Console;
