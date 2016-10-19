/*
 * Copyright (c) 2005-2015 Real-Time Innovations, Inc. All rights reserved.
 * Permission to modify and use for internal purposes granted.
 * This software is provided "as is", without warranty, express or implied.
 */

var sleep = require('sleep');
var rti   = require('rticonnextdds-connector');

var connector = new rti.Connector("MyParticipantLibrary::Zero",__dirname + "/../ShapeExample.xml");
var output = connector.getOutput("MyPublisher::MySquareWriter");

var i =0;
for (;;) {
    i = i + 1;
    output.instance.setNumber("x",i);
    output.instance.setNumber("y",i*2);
    output.instance.setNumber("shapesize",30);
    output.instance.setString("color", "BLUE");
    console.log("Writing...");
    output.write();
    sleep.sleep(2);
}
