'use strict';

var React = require('react');

var modalActionCreators = require('../action-creators/modal-action-creators');

var ConfirmForm = React.createClass({
    _onCancelClick: modalActionCreators.closeModal,
    _onSubmit: function (e) {
        e.preventDefault();
        this.props.onConfirm();
    },
    render: function () {

        var promptText = this.props.promptText;

        if (this.props.hasOwnProperty("preText") && this.props.hasOwnProperty("postText"))
        {
            promptText = <b>{promptText}</b>
        }

        return (
            <form className="confirmation-form" onSubmit={this._onSubmit}>
                <h1>{this.props.promptTitle}</h1>
                <p>
                    {this.props.preText}{promptText}{this.props.postText}
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
