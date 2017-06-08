'use strict';

require('react-select-me/lib/ReactSelectMe.css');
require('font-awesome/css/font-awesome.css');
require('normalize.css/normalize.css');

var React = require('react');
var ReactDOM = require('react-dom');

import { Router, Route, IndexRedirect, hashHistory } from 'react-router';

var authorizationStore = require('./stores/authorization-store');
var platformsPanelItemsStore = require('./stores/platforms-panel-items-store');
var devicesStore = require('./stores/devices-store');
var Dashboard = require('./components/dashboard');
var LoginForm = require('./components/login-form');
var PageNotFound = require('./components/page-not-found');
var Platform = require('./components/platform');
import PlatformManager from './components/platform-manager';
var Platforms = require('./components/platforms');
import ConfigureDevices from './components/configure-devices';
import ReconfigureDevice from './components/reconfigure-device';
var PlatformCharts = require('./components/platform-charts');
var Navigation = require('./components/navigation');
var devicesActionCreators = require('./action-creators/devices-action-creators');
var StatusIndicator = require('./components/status-indicator');
var statusIndicatorStore = require('./stores/status-indicator-store');

var _afterLoginPath = '/dashboard';


const checkAuth = AuthComponent => class extends React.Component {
    componentWillMount() {

        if ((AuthComponent.displayName !== 'LoginForm') && (AuthComponent.displayName !== 'PageNotFound')) {
            if (!authorizationStore.getAuthorization()) {
                hashHistory.replace('/login');
            }
        } 
        else if (authorizationStore.getAuthorization()) {
            hashHistory.replace(_afterLoginPath);
        }
    }

    render() {
        return <AuthComponent {...this.props}/>;
    }
};

var PublicExterior = React.createClass({
    getInitialState: function () {
        var state = {
            status: statusIndicatorStore.getStatus(),
            statusMessage: statusIndicatorStore.getStatusMessage(),
        };

        return state;
    },
    componentDidMount: function () {
        statusIndicatorStore.addChangeListener(this._onStoreChange);
    },
    componentWillUnmount: function () {
        statusIndicatorStore.removeChangeListener(this._onStoreChange);
    },
    _onStoreChange: function () {
        this.setState({status: statusIndicatorStore.getStatus()});
        this.setState({statusMessage: statusIndicatorStore.getStatusMessage()});
    },
    render: function() {

        var statusIndicator;

        if (this.state.status) {
            statusIndicator = (
                <StatusIndicator status={this.state.statusMessage}></StatusIndicator>
            );
        }

        return (
            <div className="public-exterior not-logged-in">
                <div className="main">
                    {statusIndicator}
                    <Navigation />
                    {this.props.children}
                </div>
            </div>
        );
    }
});

var routes = (
    <Router history={hashHistory}>
        <Route path="/" component={checkAuth(PlatformManager)} > 
            <IndexRedirect to="dashboard" />
            <Route path="dashboard" component={checkAuth(Dashboard)} />
            <Route path="platforms" component={checkAuth(Platforms)} />
            <Route path="platform/:uuid" component={checkAuth(Platform)} />
            <Route path="configure-devices" component={checkAuth(ConfigureDevices)} />
            <Route path="reconfigure-device" component={checkAuth(ReconfigureDevice)} />
            <Route path="charts" component={checkAuth(PlatformCharts)} />
        </Route>
        <Route path="/" component={checkAuth(PublicExterior)} > 
            <Route path="login" component={checkAuth(LoginForm)} />
        </Route>
        <Route path="*" component={PageNotFound}/>
        
    </Router>
);

ReactDOM.render(routes, document.getElementById('app'), function (Handler) {
    authorizationStore.addChangeListener(function () {
        if (authorizationStore.getAuthorization() && this.router.isActive('/login')) 
        {
            this.router.replace(_afterLoginPath);
        } 
        else if (!authorizationStore.getAuthorization() && !this.router.isActive('/login')) 
        {
            this.router.replace('/login');
        }
    }.bind(this));

    platformsPanelItemsStore.addChangeListener(function () {
        if (platformsPanelItemsStore.getLastCheck() && authorizationStore.getAuthorization())
        {
            if (!this.router.isActive('charts'))
            {
                this.router.push('/charts');
            }
        }

    }.bind(this));

    devicesStore.addChangeListener(function () { 

        if (devicesStore.getClearConfig())
        {
            if (!this.router.isActive('dashboard'))
            {
                this.router.push('/dashboard');
            }
        }
        else if (devicesStore.getNewScan())       
        {
            if (!this.router.isActive('configure-devices'))
            {
                this.router.push('/configure-devices');
            }
        }
        else if (devicesStore.reconfiguringDevice())       
        {
            if (!this.router.isActive('reconfigure-device'))
            {
                this.router.push('/reconfigure-device');
            }
        }

    }.bind(this));

});



