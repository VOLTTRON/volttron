/*
 * Copyright (c) 2005-2015 Real-Time Innovations, Inc. All rights reserved.
 * Permission to modify and use for internal purposes granted.
 * This software is provided "as is", without warranty, express or implied.
 */

var sleep = require('sleep');
var rti   = require('rticonnextdds-connector');

var connector = new rti.Connector("MyParticipantLibrary::Zero",__dirname + "/../ShapeExample.xml");
var input = connector.getInput("MySubscriber::MySquareReader");

for (;;) {
    console.log("Waiting for samples...");
    input.take();
    for (i=1; i <= input.samples.getLength(); i++) {
      if (input.infos.isValid(i)) {
        console.log(JSON.stringify(input.samples.getJSON(i)));
      }
    }

    sleep.sleep(2);
}
