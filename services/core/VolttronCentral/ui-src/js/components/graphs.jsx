'use strict';

var React = require('react');
var Router = require('react-router');
var Graph = require('./graph');

var graphStore = require('../stores/graph-store');

var Graphs = React.createClass({
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

        var graph = <Graph/>

        return (
                <div>
                    <div className="view">
                        <h2>Graphs</h2>
                        {graph}
                    </div>
                </div>
        );
    },
});

function getStateFromStores() {
    return {
        graphs: graphStore.getGraphs(),
    };
}

module.exports = Graphs;
