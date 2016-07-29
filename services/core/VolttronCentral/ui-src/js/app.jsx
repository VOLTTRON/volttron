'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
// var ReactRouter = require('react-router');

import { Router, Route, hashHistory, IndexRoute, browserHistory, useRouterHistory, Redirect, withRouter } from 'react-router';
// var hashHistory = ReactRouter.hashHistory;
// var IndexRoute = ReactRouter.IndexRoute;

// var useRouterHistory = ReactRouter.useRouterHistory;
// var createHashHistory = require('history').createHashHistory;

// import {createHashHistory, createHistory} from 'history';

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

// var MainLayout = React.createClass({
//     render: function() {

//         var monkey;

//         return (
//             <div>
//                 {this.props.children}
//             </div>
//         );
//     }
// });

// const newCheckAuth = (nextState, replace, callback) => { 

//     if (!authorizationStore.getAuthorization()) {
//         replace('/login');
//     }
//     else
//     {
//         replace(_afterLoginPath);
//     }
// } 

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


        // if (!authorizationStore.getAuthorization()) {
        //     hashHistory.replace('/login');
        // }
    }

    render() {
        return <AuthComponent {...this.props}/>;
    }
};

// var AfterLogin = React.createClass({
//     statics: {
//         willTransitionTo: function (transition) {
//             transition.redirect(_afterLoginPath);
//         },
//     },
//     render: function () {},
// });

// const AfterLogin = withRouter(React.createClass({
//     componentWillMount() {
//         hashHistory.replace(_afterLoginPath);
//     },

//     routerWillLeave(nextLocation)
//     {
//         var i = 0;
//     },

//     render() {
//         return <div>No Hablo Espanol</div>
//     }
// }));

// const checkNewAuth = (AuthComponent) => React.createClass({

//     render() {

//         var elem;

//         if (!authorizationStore.getAuthorization())
//         {
//             elem = <LoginForm/>;
//         }
//         else
//         {
//             elem = <AuthComponent {...this.props}/>;
//         }

//         // return (!authorizationStore.getAuthorization() ? <LoginForm/> : <AuthComponent/>);
//         return elem;
//     }
// });

// checkNewAuth.contextTypes = {
//     router: React.PropTypes.func.isRequired
// }

// function checkAuth(Component) {
//     return React.createClass({

//         // componentDidMount() {
//         //     this.props.router.setRouteLeaveHook(this.props.route, this.routerWillLeave)
//         // },
//         // routerWillLeave(nextLocation) {
//         //     // return false to prevent a transition w/o prompting the user,
//         //     // or return a string to allow the user to decide:
//         //     if (!this.state.isSaved)
//         //         return 'Your work is not saved! Are you sure you want to leave?'

//         // },


//         // if (transition.path !== '/login') {
//         //     if (!authorizationStore.getAuthorization()) {
//         //         transition.redirect('/login');
//         //     }
//         // } else if (transition.path === '/login' && authorizationStore.getAuthorization()) {
//         //     transition.redirect(_afterLoginPath);
//         // }

//         statics: {
//             willTransitionTo: function (transition) {
//                 if (transition.path !== '/login') {
//                     if (!authorizationStore.getAuthorization()) {
//                         transition.redirect('/login');
//                     }
//                 } else if (transition.path === '/login' && authorizationStore.getAuthorization()) {
//                     transition.redirect(_afterLoginPath);
//                 }
//             },
//         },
//         render: function () {
//             return (
//                 <Component {...this.props} />
//             );
//         },
//     });
// }

// var AfterLogin = React.createClass({
//     statics: {
//         willTransitionTo: function (transition) {
//             transition.redirect(_afterLoginPath);
//         },
//     },
//     render: function () {},
// });

// const DefaultRoute = withRouter(React.createClass({
//     componentDidMount() {
//         this.props.router.setRouteLeaveHook(this.props.route, this.routerWillLeave);
//     },

//     routerWillLeave(nextLocation)
//     {
//         var i = 0;
//     },

//     render() {
//         return <div>No Hablo Espanol</div>
//     }
// }));


// const appHistory = useRouterHistory(createHashHistory)({ queryKey: false});

// let history = createHistory();


var routes = (
    <Router history={hashHistory}>
        <Route path="/" component={checkAuth(PlatformManager)} > 
            <Route path="login" component={checkAuth(LoginForm)} />
            <Route path="dashboard" component={checkAuth(Dashboard)} />
            <Route path="platforms" component={checkAuth(Platforms)} />
            <Route path="platform/:uuid" component={checkAuth(Platform)} />
            <Route path="devices" component={checkAuth(Devices)} />
            <Route path="configure-devices" component={checkAuth(ConfigureDevices)} />
            <Route path="charts" component={checkAuth(PlatformCharts)} />
            <Route path="*" component={checkAuth(PageNotFound)}/>
        </Route>

        <Route path="*" component={checkAuth(PageNotFound)}/>
        
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
        if (!this.router.isActive('configure'))
        {
            this.router.push('/configure-devices');
        }
    }.bind(this));

    // if (!authorizationStore.getAuthorization())
    // {
    //     this.router.replace('/login');
    // }
    // else
    // {
    //     this.router.replace('/dashboard');
    // }
});



