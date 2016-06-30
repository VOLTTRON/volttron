/*
 * Copyright (c) 2005-2015 Real-Time Innovations, Inc. All rights reserved.
 * Permission to modify and use for internal purposes granted.
 * This software is provided "as is", without warranty, express or implied.
 */

/* DDS Connector
 */
var rti   = require('rticonnextdds-connector');

var connector = new rti.Connector("MyParticipantLibrary::Zero",__dirname + "/../ShapeExample.xml");
var input = connector.getInput("MySubscriber::MySquareReader");

connector.on('on_data_available', function() {
	input.take();

	console.log("length = " + input.samples.getLength());
	for (i=1; i <= input.samples.getLength(); i++) {
	  if (input.infos.isValid(i)) {
	    console.log(JSON.stringify(input.samples.getJSON(i)));
	  }
	}
})

/*****************************************************************************/
/** HTTP Web
 */

var http = require('http');

http.createServer(function (req, res) {

	res.writeHead(200, {'Content-Type': 'text/plain'});
    for (i=1; i <= input.samples.getLength(); i++) {
        if (input.infos.isValid(i)) {
          res.write(JSON.stringify(input.samples.getJSON(i)));
        }
    }
    res.end();

}).listen(7400, '127.0.0.1');

console.log('Server running at http://127.0.0.1:7400/');

/*****************************************************************************/
