'use strict';

var React = require('react');
var Router = require('react-router');

var devicesActionCreators = require('../action-creators/devices-action-creators');
var devicesStore = require('../stores/devices-store');

var DevicesFound = React.createClass({
    getInitialState: function () {
        return getStateFromStores(this.props.platform);
    },
    componentDidMount: function () {
        // platformsStore.addChangeListener(this._onStoresChange);
    },
    componentWillUnmount: function () {
        // platformsStore.removeChangeListener(this._onStoresChange);
    },
    _onStoresChange: function () {
        this.setState(getStateFromStores(this.props.platform));
    },
    _configureDevice: function (device) {
        devicesActionCreators.configureDevice(device);
    },
    render: function () {        
        
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
    },
});

function getStateFromStores(platform) {
    return {
        devices: devicesStore.getDevices(platform)
    };
}

module.exports = DevicesFound;