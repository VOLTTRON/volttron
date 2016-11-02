'use strict';

var React = require('react');

import ControlButton from './control-button';

var DragButton = React.createClass({
    render: function () {

        var taptipX = 60;
        var taptipY = 120;

        var tooltipX = 20;
        var tooltipY = 60;

        var dragIcon = <i className="fa fa-bars"></i>;

        var dragTooltip = {
            "content": this.props.tooltipMsg,
            "xOffset": tooltipX,
            "yOffset": tooltipY
        };

        return (
            <ControlButton 
                name="dragButton"
                icon={dragIcon}
                tooltip={dragTooltip}
                clickAction={this.props.ondrag}></ControlButton>
        );
    },
});

module.exports = DragButton;
