'use strict';

import React from 'react';
import io from 'socket';
import BaseComponent from './base-component';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
let socket = io('http://localhost:8000');

class DevicesFound extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange');

        this.state = {};
        this.state.devices = devicesStore.getDevices(props.platform);

        if (socket)
        {
            socket.on('server:event', data => {
                console.log("data: " + data);
            });
        }
    }
    componentDidMount() {
        // platformsStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount() {
        // platformsStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {
        this.setState({devices: devicesStore.getDevices(this.props.platform)});
    }
    _configureDevice(device) {
        devicesActionCreators.configureDevice(device);
    }
    render() {        
        
        var devices = 
            this.state.devices.map(function (device) {

                var buttonStyle = {
                    height: "24px",
                    lineHeight: "18px"
                }

                var tds = device.map(function (d) {
                                return (<td className="plain">{ d.value }</td>)
                            });
                return (
                    <tr>
                        { tds }

                        <td className="plain">
                            <button 
                                onClick={this._configureDevice.bind(this, device)}
                                style={buttonStyle}>Configure</button>
                        </td>
                    </tr>
                );

            }, this); 

        var ths = this.state.devices[0].map(function (d) {
                        return (<th className="plain">{d.label}</th>); 
                    });    

        return (
            <div className="devicesFoundContainer">
                <div className="devicesFoundBox">
                    <table>
                        <tbody>
                            <tr>
                                { ths }
                                <th className="plain"></th>
                            </tr>
                            {devices}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }
};

function getStateFromStores(platform) {
    return {
        devices: devicesStore.getDevices(platform)
    };
}

export default DevicesFound;