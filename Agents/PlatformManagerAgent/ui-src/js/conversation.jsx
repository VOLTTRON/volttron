'use strict';

var $ = require('jquery');
var React = require('react');

var Exchange = require('./exchange');

var Conversation = React.createClass({
    componentDidMount: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }
    },
    componentDidUpdate: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    render: function () {
        return (
            <div ref="conversation" className="conversation">
                {this.props.exchanges.map(function (exchange, index) {
                    return (
                        <Exchange key={index} exchange={exchange} />
                    );
                })}
            </div>
        );
    }
});

module.exports = Conversation;
