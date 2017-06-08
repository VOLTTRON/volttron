'use strict';

import React from 'react';
import BaseComponent from './base-component';

var controlButtonStore = require('../stores/control-button-store');
var controlButtonActionCreators = require('../action-creators/control-button-action-creators');
var OutsideClick = require('react-click-outside');

class ControlButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange', 'handleClickOutside', '_showTaptip', '_hideTaptip', '_showTooltip', '_hideTooltip');

		this.state = {};

		this.state.showTaptip = false;
		this.state.showTooltip = false;
		this.state.deactivateTooltip = false;

        this.state.selected = (this.props.selected === true);

		this.state.taptipX = 0;
		this.state.taptipY = 0;
        this.state.tooltipX = 0;
        this.state.tooltipY = 0;

        this.state.tooltipOffsetX = 0;
        this.state.tooltipOffsetY = 0;
        this.state.taptipOffsetX = 0;
        this.state.taptipOffsetY = 0;

        if (this.props.hasOwnProperty("tooltip"))
        {
            if (this.props.tooltip.hasOwnProperty("x"))
                this.state.tooltipX = this.props.tooltip.x;

            if (this.props.tooltip.hasOwnProperty("y"))
                this.state.tooltipY = this.props.tooltip.y;
            
            if (this.props.tooltip.hasOwnProperty("xOffset"))
                this.state.tooltipOffsetX = this.props.tooltip.xOffset;

            if (this.props.tooltip.hasOwnProperty("yOffset"))
                this.state.tooltipOffsetY = this.props.tooltip.yOffset;
        }

        if (this.props.hasOwnProperty("taptip"))
        {
            if (this.props.taptip.hasOwnProperty("x"))
                this.state.taptipX = this.props.taptip.x;

            if (this.props.taptip.hasOwnProperty("y"))
                this.state.taptipY = this.props.taptip.y;
            
            if (this.props.taptip.hasOwnProperty("xOffset"))
                this.state.taptipOffsetX = this.props.taptip.xOffset;

            if (this.props.taptip.hasOwnProperty("yOffset"))
                this.state.taptipOffsetY = this.props.taptip.yOffset;
        }
	}
    componentDidMount() {
        controlButtonStore.addChangeListener(this._onStoresChange);

        window.addEventListener('keydown', this._hideTaptip);
    }
    componentWillUnmount() {
        controlButtonStore.removeChangeListener(this._onStoresChange);

        window.removeEventListener('keydown', this._hideTaptip);
    }
    componentWillReceiveProps(nextProps) {
    	this.setState({ selected: (nextProps.selected === true) });

    	if (nextProps.selected === true) 
    	{
    		this.setState({ showTooltip: false });
    	}
    }
    _onStoresChange() {

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

                if (typeof this.props.taptip.getTaptipRef === "function")
                {
                    this.props.taptip.getTaptipRef(this.taptip);
                }
	    	}
            else
            {
                if (typeof this.props.closeAction == 'function')
                {
                    this.props.closeAction();
                }

                this.taptip.style.top = this.state.taptipY + "px";
            }
	    }
    }
    handleClickOutside() {
        if (this.state.showTaptip)
        {
            controlButtonActionCreators.hideTaptip(this.props.name);
        }

        if (this.state.showTooltip)
        {
            this._hideTooltip();
        }
    }
	_showTaptip(evt) {

		if (!this.state.showTaptip)
		{
            if (!(this.props.taptip.hasOwnProperty("x") && this.props.taptip.hasOwnProperty("y")))
            {            
                this.setState({taptipX: evt.clientX - this.state.taptipOffsetX});
                this.setState({taptipY: evt.clientY - this.state.taptipOffsetY});    
            }
		}

		controlButtonActionCreators.toggleTaptip(this.props.name);
	}
	_hideTaptip(evt) {
		if (evt.keyCode === 27) 
		{
	        controlButtonActionCreators.hideTaptip(this.props.name);
        }
	}
    _showTooltip(evt) {
        this.setState({showTooltip: true});

        if (!this.props.tooltip.hasOwnProperty("x"))
        {
            this.setState({tooltipX: evt.clientX - this.state.tooltipOffsetX});
        }

        if (!this.props.tooltip.hasOwnProperty("y"))
        {
            this.setState({tooltipY: evt.clientY - this.state.tooltipOffsetY});
        }
    }
    _hideTooltip() {
        this.setState({showTooltip: false});
    }
    render() {
        
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
            var showTooltip = (this.state.showTooltip || this.props.triggerTooltip);

        	var tooltipStyle = {
	            display: (showTooltip ? "block" : "none"),
	            position: "absolute",
	            top: this.state.tooltipY + "px",
	            left: this.state.tooltipX + "px"
	        };

	        var toolTipClasses = ["tooltip_outer"];

            if (showTooltip)
            {
                toolTipClasses.push("delayed-show-slow");
            }

            if (this.props.tooltip.tooltipClass)
            {
                toolTipClasses.push(this.props.tooltip.tooltipClass);
            }

	        tooltipShow = this._showTooltip;
	        tooltipHide = this._hideTooltip;

            var tooltipContent = this.props.tooltip.content;
            
            if (this.props.tooltip.nobr)
            {
                tooltipContent = (
                    <nobr>
                        {this.props.tooltip.content}
                    </nobr>
                );
            }

            tooltip = (
                <div className={toolTipClasses.join(" ")}
                    style={tooltipStyle}>
                    <div className="tooltip_inner">
                        <div className="opaque_inner">
                            {tooltipContent}
                        </div>
                    </div>
                </div>
            );
        }
        

        if (this.props.taptip)
        {
            var taptipStyle = {
		        display: (this.state.showTaptip ? "block" : "none"),
		        position: "absolute",
		        left: this.state.taptipX + "px",
		        top: this.state.taptipY + "px"
		    };

            if (this.props.taptip.styles)
            {
                this.props.taptip.styles.forEach(function (styleToAdd) {
                    taptipStyle[styleToAdd.key] = styleToAdd.value;
                });
            }

		    var tapTipClasses = ["taptip_outer"];

            if (this.props.taptip.taptipClass)
            {
                tapTipClasses.push(this.props.taptip.taptipClass);
            }

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
		    	<div className={tapTipClasses.join(" ")}
	                style={taptipStyle}
                    ref={function(div) {
                        this.taptip = div;
                    }.bind(this)}>
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

        var centering = (this.props.hasOwnProperty("nocentering") && (this.props.nocentering === true) ?
                            "" : "centeredDiv");

        var outerClasses = ((this.props.hasOwnProperty("outerclass") && this.props.outerclass) ? this.props.outerclass :
                                (this.props.hasOwnProperty("floatleft") && (this.props.floatleft === true) ?
                                    "floatLeft" : "inlineBlock") );

        return (
            <div className={outerClasses}>
            	{taptip}
            	{tooltip}
                <div className={controlButtonClass}
                    onClick={clickAction}                  
                    onMouseEnter={tooltipShow}
                    onMouseLeave={tooltipHide}
                    style={selectedStyle}>
                    <div className={centering}>
                        {buttonIcon}
                    </div>
                </div>                  
            </div>
        );
    }
}

export default OutsideClick(ControlButton);
