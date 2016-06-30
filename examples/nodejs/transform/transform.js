/*
 * Copyright (c) 2005-2016 Real-Time Innovations, Inc. All rights reserved.
 * Permission to modify and use for internal purposes granted.
 * This software is provided "as is", without warranty, express or implied.
 */

var sleep = require('sleep');
var rti   = require('rticonnextdds-connector');

var connector = new rti.Connector("MyParticipantLibrary::Zero",__dirname + "/../ShapeExample.xml");
var input = connector.getInput("MySubscriber::MySquareReader");
var output = connector.getOutput("MyPublisher::MySquareWriter");

connector.on('on_data_available',
   function() {
     input.take();
     for (i=1; i <= input.samples.getLength(); i++) {
         if (input.infos.isValid(i)) {
             //get the received sample
             var mysample = input.samples.getJSON(i)
             //change the color
             mysample.color = 'YELLOW'
            //set the sample to write
            output.instance.setFromJSON(mysample);
            //write
            console.log("Writing...");
            output.write();
         }
     }

});

console.log("Waiting for data");
