'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
// var ReactRouter = require('react-router');

import { Router, Route, hashHistory, IndexRoute, browserHistory, useRouterHistory, Redirect } from 'react-router';
// var hashHistory = ReactRouter.hashHistory;
// var IndexRoute = ReactRouter.IndexRoute;

// var useRouterHistory = ReactRouter.useRouterHistory;
// var createHashHistory = require('history').createHashHistory;

import {createHashHistory, createHistory} from 'history';

// var Redirect = ReactRouter.Redirect;


var authorizationStore = require('./stores/authorization-store');
var platformsPanelItemsStore = require('./stores/platforms-panel-items-store');
var devicesStore = require('./stores/devices-store');
var Dashboard = require('./components/dashboard');
var LoginForm = require('./components/login-form');
var PageNotFound = require('./components/page-not-found');
var Platform = require('./components/platform');
import PlatformManager from './components/platform-manager';
var Platforms = require('./components/platforms');
var Devices = require('./components/devices');
var ConfigureDevices = require('./components/configure-devices');
var PlatformCharts = require('./components/platform-charts');

var _afterLoginPath = '/dashboard';

var MainLayout = React.createClass({
    render: function() {

        var monkey;

        return (
            <div>
                {this.props.children}
            </div>
        );
    }
});


function checkAuth(Component) {
    return React.createClass({
        statics: {
            willTransitionTo: function (transition) {
                if (transition.path !== '/login') {
                    if (!authorizationStore.getAuthorization()) {
                        transition.redirect('/login');
                    }
                } else if (transition.path === '/login' && authorizationStore.getAuthorization()) {
                    transition.redirect(_afterLoginPath);
                }
            },
        },
        render: function () {
            return (
                <Component {...this.props} />
            );
        },
    });
}

var AfterLogin = React.createClass({
    statics: {
        willTransitionTo: function (transition) {
            transition.redirect(_afterLoginPath);
        },
    },
    render: function () {},
});


// const appHistory = useRouterHistory(createHashHistory)({ queryKey: false});

// let history = createHistory();


var routes = (
    <Router history={browserHistory}>
        <Route path="/" component={checkAuth(PlatformManager)}> 
            <Route path="login" component={checkAuth(LoginForm)} />
            <Route path="dashboard" component={checkAuth(Dashboard)} />
            <Route path="platforms" component={checkAuth(Platforms)} />
            <Route path="platform/:uuid" component={checkAuth(Platform)} />
            <Route path="devices" component={checkAuth(Devices)} />
            <Route path="configure-devices" component={checkAuth(ConfigureDevices)} />
            <Route path="charts" component={checkAuth(PlatformCharts)} />
            <Route path="*" component={PageNotFound}/>
        </Route>
        
    </Router>
);

// var routes = (
//     <Router history={history}>
//         <Route name="home" path="/" component={MainLayout}> 
//             <IndexRoute component={checkAuth(PlatformManager)} />
//             <Route path="login" component={checkAuth(LoginForm)} />
//             <Route path="dashboard" component={checkAuth(Dashboard)} />
//             <Route path="platforms" component={checkAuth(Platforms)} />
//             <Route path="platforms/:uuid" component={checkAuth(Platform)} />
//             <Route path="devices" component={checkAuth(Devices)} />
//             <Route path="configure-devices" component={checkAuth(ConfigureDevices)} />
//             <Route path="platform-charts" component={checkAuth(PlatformCharts)} />
//             <Route path="*" component={PageNotFound}/>
//         </Route>
        
//     </Router>
// );

// ReactDOM.render(routes, document.getElementById('app'));


// ReactDOM.render(routes, document.getElementById('app'));

ReactDOM.render(routes, document.getElementById('app'), function (Handler) {
    authorizationStore.addChangeListener(function () {
        if (authorizationStore.getAuthorization() && this.history.isActive('/login')) 
        {
            this.history.replaceState(null, _afterLoginPath);
        } 
        else if (!authorizationStore.getAuthorization() && !this.history.isActive('/login')) 
        {
            this.history.replaceState(null, '/login');
        }
    }.bind(this));

    platformsPanelItemsStore.addChangeListener(function () {
        if (platformsPanelItemsStore.getLastCheck() && authorizationStore.getAuthorization())
        {
            if (!this.history.isActive('charts'))
            {
                this.history.pushState(null, '/charts');
            }
        }

    }.bind(this));

    devicesStore.addChangeListener(function () {        
        if (!this.history.isActive('configure'))
        {
            this.history.pushState(null, '/configure-devices');
        }
    }.bind(this));
});



