# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}
import inspect
import os
import csv
import itertools
import logging
from zmq.utils import jsonapi
import datetime
from Tkinter import *
from tkFileDialog import askopenfilename

from volttron.platform.agent import  utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
from read_csv import read_csv_descList, mdy_hm_to_datetime

def read_oae_csv(mainFileFullName):
    if(not os.path.isfile(mainFileFullName)):
        return (False, 'Missing CSV file "' +mainFileFullName +'"')
    print 'Reading data file...'

    with open(mainFileFullName) as f:
        reader = csv.reader(f, delimiter=',', skipinitialspace=True)
        first_row = next(reader)
        num_cols = len(first_row)
        f.close()

    descList = [
        # Column 1, date, formatted like "5/13/2013 01:00".
        ('Timestamp', mdy_hm_to_datetime, None),
        # Column 2, outside air temperature [F], formatted as floating-point number.
        ('OutsideAirTemp',None,None),
        # # Column 3, return air temperature [F], formatted as floating-point number.
        ('ReturnAirTemp',None,None),
        # # Column 4, mixed air temperature [F], formatted as floating-point number
        ('MixedAirTemp',None,None),
        # Column 5, compressor status formatted as an integer.
        ('CompressorStatus',None,None),
        # Column 6, heating status formatted as an integer.
        ('HeatingStatus',None,None),
        # Column 7, fan status formatted as an integer.
        ('FanStatus',None,None),
        # Column 8, damper command/signal
        ('Damper',None,None)
    ]
    if len(descList) > num_cols:
        print 'Warning data input has fewer columns than required!'
    if len(descList) < num_cols:
        print 'Warning data input has more columns than required'
        
    bldgData = read_csv_descList(mainFileFullName, descList, 1)
    
    return bldgData

def result_writer(contents):
    try:
        home = os.path.expanduser("~")
        dir1 = "workspace/volttron/Agents/PassiveAFDD/passiveafdd/Results"
        dir = os.path.join(home,dir1)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        now = datetime.date.today()
        file_path = os.path.join(dir,"AFDD_Results({ts}).csv".format(ts=now))
        
        ofile = open(file_path, 'w')
        #x = [self.timestamp, self.afdd2_result, self.afdd3_result, self.afdd4_result, self.afdd5_result, self.afdd6_result, self.afdd7_result, self.energy_impact, self.oaf]
        outs = csv.writer(ofile, dialect='excel')
        writer = csv.DictWriter(ofile, fieldnames = ["Timestamp", "OAE1", "OAE2", "OAE3", "OAE4", "OAE5", "OAE6", "Energy_Impact", "OAF"], delimiter = ',')
        writer.writeheader()
       
        for row in itertools.izip_longest(*contents):
            outs.writerow(row)
            #Create monthly plot
        ofile.close()
        print 'Processing Done!'
    except IOError:
        print('Output error please close results file and rerun')
        return
    
def open_file():
    file_path = None
    tk = Tk()
    tk.withdraw() 
    file_path = askopenfilename(defaultextension='.csv', title='choose csv file for AFDD',
                                initialfile='', parent=tk, initialdir = os.path.expanduser('~/workspace'))
    filename, filextension = os.path.spplatformxt(file_path)
    if filextension != '.csv' and filextension !='':
        file_path = 'File Selected is not a csv'
        return file_path
    if file_path != '' and os.path.exists(file_path) and os.path.isfile(file_path):
        file_path = file_path
    tk.destroy()
    return file_path
   
                
    
        