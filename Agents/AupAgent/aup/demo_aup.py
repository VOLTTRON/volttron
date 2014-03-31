#!/usr/bin/env python

from aup import do_aup, demo_aup

# This module will implement the AUP method for setting the priority for load curtailment

# The first, represent the pairwise matrix
criteria_labels = ['NO_curtailing', 'deltaT_zone_delta', 'Room_rtu', 'Power_rtu', 'deltaT_zone_sp']
criteria_matrix = [[1.0, 0.25, 3.0, 0.2, 0.2],
                   [4.0, 1.0, 5.0, 3.0, 0.33],
                   [0.33, 0.2, 1.0, 0.2, 0.2],
                   [5.0, 0.33, 5.0, 1.0, 0.33],
                   [5.0, 3.0, 5.0, 3.0, 1.0]]

# Used to print out the matrix
matrix_rowstring = "%20s\t%15.2f%19.2f%10.2f%11.2f%16.2f"
criteria_labelstring = "\t\t\t%15s%19s%10s%11s%16s"

# This matrix will temporarily represent the devices and the measured information.
# This will usually be generated from measurements and the actions of the agent
# Each row represents one device or room, each column represents one of the criteria
# For now, I'm using numbers in place of designations for room type
devices = ["Room1", "Room2", "Room3"]
device_matrix = [[2.0, .2, 3.0, 8.0, .2],
                [5.0, .33, 5.0, 3.2, 1.0],
                [10.0, 1.0, 1.0, 6.4, .33]]


if __name__ == '__main__':
    demo_aup(criteria_matrix, device_matrix, devices, criteria_labels, criteria_labelstring, matrix_rowstring)
    # print do_aup(criteria_matrix, device_matrix, devices)
