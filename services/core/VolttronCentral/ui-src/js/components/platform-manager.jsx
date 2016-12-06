'use strict';

var $ = require('jquery');
import React from 'react';
var ReactDOM = require('react-dom');
var Router = require('react-router');

var authorizationStore = require('../stores/authorization-store');
var Console = require('./console');
var consoleActionCreators = require('../action-creators/console-action-creators');
var consoleStore = require('../stores/console-store');
var Modal = require('./modal');
var modalActionCreators = require('../action-creators/modal-action-creators');
var modalStore = require('../stores/modal-store');
var Navigation = require('./navigation');
var platformManagerActionCreators = require('../action-creators/platform-manager-action-creators');
var platformsPanelStore = require('../stores/platforms-panel-store');
var StatusIndicator = require('./status-indicator');
var statusIndicatorStore = require('../stores/status-indicator-store');
var platformsStore = require('../stores/platforms-store');

import PlatformsPanel from './platforms-panel';
import ColumnMover from './column-mover';

class PlatformManager extends React.Component {
    constructor(props) {
        super(props);
        this._doModalBindings = this._doModalBindings.bind(this);
        this._onStoreChange = this._onStoreChange.bind(this);

        this.state = getStateFromStores();
    }
    componentWillMount() {
        if (!this.state.initialized)
        {
            platformManagerActionCreators.initialize();
        }
    }
    componentDidMount() {
        authorizationStore.addChangeListener(this._onStoreChange);
        consoleStore.addChangeListener(this._onStoreChange);
        modalStore.addChangeListener(this._onStoreChange);
        platformsPanelStore.addChangeListener(this._onStoreChange);
        platformsStore.addChangeListener(this._onStoreChange);
        statusIndicatorStore.addChangeListener(this._onStoreChange);
        this._doModalBindings();
    }
    componentDidUpdate() {
        this._doModalBindings();

        if (this.state.expanded)
        {    
            var handle = document.querySelector(".resize-handle");

            var onMouseDown = function (evt)
            {
                var exteriorPanel = this.parentNode;
                var children = exteriorPanel.parentNode.childNodes;
                var platformsPanel;

                for (var i = 0; i < children.length; i++)
                {
                    if (children[i].classList.contains("platform-statuses"))
                    {
                        platformsPanel = children[i];
                        break;
                    }
                }

                var target = (evt.target.setCapture ? evt.target : document);

                if (target.setCapture)
                {
                    target.setCapture();
                }

                var onMouseMove = function (evt)
                {               
                    var newWidth = Math.min(window.innerWidth, evt.clientX);
                    
                    platformsPanel.style.width = newWidth + "px";
                    exteriorPanel.style.width = (window.innerWidth - newWidth - 100) + "px";
                };                    

                var onMouseUp = function (evt)
                {
                    target.removeEventListener("mousemove", onMouseMove);
                    target.removeEventListener("mouseup", onMouseUp);
                };                  

                target.addEventListener("mousemove", onMouseMove);
                target.addEventListener("mouseup", onMouseUp);

                evt.preventDefault();
            };

            handle.addEventListener("mousedown", onMouseDown);
        }
    }
    _doModalBindings() {
        if (this.state.modalContent) {
            window.addEventListener('keydown', this._closeModal);
            this._focusDisabled = $('input,select,textarea,button,a', ReactDOM.findDOMNode(this.refs.main)).attr('tabIndex', -1);
        } else {
            window.removeEventListener('keydown', this._closeModal);
            if (this._focusDisabled) {
                this._focusDisabled.removeAttr('tabIndex');
                delete this._focusDisabled;
            }
        }
    }
    componentWillUnmount() {
        authorizationStore.removeChangeListener(this._onStoreChange);
        consoleStore.removeChangeListener(this._onStoreChange);
        modalStore.removeChangeListener(this._onStoreChange);
        platformsPanelStore.removeChangeListener(this._onStoreChange);
        platformsStore.removeChangeListener(this._onStoreChange);
        statusIndicatorStore.removeChangeListener(this._onStoreChange);
    }
    _onStoreChange() {
        this.setState(getStateFromStores());
    }
    _onToggleClick() {
        consoleActionCreators.toggleConsole();
    }
    _closeModal(e) {
        if (e.keyCode === 27) {
            modalActionCreators.closeModal();
        }
    }
    render() {
        var classes = ['platform-manager'];
        var modal;
        var exteriorClasses = ["panel-exterior"];

        if (this.state.expanded === true)
        {
            exteriorClasses.push("narrow-exterior");
            exteriorClasses.push("slow-narrow");
        }
        else if (this.state.expanded === false)
        {
            exteriorClasses.push("wide-exterior");
            exteriorClasses.push("slow-wide");
        }
        else if (this.state.expanded === null)
        {
            exteriorClasses.push("wide-exterior");
        }

        var statusIndicator;

        if (this.state.consoleShown) {
            classes.push('console-open');
        }

        classes.push(this.state.loggedIn ?
            'logged-in' : 'not-logged-in');

        if (this.state.modalContent) {
            classes.push('modal-open');
            modal = (
                <Modal>{this.state.modalContent}</Modal>
            );
        }

        if (this.state.status) {
            statusIndicator = (
                <StatusIndicator status={this.state.statusMessage}></StatusIndicator>
            );
        }

        var resizeHandle;

        if (this.state.expanded === true)
        {
            resizeHandle = (
                <div className="resize-handle"></div>
            );

            exteriorClasses.push("absolute_anchor");
        }

        return (
            <div className={classes.join(' ')}>
                {statusIndicator}
                {modal}
                <ColumnMover/>
                <div ref="main" className="main">
                    <Navigation />                
                    <PlatformsPanel/>
                    <div className={exteriorClasses.join(' ')}>
                        {resizeHandle}
                        {this.props.children}
                    </div>
                </div>
                <input
                    className="toggle"
                    type="button"
                    value={'Console ' + (this.state.consoleShown ? '\u25bc' : '\u25b2')}
                    onClick={this._onToggleClick}
                />
                {this.state.consoleShown && <Console className="console" />}
            </div>
        );
    }
}

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!authorizationStore.getAuthorization(),
        modalContent: modalStore.getModalContent(),
        expanded: platformsPanelStore.getExpanded(),
        status: statusIndicatorStore.getStatus(),
        statusMessage: statusIndicatorStore.getStatusMessage(),
        initialized: platformsStore.getInitialized()
    };
}

export default PlatformManager;
