'use strict';

import React from 'react';


class BaseComponent extends React.Component {
	_bind(...methods) {
		methods.forEach((method) => this[method] = this[method].bind(this));
	}	
}

export default BaseComponent;