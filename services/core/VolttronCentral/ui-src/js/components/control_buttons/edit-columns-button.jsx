'use strict';

import React from 'react';
import BaseComponent from '../base-component';

import ControlButton from '../control-button';
var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');

class EditColumnButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_onFindBoxChange", "_onReplaceBoxChange", "_findNext", "_onClearEdit", "_replace", "_replaceAll",
                    "_onKeyDown");

        this.state = {
            findValue: "",
            replaceValue: ""
        };
    }
    _onFindBoxChange(e) {
        var findValue = e.target.value;

        this.setState({ findValue: findValue });        

        this.props.onclear(this.props.column);        
    }
    _onKeyDown(callback, e) {

        if (e.keyCode === 13) //Enter
        {
            callback();
        }
    }
    _onReplaceBoxChange(e) {
        var replaceValue = e.target.value;

        this.setState({ replaceValue: replaceValue });
    }
    _findNext() {

        if (this.state.findValue === "")
        {
            this.props.onclear(this.props.column);
        }
        else
        {
            this.props.findnext(this.state.findValue, this.props.column);
        }
    }
    _onClearEdit(e) {

        this.props.onclear(this.props.column);
        this.setState({ findValue: "" });
        this.setState({ replaceValue: "" });
        controlButtonActionCreators.hideTaptip(this.props.name);

    }
    _replace() {    
        if (this.props.replaceEnabled)    
        {
            this.props.replace(this.state.findValue, this.state.replaceValue, this.props.column);
        }
    }
    _replaceAll() {
        if (this.props.replaceEnabled)    
        {
            this.props.replaceall(this.state.findValue, this.state.replaceValue, this.props.column);
        }
    }
    render() {

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

        var replaceEnabled = (!this.props.replaceEnabled ? "disableReplace plain" : "plain");

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
                                        onKeyDown={this._onKeyDown.bind(this, this._findNext)}
                                        value={ this.state.findValue }
                                    />
                                </td>
                                <td className="plain">
                                    <div style={buttonsStyle}>
                                        <ControlButton 
                                            fontAwesomeIcon="step-forward"
                                            tooltip={findTooltip}
                                            clickAction={this._findNext}/>
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td className={replaceEnabled}
                                    colSpan="2">
                                    Replace With
                                </td>
                            </tr>
                            <tr>
                                <td className={replaceEnabled}>
                                    <input
                                        type="text"
                                        style={inputStyle}
                                        onChange={this._onReplaceBoxChange}
                                        onKeyDown={this._onKeyDown.bind(this, this._replace)}
                                        value={ this.state.replaceValue }
                                        disabled={ !this.props.replaceEnabled }
                                    />
                                </td>
                                <td className={replaceEnabled}>
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
            "x": 80,
            "y": -150,
            "styles": [{"key": "width", "value": "250px"}],
            "break": "",
            "getTaptipRef": function (taptip) {
                if (typeof this.props.taptipRef === "function")
                {
                    this.props.taptipRef(taptip);
                }
            }.bind(this)
        };
        
        var editTooltip = {
            "content": this.props.tooltipMsg,
            "x": 160,
            "y": 0
        };

        var columnIndex = this.props.column;

        

        return (
            <ControlButton
                name={this.props.name}
                taptip={editTaptip}
                tooltip={editTooltip}
                fontAwesomeIcon="pencil"                
                controlclass="edit_column_button"
                closeAction={this.props.onhide}/>
        );
    }
};

export default EditColumnButton;