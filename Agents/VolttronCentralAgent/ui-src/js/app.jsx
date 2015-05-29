'use strict';

var React = require('react');
var Router = require('react-router');

var PageNotFound = require('./components/page-not-found');
var LoginForm = require('./components/login-form');
var Logout = require('./components/logout');
var PlatformManager = require('./components/platform-manager');
var platformManagerStore = require('./stores/platform-manager-store');
var Platforms = require('./components/platforms');

var _afterLoginRoute = 'platforms';

function checkAuth(Component) {
	return React.createClass({
		statics: {
			willTransitionTo: function (transition) {
				if (transition.path !== '/login') {
					_afterLoginRoute = transition.path;

					if (!platformManagerStore.getAuthorization()) {
				    	transition.redirect('login');
				    }
				} else if (transition.path === '/login' && platformManagerStore.getAuthorization()) {
				    transition.redirect(_afterLoginRoute);
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
			transition.redirect(_afterLoginRoute);
		},
	},
	render: function () {},
});

var routes = (
	<Router.Route path="/" handler={PlatformManager}>
		<Router.Route name="login" path="login" handler={checkAuth(LoginForm)} />
		<Router.Route name="logout" path="logout" handler={Logout} />
		<Router.Route name="platforms" path="platforms" handler={checkAuth(Platforms)} />
		<Router.NotFoundRoute handler={checkAuth(PageNotFound)} />
		<Router.DefaultRoute handler={AfterLogin} />
	</Router.Route>
);

var router = Router.create(routes);

router.run(function (Handler) {
	React.render(
	    <Handler />,
	    document.getElementById('app')
	);
});

platformManagerStore.addChangeListener(function () {
	if (!router.isActive('login') && !platformManagerStore.getAuthorization()) {
		router.transitionTo('login');
	}
});
