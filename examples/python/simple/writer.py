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

connector = rti.Connector("MyParticipantLibrary::Zero", filepath + "/../ShapeExample.xml");
output    = connector.getOutput("MyPublisher::MySquareWriter")

for i in range(1,500):
	output.instance.setNumber("x", i);
	output.instance.setNumber("y", i*2);
	output.instance.setNumber("shapesize", 30);
	output.instance.setString("color", "BLUE");
	output.write();
	time.sleep(2)

