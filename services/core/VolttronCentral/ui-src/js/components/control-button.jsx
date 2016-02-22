'use strict';

var React = require('react');
var Router = require('react-router');


var ControlButton = React.createClass({
	getInitialState: function () {
		var state = {};

		state.showTaptip = false;
		state.taptipX = 0;
		state.taptipY = 0;

		return state;
	},
	_showTaptip: function (evt) {

		if (!this.state.showTaptip)
		{
			this.setState({taptipX: evt.clientX - 60});
			this.setState({taptipY: evt.clientY - 120});
		}

		this.setState({showTaptip: !this.state.showTaptip});
	},
    render: function () {
        
        var taptip;
        var clickAction;

        if (this.props.taptip)
        {
        	var taptipStyle = {
		        display: (this.state.showTaptip ? "block" : "none"),
		        position: "absolute",
		        left: this.state.taptipX + "px",
		        top: this.state.taptipY + "px"
		    };

		    var tapTipClasses = "taptip_outer";

		    taptip = (
		    	<div className={tapTipClasses}
	                style={taptipStyle}>
	                <div className="taptip_inner">
	                    <div className="opaque_inner">
	                        <h4>{this.props.taptip.title}</h4>
	                        <br/>
	                        {this.props.taptip.content}
	                    </div>
	                </div>
	            </div>
        	);

        	clickAction = (this.props.taptip.action ? this.props.taptip.action : this._showTaptip);
        }
        else if (this.props.clickAction)
        {
        	clickAction = this.props.clickAction;
        }

        return (
            <div className="inlineBlock">
            	{taptip}
                <div className="control_button"
                    onClick={clickAction}>
                    <div className="centeredDiv">
                        {this.props.icon}
                    </div>
                </div>                  
            </div>
        );
    },
});







module.exports = ControlButton;
