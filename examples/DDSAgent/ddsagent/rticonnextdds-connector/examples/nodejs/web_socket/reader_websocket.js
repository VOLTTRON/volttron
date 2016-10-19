/*****************************************************************************
*    (c) 2005-2015 Copyright, Real-Time Innovations, All rights reserved.    *
*                                                                            *
* RTI grants Licensee a license to use, modify, compile, and create          *
* derivative works of the Software.  Licensee has the right to distribute    *
* object form only for use with RTI products. The Software is provided       *
* "as is", with no warranty of any type, including any warranty for fitness  *
* for any purpose. RTI is under no obligation to maintain or support the     *
* Software.  RTI shall not be liable for any incidental or consequential     *
* damages arising out of the use or inability to use the software.           *
*                                                                            *
******************************************************************************/

var http  = require('http');
var fs    = require('fs');
var rti   = require('rticonnextdds-connector');

var connector = new rti.Connector("MyParticipantLibrary::Zero",__dirname + "/../ShapeExample.xml");
var input = connector.getInput("MySubscriber::MySquareReader");

var server = http.createServer(function (req, res) {
	if (req.url=="/simple") {
        fs.readFile(__dirname + "/indexShape.html", function(error, data) {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(data, 'utf-8');
        });
    } else if (req.url=="/chart") {
	  fs.readFile(__dirname + '/indexChart.html', function(error, data) {
	    res.writeHead(200, { 'Content-Type': 'text/html' });
	    res.end(data, 'utf-8');
	  });
    } else if (req.url == "/earth") {
      fs.readFile(__dirname + '/indexEarth.html', function(error, data) {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(data, 'utf-8');
      });
    } else {
      res.writeHead(200, {'Content-Type': 'text/html'});
      res.write("Click <a href='simple'>simple</a>, <a href='chart'>D3 chart</a> or <a href='earth'>earth</a>");
      res.end();
    }
	}).listen(7400, "127.0.0.1");
console.log('Server running at http://127.0.0.1:7400/');

var io = require('socket.io').listen(server);

connector.on('on_data_available',
   function() {
       console.log('on_dat');
       input.take();
       console.log(input.samples.getLength());
       for (i=1; i <= input.samples.getLength(); i++) {
         if (input.infos.isValid(i)) {  
           console.log('is valid');     
           var jsonObj = input.samples.getJSON(i);
           console.log(JSON.stringify(jsonObj));
           io.sockets.emit('shape', jsonObj);
        }
   }
});
