'use strict';

var $ = require('jquery');
var React = require('react');
var ReactDOM = require('react-dom');

var Exchange = require('./exchange');
var consoleStore = require('../stores/console-store');

var Conversation = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        var $conversation = $(ReactDOM.findDOMNode(this.refs.conversation));

        if ($conversation.prop('scrollHeight') > $conversation.height()) {
            $conversation.scrollTop($conversation.prop('scrollHeight'));
        }

        consoleStore.addChangeListener(this._onChange);
    },
    componentDidUpdate: function () {
        var $conversation = $(ReactDOM.findDOMNode(this.refs.conversation));

        $conversation.stop().animate({ scrollTop: $conversation.prop('scrollHeight') }, 500);
    },
    componentWillUnmount: function () {
        consoleStore.removeChangeListener(this._onChange);
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
    return { exchanges: consoleStore.getExchanges() };
}

module.exports = Conversation;
