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

        var confirmButton = (
            (this.props.confirmText ? <button className="button">{this.props.confirmText}</button> : "")
        );

        var cancelText = (
            (this.props.cancelText ? this.props.cancelText : "Cancel")
        );

        var formWidth;

        if (this.props.width)
        {
            formWidth = {
                width: this.props.width
            }
        }

        return (
            <form className="confirmation-form" 
                onSubmit={this._onSubmit}
                style={formWidth}>
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
                        {cancelText}
                    </button>
                    {confirmButton}
                </div>
            </form>
        );
    },
});

module.exports = ConfirmForm;
