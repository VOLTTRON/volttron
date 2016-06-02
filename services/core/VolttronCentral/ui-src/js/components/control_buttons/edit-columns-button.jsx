'use strict';

var React = require('react');

var ControlButton = require('../control-button');
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');
// var controlButtonStore = require('../../stores/control-button-store');

var EditColumnButton = React.createClass({
    getInitialState: function () {
        return getStateFromStores();
    },
    _onFindBoxChange: function (e) {
        var findValue = e.target.value;

        this.setState({ findValue: findValue });        

        this.props.onclear(this.props.column);        
    },
    _onReplaceBoxChange: function (e) {
        var replaceValue = e.target.value;

        this.setState({ replaceValue: replaceValue });
    },
    _findNext: function () {

        if (this.state.findValue === "")
        {
            this.props.onclear(this.props.column);
        }
        else
        {
            this.props.findnext(this.state.findValue, this.props.column);
        }
    },
    _onClearEdit: function (e) {

        this.props.onclear(this.props.column);
        this.setState({ findValue: "" });
        this.setState({ replaceValue: "" });
        controlButtonActionCreators.hideTaptip("editControlButton" + this.props.column);

    },
    _replace: function () {        
        this.props.replace(this.state.findValue, this.state.replaceValue, this.props.column);
    },
    _replaceAll: function () {
        this.props.replaceall(this.state.findValue, this.state.replaceValue, this.props.column);
    },
    render: function () {

        var editBoxContainer = {
            position: "relative"
        };

        var inputStyle = {
            width: "100%",
            marginLeft: "10px",
            fontWeight: "normal"
        }

        var divWidth = {
            width: "85%"
        }

        var clearTooltip = {
            content: "Clear Search",
            x: 50,
            y: 0
        }

        var findTooltip = {
            content: "Find Next",
            x: 100,
            y: 0
        }

        var replaceTooltip = {
            content: "Replace",
            x: 100,
            y: 80
        }

        var replaceAllTooltip = {
            content: "Replace All",
            x: 100,
            y: 80
        }

        var buttonsStyle={
            marginTop: "8px"
        }

        var editBox = (
            <div style={editBoxContainer}>
                <ControlButton 
                    fontAwesomeIcon="ban"
                    tooltip={clearTooltip}
                    clickAction={this._onClearEdit}/>
                <div>
                    <table>
                        <tbody>
                            <tr>
                                <td colSpan="2">
                                    Find in Column
                                </td>
                            </tr>
                            <tr>
                                <td width="70%">
                                    <input
                                        type="text"
                                        style={inputStyle}
                                        onChange={this._onFindBoxChange}
                                        value={ this.state.findValue }
                                    />
                                </td>
                                <td>
                                    <div style={buttonsStyle}>
                                        <ControlButton 
                                            fontAwesomeIcon="step-forward"
                                            tooltip={findTooltip}
                                            clickAction={this._findNext}/>
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td colSpan="2">
                                    Replace With
                                </td>
                            </tr>
                            <tr>
                                <td>
                                    <input
                                        type="text"
                                        style={inputStyle}
                                        onChange={this._onReplaceBoxChange}
                                        value={ this.state.replaceValue }
                                    />
                                </td>
                                <td>
                                    <div className="inlineBlock"
                                            style={buttonsStyle}>
                                        <ControlButton 
                                            fontAwesomeIcon="step-forward"
                                            tooltip={replaceTooltip}
                                            clickAction={this._replace}/>

                                        <ControlButton 
                                            fontAwesomeIcon="fast-forward"
                                            tooltip={replaceAllTooltip}
                                            clickAction={this._replaceAll}/>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div> 
        );

        var editTaptip = { 
            "title": "Search Column", 
            "content": editBox,
            "x": 100,
            "y": 24,
            "styles": [{"key": "width", "value": "250px"}]
        };
        
        var editTooltip = {
            "content": this.props.tooltipMsg,
            "x": 160,
            "y": 0
        };

        var columnIndex = this.props.column;

        

        return (
            <ControlButton
                name={"editControlButton" + columnIndex}
                taptip={editTaptip}
                tooltip={editTooltip}
                fontAwesomeIcon="pencil"
                controlclass="edit_column_button"/>
        );
    },
});

function getStateFromStores() {
    return {
        findValue: "",
        replaceValue: ""
    };
}

module.exports = EditColumnButton;