'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var RegisterPlatformForm = React.createClass({
    getInitialState: function () {
        var state = {};
        
        state.method = 'discovery';

        state.name = state.discovery_address = state.ipaddress = state.serverKey = state.publicKey = state.secretKey = '';
        state.protocol = 'tcp';

        return state;
    },
    _onNameChange: function (e) {
        this.setState({ name: e.target.value });
    },
    _onAddressChange: function (e) {
        this.setState({ ipaddress: e.target.value });
        this.setState({ discovery_address: e.target.value });
    },
    _onProtocolChange: function (e) {
        this.setState({ protocol: e.target.value });
    },
    _onServerKeyChange: function (e) {
        this.setState({ serverKey: e.target.value });
    },
    _onPublicKeyChange: function (e) {
        this.setState({ publicKey: e.target.value });
    },
    _onSecretKeyChange: function (e) {
        this.setState({ secretKey: e.target.value });
    },
    _toggleMethod: function (e) {
        this.setState({ method: (this.state.method === "discovery" ? "advanced" : "discovery") });
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function (e) {
        e.preventDefault();
        var address = (this.state.method === "discovery" ? this.state.discovery_address : this._formatAddress());
        platformManagerActionCreators.registerPlatform(this.state.name, address, this.state.method);
    },
    _formatAddress: function () {

        var fullAddress = this.state.protocol + "://" + this.state.ipaddress;

        if (this.state.serverKey)
        {
            fullAddress = fullAddress + "?serverkey=" + this.state.serverKey;
        }

        if (this.state.publicKey)
        {
            fullAddress = fullAddress + "&publickey=" + this.state.publicKey;
        }

        if (this.state.secretKey)
        {
            fullAddress = fullAddress + "&secretkey=" + this.state.secretKey;
        }

        return fullAddress;
    },
    render: function () {
        
        var fullAddress = this._formatAddress();

        var registerForm;

        var submitMethod;

        switch (this.state.method)
        {
            case "discovery":
                registerForm = (
                    <div>
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv firstCell">
                                    <label className="formLabel">Name</label>
                                    <input
                                        className="form__control form__control--block inputField"
                                        type="text"
                                        onChange={this._onNameChange}
                                        value={this.state.name}
                                        autoFocus
                                        required
                                    />
                                </div> 
                                <div className="cellDiv"
                                    width="70%">
                                    <label className="formLabel">Address</label>
                                    <input
                                        className="form__control form__control--block inputField"
                                        type="text"
                                        onChange={this._onAddressChange}
                                        value={this.state.discovery_address}
                                        required
                                    />
                                </div>                     
                            </div>  
                        </div> 
                        
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv firstCell">
                                    <div className="form__link"
                                        onClick={this._toggleMethod}>
                                        <a>Advanced</a>
                                    </div>
                                </div> 
                                <div className="cellDiv"
                                    width="70%">
                                    <div className="form__actions">
                                        <button
                                            className="button button--secondary"
                                            type="button"
                                            onClick={this._onCancelClick}
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            className="button"
                                            disabled={!this.state.name || !this.state.discovery_address}
                                        >
                                            Register
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )
                break;
            case "advanced":

                registerForm = (
                    <div>
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv firstCell">
                                    <label className="formLabel">Name</label>
                                    <input
                                        className="form__control form__control--block"
                                        type="text"
                                        onChange={this._onNameChange}
                                        value={this.state.name}
                                        autoFocus
                                        required
                                    />
                                </div>   
                                <div className="cellDiv"
                                    width="10%">
                                    <label className="formLabel">Protocol</label><br/>
                                    <select
                                        className="form__control"
                                        onChange={this._onProtocolChange}
                                        value={this.state.protocol}
                                        required
                                    >   
                                        <option value="tcp">TCP</option>
                                        <option value="ipc">IPC</option>
                                    </select>
                                </div>
                                <div className="cellDiv"
                                    width="56%">
                                    <label className="formLabel">VIP address</label>
                                    <input
                                        className="form__control form__control--block"
                                        type="text"
                                        onChange={this._onAddressChange}
                                        value={this.state.ipaddress}
                                        required
                                    />
                                </div>                     
                            </div>  
                        </div> 
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv"
                                    width="80%">                        
                                    <label className="formLabel">Server Key</label>
                                    <input
                                        className="form__control form__control--block"
                                        type="text"
                                        onChange={this._onServerKeyChange}
                                        value={this.state.serverKey}
                                    />
                                </div>
                            </div>
                        </div>
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv"
                                    width="80%">
                                    <label className="formLabel">Public Key</label>
                                    <input
                                        className="form__control form__control--block"
                                        type="text"
                                        onChange={this._onPublicKeyChange}
                                        value={this.state.publicKey}
                                    />
                                </div>
                            </div>
                        </div>
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv"
                                    width="80%">
                                    <label className="formLabel">Secret Key</label>
                                    <input
                                        className="form__control form__control--block"
                                        type="text"
                                        onChange={this._onSecretKeyChange}
                                        value={this.state.secretKey}
                                    />
                                </div>
                            </div>
                        </div>
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv"
                                    width="100%"> 
                                    <label className="formLabel">Preview</label>                   
                                    <div
                                        className="preview">
                                        {fullAddress}
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div className="tableDiv">
                            <div className="rowDiv">
                                <div className="cellDiv firstCell">
                                    <div className="form__link"
                                        onClick={this._toggleMethod}>
                                        <a>Discover</a>
                                    </div>
                                </div> 
                                <div className="cellDiv"
                                    width="70%">
                                    <div className="form__actions">
                                        <button
                                            className="button button--secondary"
                                            type="button"
                                            onClick={this._onCancelClick}
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            className="button"
                                            disabled={!this.state.name || !this.state.protocol || !this.state.ipaddress 
                                                || !((this.state.serverKey && this.state.publicKey && this.state.secretKey) 
                                                        || (!this.state.publicKey && !this.state.secretKey))}
                                        >
                                            Register
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )
                break;
        }

        return (
            <form className="register-platform-form" onSubmit={this._onSubmit}>
                <h1>Register platform</h1>
                {registerForm}

            </form>
        );
    },
});

module.exports = RegisterPlatformForm;
