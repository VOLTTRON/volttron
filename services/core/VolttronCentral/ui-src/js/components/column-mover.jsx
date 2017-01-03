'use strict';

import React from 'react';
import BaseComponent from './base-component';

var columnMoverStore = require('../stores/column-mover-store');

class ColumnMover extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange');

        this.state = columnMoverStore.getColumnMover();
    }
    componentDidMount() {
        columnMoverStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount() {
        columnMoverStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {
    	this.setState(columnMoverStore.getColumnMover());
    }
	render () {

		var moverStyle = {
			display: this.state.style.display,
			left: this.state.style.left + "px",
			height: this.state.style.height + "px",
			top: this.state.style.top + "px"
		}
		return (
			<div className="column-mover"
				style={moverStyle}>
			</div>
		);
	}
};

export default ColumnMover;
