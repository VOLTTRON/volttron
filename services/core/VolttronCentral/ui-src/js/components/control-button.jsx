'use strict';

var React = require('react');
var Router = require('react-router');
var controlButtonStore = require('../stores/control-button-store');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');


var ControlButton = React.createClass({
	getInitialState: function () {
		var state = {};

		state.showTaptip = false;
		state.taptipX = 0;
		state.taptipY = 0;

		return state;
	},
    componentDidMount: function () {
    	// controlButtonActionCreators.addControlButton(this.props.name);
        controlButtonStore.addChangeListener(this._onStoresChange);

        window.addEventListener('keydown', this._hideTaptip);
    },
    componentWillUnmount: function () {
    	// controlButtonActionCreators.removeControlButton(this.props.name)
        controlButtonStore.removeChangeListener(this._onStoresChange);

        window.removeEventListener('keydown', this._hideTaptip);
    },
    _onStoresChange: function () {

    	var showTaptip = controlButtonStore.getTaptip(this.props.name);

    	if (showTaptip !== null)
    	{
	    	if (showTaptip !== this.state.showTaptip)
	    	{
	    		this.setState({ showTaptip: showTaptip });	
	    	}
	    }
    },
	_showTaptip: function (evt) {

		if (!this.state.showTaptip)
		{
			this.setState({taptipX: evt.clientX - 60});
			this.setState({taptipY: evt.clientY - 120});
		}

		controlButtonActionCreators.toggleTaptip(this.props.name);
	},
	_hideTaptip: function (evt) {
		if (evt.keyCode === 27) 
		{
	        controlButtonActionCreators.hideTaptip(this.props.name);
        }
	},
    _showTooltip: function (evt) {
        this.setState({showTooltip: true});
        this.setState({tooltipX: evt.clientX - 60});
        this.setState({tooltipY: evt.clientY - 120});
    },
    _hideTooltip: function () {
        this.setState({showTooltip: false});
    },
    render: function () {
        
        var taptip;
        var tooltip;
        var clickAction;
        var selectedStyle;

        var tooltipShow;
        var tooltipHide;

        if (this.props.tooltip)
        {
        	var tooltipStyle = {
	            display: (this.state.showTooltip ? "block" : "none"),
	            position: "absolute",
	            top: this.state.tooltipY + "px",
	            left: this.state.tooltipX + "px"
	        };

	        var toolTipClasses = (this.state.showTooltip ? "tooltip_outer delayed-show-slow" : "tooltip_outer");

	        tooltipShow = this._showTooltip;
	        tooltipHide = this._hideTooltip;

        	tooltip = (<div className={toolTipClasses}
                        style={tooltipStyle}>
                        <div className="tooltip_inner">
                            <div className="opaque_inner">
                                {this.props.tooltip.content}
                            </div>
                        </div>
                    </div>)
        }
        

        if (this.props.taptip)
        {
        	if (this.state.showTaptip === true)
        	{
        		selectedStyle = {
		        	backgroundColor: "#ccc"
		        }
        	}

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

        	selectedStyle = this.props.selectedStyle;
        }

        return (
            <div className="inlineBlock">
            	{taptip}
            	{tooltip}
                <div className="control_button"
                    onClick={clickAction}                  
                    onMouseEnter={tooltipShow}
                    onMouseLeave={tooltipHide}
                    style={selectedStyle}>
                    <div className="centeredDiv">
                        {this.props.icon}
                    </div>
                </div>                  
            </div>
        );
    },
});







module.exports = ControlButton;
