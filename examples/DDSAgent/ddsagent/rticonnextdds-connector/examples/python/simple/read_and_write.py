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
input  = connector.getInput("MySubscriber::MySquareReader");
output = connector.getOutput("MyPublisher::MySquareWriter")

for i in range(1,500):
	input.take();
	numOfSamples = input.samples.getLength();
	for j in range (1, numOfSamples+1):
		if input.infos.isValid(j):
			sample = input.samples.getDictionary(j); #this gives you a dictionary
			tmp = sample['x'];
			sample['x'] = sample['y'];
			sample['y'] = tmp
			sample['color'] = 'RED'
			output.instance.setDictionary(sample);
			output.write();
	time.sleep(2);
