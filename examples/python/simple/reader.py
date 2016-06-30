##############################################################################
# Copyright (c) 2005-2015 Real-Time Innovations, Inc. All rights reserved.
# Permission to modify and use for internal purposes granted.
# This software is provided "as is", without warranty, express or implied.
##############################################################################

import sys
import os
filepath = os.path.dirname(os.path.realpath(__file__))
sys.path.append(filepath + "/../../../");
import time
import rticonnextdds_connector as rti


connector = rti.Connector("MyParticipantLibrary::Zero",filepath + "/../ShapeExample.xml");
input = connector.getInput("MySubscriber::MySquareReader");

for i in range(1,500):
	input.take();
	numOfSamples = input.samples.getLength();
	for j in range (1, numOfSamples+1):
		if input.infos.isValid(j):
			sample = input.samples.getDictionary(j); #this gives you a dictionary
			x = sample['x']; #you can access the dictionary...
			y = sample['y'];
			size = input.samples.getNumber(j, "shapesize"); #or, if you need a single field, you can just access the field directly
			color = input.samples.getString(j, "color");
			toPrint = "Received x: " + repr(x) + " y: " + repr(y) + " size: " + repr(size) + " color: " + repr(color);
			print(toPrint);
	time.sleep(2);
