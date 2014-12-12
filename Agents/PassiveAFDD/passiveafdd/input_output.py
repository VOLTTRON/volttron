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
import os
import pandas
import csv
import itertools
from zmq.utils import jsonapi
import dateutil
import imp
try:
    imp.find_module('Tkinter')
    from Tkinter import *
    from tkFileDialog import askopenfilename
    found = True
except ImportError:
    found = False
from volttron.platform.agent import  utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
  
def read_oae_pandas(mainFileFullName, data_tags):
    '''Parse metered data for RTU or AHU and provide to diagnostic algorithms.
    
    Uses panda library to efficiently parse the csv data and returns a
    panda time-serires.
    '''
    if(not os.path.isfile(mainFileFullName)):
        return (False, 'Missing CSV file "' + mainFileFullName +'"')
    data = pandas.read_csv(mainFileFullName, error_bad_lines=False, sep=',')
    data = data.dropna()
    return data

def result_writer(contents):
    '''Data is aggregated into hourly or smaller intervals based on compressor
    status, heating status, and supply fan status for analysis.  
    
    result_writer receives the diagnostic results and associated energy impact
    and writes the values to csv.
    '''
    try:
        file_dir = os.path.dirname(__file__)
        dir1 = "Results"
        dir = os.path.join(file_dir, dir1)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        now = datetime.date.today()
        file_path = os.path.join(dir,"AFDD_Results({ts}).csv".format(ts=now))
        ofile = open(file_path, 'w')
        outs = csv.writer(ofile, dialect='excel')
        writer = csv.DictWriter(ofile, fieldnames = ["Timestamp", "OAE1",
                                                     "OAE2","OAE3", "OAE4",
                                                     "OAE5", "OAE6",
                                                     "Energy_Impact", "OAF"],
                                delimiter = ',')
        writer.writeheader()
        for row in itertools.izip_longest(*contents):
            outs.writerow(row)
        ofile.close()
        print 'Processing Done!'
    except IOError:
        print('Output error please close results file and rerun.')
        return
    
def open_file():
    '''Create file input window for user.'''
    file_path = None
    if found:
        tk = Tk()
        tk.withdraw() 
        file_path = askopenfilename(defaultextension='.csv',
                                    title='choose csv file for AFDD',
                                    initialfile='',
                                    parent=tk,
                                    initialdir = os.path.realpath(__file__))
        filename, filextension = os.path.splitext(file_path)
        if filextension != '.csv' and filextension !='':
            file_path = 'File Selected is not a csv'
            return file_path
        if (file_path != '' and os.path.exists(file_path) and 
                os.path.isfile(file_path)):
            file_path = file_path
        tk.destroy()
    return file_path

        