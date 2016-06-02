'use strict';

var React = require('react');
var Router = require('react-router');

var platformsStore = require('../stores/platforms-store');
var devicesActionCreators = require('../action-creators/devices-action-creators');

var DetectDevices = React.createClass({
    getInitialState: function () {
        var state = getStateFromStores();

        state.deviceRangeSelected = true;
        state.selectedProtocol = "udp_ip";
        state.udpPort = "";
        state.deviceStart = "";
        state.deviceEnd = "";
        state.address = "";

        return state;
    },
    componentDidMount: function () {
        // platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        // platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores());
    },
    _doScan: function () {
        devicesActionCreators.scanForDevices(this.props.platform);
    },
    _cancelScan: function () {
        devicesActionCreators.cancelScan(this.props.platform);
    },
    _continue: function () {
        devicesActionCreators.listDetectedDevices(this.props.platform);
    },
    _onDeviceRangeSelect: function (evt) {
        var deviceRangeSelected = evt.target.checked;
        this.setState({ deviceRangeSelected: deviceRangeSelected });
    },
    _onAddressSelect: function (evt) {
        var addressSelected = evt.target.checked;
        this.setState({ deviceRangeSelected: !addressSelected });
    },
    _onIpSelect: function (evt) {
        var selectedProtocol = evt.target.value;
        this.setState({ selectedProtocol: selectedProtocol });
    },
    _onPortInput: function (evt) {
        var udpPort = evt.target.value;
        this.setState({ udpPort: udpPort });
    },
    _onDeviceStart: function (evt) {
        var deviceStart = evt.target.value;
        this.setState({ deviceStart: deviceStart });
    },
    _onDeviceEnd: function (evt) {
        var deviceEnd = evt.target.value;
        this.setState({ deviceEnd: deviceEnd });
    },
    _onAddress: function (evt) {
        var address = evt.target.value;
        this.setState({ address: address });
    },
    render: function () {        
        
        var devices;

        switch (this.props.action)
        {
            case "start_scan":

                var containerStyle = {
                    width: "400px",
                    height: "400px"
                }

                var progressStyle = {
                    height: "40%",
                    clear: "both",
                    padding: "80px 0px 0px 200px"
                }

                var labelStyle = {
                    fontSize: "24px"
                }

                devices = (
                    <div style={containerStyle}>
                        <div style={progressStyle}>
                            <i className="fa fa-cog fa-spin fa-5x fa-fw margin-bottom"></i>
                            <br/>
                            <div style={labelStyle}>
                                <span>Detecting...</span>
                            </div>
                        </div>
                        <div className="inlineBlock">
                            <div className="inlineBlock">
                                <button onClick={this._cancelScan}>Cancel</button>
                            </div>
                            <div className="inlineBlock">
                                <button onClick={this._continue}>Continue</button>
                            </div>
                        </div>
                    </div>
                )

                break;
            case "get_scan_settings":

                var selectStyle = {
                    height: "24px",
                    width: "151px"
                }

                var radioStyle = {
                    width: "20px",
                    float: "left",
                    height: "20px",
                    paddingTop: "4px"
                }

                var buttonStyle = {
                    display: (((this.state.deviceRangeSelected 
                                    && this.state.deviceStart !== "" 
                                    && this.state.deviceEnd !== "") || 
                                (!this.state.deviceRangeSelected 
                                    && this.state.address !== "")) &&
                              (this.state.udpPort !== "") ? "block" : "none")
                }

                var addressStyle = {
                    color: (this.state.deviceRangeSelected ? "gray" : "black")
                };

                var deviceRangeStyle = {
                    color: (this.state.deviceRangeSelected ? "black" : "gray")
                };

                devices = (
                    <div className="detectDevicesContainer">
                        <div className="detectDevicesBox">
                            <table>
                                <tbody>
                                    <tr>
                                        <td className="table_label">Network Interface</td>
                                        <td className="plain">
                                            <select 
                                                style={selectStyle}
                                                onChange={this._onIpSelect}
                                                value={this.state.selectedProtocol}>
                                                <option value="udp_ip">UDP/IP</option>
                                                <option value="ipc">IPC</option>
                                                <option value="tcp">TCP</option>
                                            </select>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="table_label buffer_row">UDP Port</td>
                                        <td className="plain buffer_row">
                                            <input 
                                                type="number"
                                                onChange={this._onPortInput}
                                                value={this.state.udpPort}></input>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="table_label">
                                            <div>
                                                <div style={radioStyle}>
                                                    <input 
                                                        type="radio" 
                                                        name="scan_method" 
                                                        onChange={this._onDeviceRangeSelect}
                                                        checked={this.state.deviceRangeSelected}/>
                                                </div>
                                                <span style={deviceRangeStyle}>Device ID Range</span>
                                            </div>
                                        </td>
                                        <td className="plain">
                                            <input 
                                                disabled={!this.state.deviceRangeSelected}
                                                style={deviceRangeStyle}
                                                type="number"
                                                onChange={this._onDeviceStart}
                                                value={this.state.deviceStart}></input>&nbsp;
                                            <input 
                                                disabled={!this.state.deviceRangeSelected}
                                                style={deviceRangeStyle}
                                                type="number"
                                                onChange={this._onDeviceEnd}
                                                value={this.state.deviceEnd}></input>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="table_label">
                                            <div>
                                                <div style={radioStyle}>
                                                    <input 
                                                        type="radio" 
                                                        name="scan_method" 
                                                        onChange={this._onAddressSelect}
                                                        checked={!this.state.deviceRangeSelected}/>
                                                </div>
                                                <span style={addressStyle}>Address</span>
                                            </div>
                                        </td>
                                        <td className="plain">
                                            <input 
                                                disabled={this.state.deviceRangeSelected}
                                                style={addressStyle}
                                                type="text"
                                                onChange={this._onAddress}
                                                value={this.state.address}></input>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <div
                            style={buttonStyle}>
                            <button onClick={this._doScan}>Scan</button>
                        </div>
                        
                    </div>
                )


                break;
        }

        return (
            <div>
                {devices}  
            </div>
        );
    },
});

function getStateFromStores() {
    return {
        platform: { name: "PNNL", uuid: "99090"}
    };
}

module.exports = DetectDevices;