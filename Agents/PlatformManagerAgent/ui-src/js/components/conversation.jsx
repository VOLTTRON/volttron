'use strict';

var $ = require('jquery');
var React = require('react');

var Exchange = require('./exchange');
var messengerStore = require('../stores/messenger-store');

var Conversation = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }

        messengerStore.addChangeListener(this._onChange);
    },
    componentDidUpdate: function () {
        var $conversation = $(this.refs.conversation.getDOMNode());

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    componentWillUnmount: function () {
        messengerStore.removeChangeListener(this._onChange);
    },
    _onChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        return (
            <div ref="conversation" className="conversation">
                {this.state.exchanges.map(function (exchange, index) {
                    return (
                        <Exchange key={index} exchange={exchange} />
                    );
                })}
            </div>
        );
    }
});

function getStateFromStores() {
    return { exchanges: messengerStore.getExchanges() };
}

module.exports = Conversation;
