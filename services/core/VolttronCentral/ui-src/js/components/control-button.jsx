'use strict';

var React = require('react');
var Router = require('react-router');
var controlButtonStore = require('../stores/control-button-store');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');


var ControlButton = React.createClass({
    mixins: [
        require('react-onclickoutside')
    ],
	getInitialState: function () {
		var state = {};

		state.showTaptip = false;
		state.showTooltip = false;
		state.deactivateTooltip = false;

        state.selected = (this.props.selected === true);

		state.taptipX = 0;
		state.taptipY = 0;
        state.tooltipX = 0;
        state.tooltipY = 0;

        state.tooltipOffsetX = 0;
        state.tooltipOffsetY = 0;
        state.taptipOffsetX = 0;
        state.taptipOffsetY = 0;

        if (this.props.hasOwnProperty("tooltip"))
        {
            if (this.props.tooltip.hasOwnProperty("x"))
                state.tooltipX = this.props.tooltip.x;

            if (this.props.tooltip.hasOwnProperty("y"))
                state.tooltipY = this.props.tooltip.y;
            
            if (this.props.tooltip.hasOwnProperty("xOffset"))
                state.tooltipOffsetX = this.props.tooltip.xOffset;

            if (this.props.tooltip.hasOwnProperty("yOffset"))
                state.tooltipOffsetY = this.props.tooltip.yOffset;
        }

        if (this.props.hasOwnProperty("taptip"))
        {
            if (this.props.taptip.hasOwnProperty("x"))
                state.taptipX = this.props.taptip.x;

            if (this.props.taptip.hasOwnProperty("y"))
                state.taptipY = this.props.taptip.y;
            
            if (this.props.taptip.hasOwnProperty("xOffset"))
                state.taptipOffsetX = this.props.taptip.xOffset;

            if (this.props.taptip.hasOwnProperty("yOffset"))
                state.taptipOffsetY = this.props.taptip.yOffset;
        }

		return state;
	},
    componentDidMount: function () {
        controlButtonStore.addChangeListener(this._onStoresChange);

        window.addEventListener('keydown', this._hideTaptip);
    },
    componentWillUnmount: function () {
        controlButtonStore.removeChangeListener(this._onStoresChange);

        window.removeEventListener('keydown', this._hideTaptip);
    },
    componentWillReceiveProps: function (nextProps) {
    	this.setState({ selected: (nextProps.selected === true) });

    	if (nextProps.selected === true) 
    	{
    		this.setState({ showTooltip: false });
    	}    	
    },
    _onStoresChange: function () {

    	var showTaptip = controlButtonStore.getTaptip(this.props.name);
    	
    	if (showTaptip !== null)
    	{
	    	if (showTaptip !== this.state.showTaptip)
	    	{
	    		this.setState({ showTaptip: showTaptip });	
	    	}
            
            this.setState({ selected: (showTaptip === true) }); 

	    	if (showTaptip === true)
	    	{
	    		this.setState({ showTooltip: false });
	    	}
            else
            {
                if (typeof this.props.closeAction == 'function')
                {
                    this.props.closeAction();
                }
            }
	    }
    },
    handleClickOutside: function () {
        if (this.state.showTaptip)
        {
            controlButtonActionCreators.hideTaptip(this.props.name);
        }
    },
	_showTaptip: function (evt) {

		if (!this.state.showTaptip)
		{
            if (!(this.props.taptip.hasOwnProperty("x") && this.props.taptip.hasOwnProperty("y")))
            {
                this.setState({taptipX: evt.clientX - this.state.taptipOffsetX});
                this.setState({taptipY: evt.clientY - this.state.taptipOffsetY});    
            }
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

        if (!(this.props.tooltip.hasOwnProperty("x") && this.props.tooltip.hasOwnProperty("y")))
        {
            this.setState({tooltipX: evt.clientX - this.state.tooltipOffsetX});
            this.setState({tooltipY: evt.clientY - this.state.tooltipOffsetY});
        }
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

        var buttonIcon = (this.props.icon ? this.props.icon :
                            (this.props.fontAwesomeIcon ? 
                                (<i className={"fa fa-" + this.props.fontAwesomeIcon}></i>) : 
                                    (<div className={this.props.buttonClass}><span>{this.props.unicodeIcon}</span></div>) ) );

        if (this.props.staySelected || this.state.selected === true || this.state.showTaptip === true)
        {
        	selectedStyle = {
	        	backgroundColor: "#ccc"
	        }
        }
        else if (this.props.tooltip)
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
        	var taptipStyle = {
		        display: (this.state.showTaptip ? "block" : "none"),
		        position: "absolute",
		        left: this.state.taptipX + "px",
		        top: this.state.taptipY + "px"
		    };

            //TODO: add this to repository
            if (this.props.taptip.styles)
            {
                this.props.taptip.styles.forEach(function (styleToAdd) {
                    taptipStyle[styleToAdd.key] = styleToAdd.value;
                });
            }
            //end TODO

		    var tapTipClasses = "taptip_outer";

            var taptipBreak = (this.props.taptip.hasOwnProperty("break") ? this.props.taptip.break : <br/>);
            var taptipTitle = (this.props.taptip.hasOwnProperty("title") ? (<h4>{this.props.taptip.title}</h4>) : "");

            var innerStyle = {};

            if (this.props.taptip.hasOwnProperty("padding"))
            {
                innerStyle = {
                    padding: this.props.taptip.padding
                }
            } 

		    taptip = (
		    	<div className={tapTipClasses}
	                style={taptipStyle}>
	                <div className="taptip_inner"
                        style={innerStyle}>
	                    <div className="opaque_inner">
	                        {taptipTitle}
	                        {taptipBreak}
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

        var controlButtonClass = (this.props.controlclass ? this.props.controlclass : "control_button");

        return (
            <div className="inlineBlock">
            	{taptip}
            	{tooltip}
                <div className={controlButtonClass}
                    onClick={clickAction}                  
                    onMouseEnter={tooltipShow}
                    onMouseLeave={tooltipHide}
                    style={selectedStyle}>
                    <div className="centeredDiv">
                        {buttonIcon}
                    </div>
                </div>                  
            </div>
        );
    },
});







module.exports = ControlButton;