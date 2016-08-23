'use strict';

import React from 'react';
import io from 'socket';
import BaseComponent from './base-component';

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');
let socket = io('https://localhost:3000');

class DevicesFound extends BaseComponent {
    constructor(props) {
        super(props);
        this._bind('_onStoresChange');

        this.state = {};
        this.state.devices = devicesStore.getDevices(props.platform, props.bacnet);

        if (socket)
        {
            socket.on('server:event', data => {
                console.log("data: " + data);
            });
        }
    }
    componentDidMount() {
        devicesStore.addChangeListener(this._onStoresChange);
    }
    componentWillUnmount() {
        devicesStore.removeChangeListener(this._onStoresChange);
    }
    _onStoresChange() {
        var devices = devicesStore.getDevices(this.props.platform, this.props.bacnet);
        this.props.devicesloaded(devices.length > 0);
        this.setState({devices: devices});
    }
    _configureDevice(device) {

        device.configuring = !device.configuring;
        devicesActionCreators.configureDevice(device);
    }
    render() {        
        
        var devicesContainer;
        if (this.state.devices.length)
        {
            var devices = 
                this.state.devices.map(function (device) {

                    var deviceId = device.id;

                    var tds = device.items.map(function (d, i) {
                            return (<td key={d.key + "-" + i} className="plain">{ d.value }</td>)
                        });

                    return (
                        <tr key={deviceId}>
                            { tds }

                            <td className="plain">
                                <div className={ device.configuring ? "configure-arrow rotateConfigure" : "configure-arrow" }
                                    onClick={this._configureDevice.bind(this, device)}>
                                        &#9668;
                                </div>
                            </td>
                        </tr>
                    );

                }, this); 

            var ths = this.state.devices[0].items.map(function (d, i) {
                            return (<th key={d.key + "-" + i + "-th"} className="plain">{d.label}</th>); 
                        }); 

            devicesContainer = (
                <table>
                    <tbody>
                        <tr>
                            { ths }
                            <th className="plain"></th>
                        </tr>
                        {devices}
                    </tbody>
                </table>
            );   
        }
        else
        {
            devicesContainer = <div className="no-devices">No devices have been detected ...</div>;
        }

        return (
            <div className="devicesFoundContainer">
                <div className="devicesFoundBox">
                    {devicesContainer}
                </div>
            </div>
        );
    }
};

export default DevicesFound;