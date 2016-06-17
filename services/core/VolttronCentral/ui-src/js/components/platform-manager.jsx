'use strict';

var $ = require('jquery');
var React = require('react');
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
var PlatformsPanel = require('./platforms-panel');
var platformsPanelStore = require('../stores/platforms-panel-store');
var StatusIndicator = require('./status-indicator');
var statusIndicatorStore = require('../stores/status-indicator-store');

var PlatformManager = React.createClass({
    mixins: [Router.Navigation, Router.State],
    getInitialState: function () {
        var state = getStateFromStores();

        this.uninitialized = true;

        return state;
    },
    componentWillMount: function () {
        platformManagerActionCreators.initialize();
    },
    componentDidMount: function () {
        authorizationStore.addChangeListener(this._onStoreChange);
        consoleStore.addChangeListener(this._onStoreChange);
        modalStore.addChangeListener(this._onStoreChange);
        platformsPanelStore.addChangeListener(this._onStoreChange);
        statusIndicatorStore.addChangeListener(this._onStoreChange);
        this._doModalBindings();
    },
    componentDidUpdate: function () {
        this._doModalBindings();

        if (this.state.expanded)
        {               
            this.uninitialized = false;

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
            }

            handle.addEventListener("mousedown", onMouseDown);
        }
    },
    _doModalBindings: function () {
        if (this.state.modalContent) {
            window.addEventListener('keydown', this._closeModal);
            this._focusDisabled = $('input,select,textarea,button,a', React.findDOMNode(this.refs.main)).attr('tabIndex', -1);
        } else {
            window.removeEventListener('keydown', this._closeModal);
            if (this._focusDisabled) {
                this._focusDisabled.removeAttr('tabIndex');
                delete this._focusDisabled;
            }
        }
    },
    componentWillUnmount: function () {
        authorizationStore.removeChangeListener(this._onStoreChange);
        consoleStore.removeChangeListener(this._onStoreChange);
        modalStore.removeChangeListener(this._onStoreChange);
        statusIndicatorStore.removeChangeListener(this._onStoreChange);
        this._modalCleanup();
    },
    _onStoreChange: function () {
        this.setState(getStateFromStores());
    },
    _onToggleClick: function () {
        consoleActionCreators.toggleConsole();
    },
    _closeModal: function (e) {
        if (e.keyCode === 27) {
            modalActionCreators.closeModal();
        }
    },
    render: function () {
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
            classes.push('platform-manager--console-open');
        }

        classes.push(this.state.loggedIn ?
            'platform-manager--logged-in' : 'platform-manager--not-logged-in');

        if (this.state.modalContent) {
            classes.push('platform-manager--modal-open');
            modal = (
                <Modal>{this.state.modalContent}</Modal>
            );
        }

        if (this.state.status) {
            statusIndicator = (
                <StatusIndicator></StatusIndicator>
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
                <div ref="main" className="main">
                    <Navigation />                
                    <PlatformsPanel/>
                    <div className={exteriorClasses.join(' ')}>
                        {resizeHandle}
                        <Router.RouteHandler />
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
    },
});

function getStateFromStores() {
    return {
        consoleShown: consoleStore.getConsoleShown(),
        loggedIn: !!authorizationStore.getAuthorization(),
        modalContent: modalStore.getModalContent(),
        expanded: platformsPanelStore.getExpanded(),
        status: statusIndicatorStore.getStatus()
    };
}

module.exports = PlatformManager;
