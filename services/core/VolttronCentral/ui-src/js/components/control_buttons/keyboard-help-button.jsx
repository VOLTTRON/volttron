'use strict';

import React from 'react';
import BaseComponent from '../base-component';
import ControlButton from '../control-button';

var controlButtonActionCreators = require('../../action-creators/control-button-action-creators');

class KeyboardHelpButton extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind("_onFindBoxChange", "_onReplaceBoxChange", "_findNext", "_onClearEdit", "_replace", "_replaceAll",
                    "_onKeyDown");

        this.state = {
            buttonName: "keyboard-help-" + this.props.deviceInfo
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
        controlButtonActionCreators.hideTaptip(this.state.buttonName);

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

        var shortcutsBoxContainer = {
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

        var replaceEnabled = (!this.props.replaceEnabled ? "disableReplace" : "");

        var shortcutsBox = (
            <div style={shortcutsBoxContainer}>
                <table>
                    <tbody>
                        <tr>
                            <td><b>Ctrl</b></td>
                            <td className="plain">Activate keyboard commands for device table that has focus.</td>
                        </tr>
                        <tr>
                            <td><b>ESC</b></td>
                            <td className="plain">Deactivate keyboard commands.</td>
                        </tr>
                        <tr>
                            <td><b>Up</b></td>
                            <td className="plain">Move keyboard selection up one row.</td>
                        </tr>
                        <tr>
                            <td><b>Down / Space</b></td>
                            <td className="plain">Move keyboard selection down one row.</td>
                        </tr>
                        <tr>
                            <td><b>Shift+Up</b></td>
                            <td className="plain">Extend keyboard selection up one row.</td>
                        </tr>
                        <tr>
                            <td><b>Shift+Down</b></td>
                            <td className="plain">Extend keyboard selection down one row.</td>
                        </tr>
                        <tr>
                            <td><b>Enter</b></td>
                            <td className="plain">Lock in keyboard selections.</td>
                        </tr>
                    </tbody>
                </table>
            </div> 
        );

        var keyboardHelpTaptip = { 
            "title": "Keyboard Shortcuts", 
            "content": shortcutsBox,
            "x": -470,
            "y": -220,
            "styles": [{"key": "width", "value": "500px"}],
            "break": ""
        };
        
        var keyboardHelpTooltip = {
            "content": "Keyboard Shortcuts",
            "x": -60,
            "y": -100
        };

        return (
            <ControlButton
                name={this.state.buttonName}
                taptip={keyboardHelpTaptip}
                tooltip={keyboardHelpTooltip}
                fontAwesomeIcon="keyboard-o"
                outerclass="keyboard_help_button"                
                controlclass="keyboard-help"/>
        );
    }
};

export default KeyboardHelpButton;