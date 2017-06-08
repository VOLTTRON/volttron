'use strict';

var React = require('react');

var statusIndicatorCreators = require('../action-creators/status-indicator-action-creators');
var statusIndicatorStore = require('../stores/status-indicator-store');

var StatusIndicator = React.createClass({

	getInitialState: function () {
        var state = this.props.status;

        state.errors = (state.status === "error");
        state.fadeOut = false;

        return state;
    },
    componentWillReceiveProps: function (nextProps) {
        if ((nextProps.status.statusMessage !== this.props.status.statusMessage) ||
            (nextProps.status.status !== this.props.status.status))
        {
            var state = nextProps.status;

            state.errors = (state.status === "error");
            state.fadeOut = false;

            this.setState(state);
        }
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

		var green = "#35B809";
		var red = "#FC0516";

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

        var messageStyle = {
            padding: "0px 20px"
        }

        var statusMessage = (<b>{this.state.statusMessage}</b>);

        if (this.state.hasOwnProperty("highlight"))
        {
            var highlight = this.state.highlight;
            var wholeMessage = this.state.statusMessage;

            var startIndex = wholeMessage.indexOf(highlight);

            if (startIndex > -1)
            {
                var newMessage = [];

                if (startIndex === 0)
                {
                    newMessage.push(<b key="b1">{wholeMessage.substring(0, highlight.length)}</b>);
                    newMessage.push(<span key="span1">{wholeMessage.substring(highlight.length)}</span>);
                }
                else
                {
                    newMessage.push(<span key="span1">{wholeMessage.substring(0, startIndex)}</span>);
                    newMessage.push(<b key="b1">{wholeMessage.substring(startIndex, startIndex + highlight.length)}</b>);
                    newMessage.push(<span key="span2">{wholeMessage.substring(startIndex + highlight.length)}</span>);
                }

                statusMessage = newMessage;
            }
        }

        messageStyle.textAlign = (this.state.hasOwnProperty("align") ? this.state.align : "left");

		return (
		
        	<div 
        		className={classes.join(' ')}
        		onMouseEnter={this._keepVisible}
        	>
				<div style={colorStyle}/>
				<br/>
				<div style={messageStyle}>{statusMessage}</div>
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


module.exports = StatusIndicator;
