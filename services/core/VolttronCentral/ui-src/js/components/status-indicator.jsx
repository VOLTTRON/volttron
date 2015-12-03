'use strict';

var React = require('react');

var statusIndicatorCreators = require('../action-creators/status-indicator-action-creators');
var statusIndicatorStore = require('../stores/status-indicator-store');

var StatusIndicator = React.createClass({

	getInitialState: function () {
        var state = getStateFromStores();

        state.errors = (state.status === "error");
        state.fadeOut = false;

        return state;
    },
    componentDidMount: function () {        
        if (!this.state.errors)
        {   
        	this.fadeTimer = setTimeout(this._fadeForClose, 4000);
            this.closeTimer = setTimeout(this._autoCloseOnSuccess, 5000);
        }
    },
    _fadeForClose: function () {
    	this.setState({ fadeOut: true });
    },
    _keepVisible: function (evt) {
    	if (this.fadeTimer)
    	{
    		this.setState({ fadeOut: false });

    		clearTimeout(this.fadeTimer);
    		clearTimeout(this.closeTimer);

    		evt.currentTarget.addEventListener("mouseleave", this._closeOnMouseOut);
    	}
    },
    _closeOnMouseOut: function () {
    	if (!this.state.errors)
        {   
        	this.fadeTimer = setTimeout(this._fadeForClose, 0);
            this.closeTimer = setTimeout(this._autoCloseOnSuccess, 1000);
        }
    },
    _autoCloseOnSuccess: function () {
    	statusIndicatorCreators.closeStatusIndicator();
    },
    _onCloseClick: function () {
        statusIndicatorCreators.closeStatusIndicator();
    },

	render: function () {
		var classes = ["status-indicator"];

		var green = "#A1D490";
		var red = "#CC5056";

		var displayButton = "none";
		var color = green;
        
        if (this.state.errors)
        {
			displayButton = "block";
			color = red;
        }
        else if (this.state.fadeOut)
        {
        	classes.push("hide-slow");
        }

        var buttonStyle = {			
			margin: "auto"
		};

		var colorStyle = {
			background: color,
			width: "100%",
			height: "2rem",
			margin: "0"
		}

		var buttonDivStyle = {
			width: "100%",
			height: "3rem",
			display: displayButton
		}

		var spacerStyle = {
			width: "100%",
			height: "2rem"
		}

		return (
		
        	<div 
        		className={classes.join(' ')}
        		onMouseEnter={this._keepVisible}
        	>
				<div style={colorStyle}/>
				<br/>
				{this.state.statusMessage}
                <div style={spacerStyle}></div>  
                <div style={buttonDivStyle}>
	                <button
	                    className="button"
	                    style={buttonStyle}
	                    onClick={this._onCloseClick}
	                >
	                    Close
	                </button>
                </div>
			</div>
        
			
		);
	},
});

function getStateFromStores() {
    return {
        status: statusIndicatorStore.getStatus(),
        statusMessage: statusIndicatorStore.getStatusMessage(),
    };
}

module.exports = StatusIndicator;
