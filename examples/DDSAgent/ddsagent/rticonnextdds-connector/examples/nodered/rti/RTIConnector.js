/*
 * Copyright (c) 2005-2015 Real-Time Innovations, Inc. All rights reserved.
 * Permission to modify and use for internal purposes granted.
 * This software is provided "as is", without warranty, express or implied.
 */

module.exports = function(RED) {
    "use strict";

    var rti = require("rticonnextdds-connector");


    // The main node definition - most things happen in here
    function RTIConnectorNode(n) {
        // Create a RED node
        RED.nodes.createNode(this,n);


        // Store local copies of the node configuration (as defined in the .html)
        this.profile_name = n.profile_name;
        this.xml = n.xml;
        this.input_name = n.input_name;

        // Do whatever you need to do in here - declare callbacks etc


        var node = this;

        var connector = new rti.Connector(this.profile_name,this.xml);
        var input = connector.getInput(this.input_name);

        connector.on('on_data_available',
          function() {
            input.take();
            var i=0;
            for (i=1; i <= input.samples.getLength(); i++) {
              if (input.infos.isValid(i)) {
//                console.log(input.samples.toJSON(i));
                var msg = {};
                msg.topic = node.topic;
                msg.payload = JSON.stringify(input.samples.getJSON(i));
                node.send(msg);
              }
            }
          });
        // Note: this sample doesn't do anything much - it will only send
        // this message once at startup...
        // Look at other real nodes for some better ideas of what to do....


        // send out the message to the rest of the workspace.

        this.on("close", function () {

            // Called when the node is shutdown - eg on redeploy.
            // Allows ports to be closed, connections dropped etc.
            // eg: this.client.disconnect();
        });
    }

    // Register the node by name. This must be called before overriding any of the
    // Node functions.
    RED.nodes.registerType("RTIConnector",RTIConnectorNode);

}

