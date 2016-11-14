'use strict';

import React from 'react';
import BaseComponent from './base-component';


class CheckBox extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onCheck');

		this.state = {
            checked: (this.props.selected ? this.props.selected : false)
        };
	}
    componentDidMount() {
        
    }
    componentWillUnmount() {
        
    }
    componentWillReceiveProps(nextProps) {
    	if (nextProps.selected !== this.props.selected)
        {
            this.setState({checked: nextProps.selected});
        }
    }
    _onCheck() {

        var checked = !this.state.checked;

    	this.setState({checked: checked});

        if (typeof this.props.oncheck === "function")
        {
            this.props.oncheck(checked);
        }
    }
    render() {
        
        var selected = (this.state.checked ? "selected" : "");

        var classes = (this.props.controlClass ? "vc-checkbox " + this.props.controlClass : "vc-checkbox");

        var styles = (typeof this.props.controlStyle !== "undefined" && this.props.controlStyle !== null ? this.props.controlStyle : {});

        return (
            <div className={classes}
                style={styles}>
                <div className={selected}
                    onClick={this._onCheck}>
                    <span>
                        {this.props.label}
                    </span>
                </div>
            </div>
        );
    }
}

export default CheckBox;
