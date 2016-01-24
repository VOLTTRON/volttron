'use strict';

var React = require('react');
var Router = require('react-router');

var graphStore = require('../stores/graph-store');

var Graph = React.createClass({
    getInitialState: getStateFromStores,
    componentDidMount: function () {
        graphStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        graphStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    render: function () {
        var graphs  = [];

        return (
            <div className="view">
                <h2>Graph</h2>
                {graphs}
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        graphs: graphStore.getGraphs(),
    };
}

module.exports = Graph;
