'use strict';

var React = require('react');

var Composer = require('./composer');
var Conversation = require('./conversation');
var MessengerModel = require('./messenger-model');

var model = new MessengerModel();

var App = React.createClass({
    render: function () {
        return (
            <div className="messenger">
                <Conversation exchanges={this.props.model.exchanges} />
                <Composer sendRequestFn={this.props.model.sendRequest.bind(this.props.model)} />
            </div>
        );
    }
});

model.addSubscriber(render);

function render() {
    React.render(
        <App model={model} />,
        document.getElementById('messenger')
    );
}

render();
