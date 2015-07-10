'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var ConfirmForm = React.createClass({
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function () {
        this.props.onConfirm();
    },
    render: function () {
        return (
            <form className="confirmation-form" onSubmit={this._onSubmit}>
                <h1>{this.props.promptTitle}</h1>
                <p>
                    {this.props.promptText}
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
                    <button className="button">{this.props.confirmText}</button>
                </div>
            </form>
        );
    },
});

module.exports = ConfirmForm;
