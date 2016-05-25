'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');

var RegisterPlatformForm = React.createClass({
    getInitialState: function () {
        return {};
    },
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function (e) {
        e.preventDefault();
        platformManagerActionCreators.deregisterPlatform(this.props.platform);
    },
    render: function () {
        return (
            <form className="register-platform-form" onSubmit={this._onSubmit}>
                <h1>Deregister platform</h1>
                <p>
                    Deregister <strong>{this.props.platform.name}</strong>?
                </p>
                <div className="form__actions">
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={this._onCancelClick}
                        autoFocus
                    >
                        Cancel
                    </button>
                    <button className="button">Deregister</button>
                </div>
            </form>
        );
    },
});

module.exports = RegisterPlatformForm;
