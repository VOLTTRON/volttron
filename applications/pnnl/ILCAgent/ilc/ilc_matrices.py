# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
'''
Copyright (c) 2015, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or
service by trade name, trademark, manufacturer, or otherwise does
not necessarily constitute or imply its endorsement, recommendation,
r favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''
import os
import sys
import operator
import logging
import math
from xlrd import open_workbook
import numpy as np
from datetime import datetime as dt
from volttron.platform.agent import utils
MATRIX_ROWSTRING = "%20s\t%12.2f%12.2f%12.2f%12.2f%12.2f"
CRITERIA_LABELSTRING = "\t\t\t%12s%12s%12s%12s%12s"
DEVICE_ROWSTRING = "%20s%15.2f%12.2f%12.2f%12.2f%12.2f%12.2f%12.2f"
DEVICE_LABELSTRING = "\t\t\t%12s%12s%12s%12s%12s%12s%12s"

utils.setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')


def open_file():
    '''Create file input window for user.'''
    from Tkinter import Tk
    from tkFileDialog import askopenfilename
    file_path = None
    supported_files = ['xlsx', 'xls']
    tk = Tk()
    tk.withdraw()
    file_path = \
        askopenfilename(defaultextension='.xlsx',
                        title='choose excel file for AHP',
                        initialfile='',
                        parent=tk,
                        initialdir=os.path.realpath(__file__))
    _, filextension = os.path.splitext(file_path)
    if ([ext for ext in supported_files if ext == filextension] and
            filextension != ''):
        file_path = ('File Selected is not a supported '
                     'type (xlsx or xls)')
        return file_path
    if (file_path != '' and os.path.exists(file_path) and
            os.path.isfile(file_path)):
        file_path = file_path
    tk.destroy()
    return file_path


def extract_criteria(excel_file, sheet):
    '''Function to extract the criteria matrix from

    the CriteriaMatrix sheet of the excel spreadsheet
    '''
    # Open the excel file
    wb = open_workbook(excel_file)

    # Access the "CriteriaMatrix" sheet
    sheet = wb.sheet_by_name(sheet)

    criteria_labels = []
    criteria_matrix = []
    # Matrix starts at row 3 (column headers, which are
    # duplicated by column A) and runs until "Column Sum"
    for row in range(3, sheet.nrows):
        if(sheet.cell(row, 0).value == ""):
            break
        criteria_labels.append(sheet.cell(row, 0).value)
    criteria_labels.pop()
    # NOTE: the number of rows and number of columns should match
    # Iterate over the rows and columns of the spreadsheet loading
    # the numbers as floating point values into a list of lists.
    for row in range(3, 3 + len(criteria_labels)):
        temp_row = []
        for col in range(1, 1 + len(criteria_labels)):
            temp_row.append(float(sheet.cell(row, col).value))
        criteria_matrix.append(temp_row)

    return criteria_labels, criteria_matrix


def calc_column_sums(criteria_matrix):
    '''Calculate the column sums for the criteria matrix.'''
    j = 0
    csum = []
    while j < len(criteria_matrix[0]):
        col = [float(row[j]) for row in criteria_matrix]
        csum.append(sum(col))
        j += 1
    return csum


def normalize_matrix(criteria_matrix, col_sums):
    '''Normalizes the members of criteria matrix using the vector

    col_sums. Returns the normalized matrix, and the sums of each
    row of the matrix.
    '''
    normalized_matrix = []
    rowsums = []
    i = 0
    while i < len(criteria_matrix):
        j = 0
        norm_row = []
        while j < len(criteria_matrix[0]):
            norm_row.append(
                criteria_matrix[i][j]/(col_sums[j] if col_sums[j] != 0
                                       else 1))
            j += 1
        rowsum = sum(norm_row)
        norm_row.append(rowsum/j)
        rowsums.append(rowsum/j)
        normalized_matrix.append(norm_row)
        i += 1
    return normalized_matrix, rowsums


# Validates the criteria matrix to ensure that the inputs are internally consistent
# Returns a True if the matrix is valid, and False if it is not.
def validate_input(pairwise_matrix, col_sums, display=False,
                   criteria_LABELS="", CRITERIA_LABELSTRING="",
                   MATRIX_ROWSTRING="", display_dest=sys.stdout):
    '''Validates the criteria matrix to ensure that the inputs are

    internally consistent. Returns a True if the matrix is valid,
    and False if it is not.
    '''
    # Calculate row products and take the 5th root
    _log.info("Validating matrix")
    random_index = [0, 0, 0, 0.58, 0.9, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
    roots = []
    for row in pairwise_matrix:
        roots.append(math.pow(reduce(operator.mul, row, 1), 1.0/5))
    display_matrix([roots, ], CRITERIA_LABELSTRING,
                   criteria_LABELS, ['5th root of product'],
                   MATRIX_ROWSTRING, display_dest) \
        if display else ""
    # Sum the vector of products
    root_sum = sum(roots)
    # Calculate the priority vector
    priority_vec = []
    for item in roots:
        priority_vec.append(item / root_sum)

    display_matrix([priority_vec, ], CRITERIA_LABELSTRING,
                   criteria_LABELS, ['Priority Vector'],
                   MATRIX_ROWSTRING, display_dest) \
        if display else ""
    # Calculate the priority row
    priority_row = []
    for i in range(0, len(col_sums)):
        priority_row.append(col_sums[i] * priority_vec[i])

    display_matrix([priority_row, ], CRITERIA_LABELSTRING,
                   criteria_LABELS, ['Priority Row'],
                   MATRIX_ROWSTRING, display_dest) \
        if display else ""

    # Sum the priority row
    priority_row_sum = sum(priority_row)
    if display:
        print >> display_dest, "Priority row sum: ", priority_row_sum

    # Calculate the consistency index
    consistency_index = \
        (priority_row_sum - len(col_sums))/(len(col_sums) - 1)

    if display:
        print >> display_dest, "Consistency Index:", consistency_index

    # Calculate the consistency ratio
    consistency_ratio = consistency_index / random_index[len(col_sums)]

    if display:
        print >> display_dest, "Consistency Ratio:", consistency_ratio
    return consistency_ratio < 0.2


def build_score(_matrix, weight):
    '''Calculates the curtailment score using the normalized matrix m,

    and the weights vector returns a sorted vector of weights for each
    device that is a candidate for curtailment.
    '''
    input_keys, input_values = _matrix.keys(), _matrix.values()
    scores = []
    for i in range(0, len(input_values) - 1):
        criteria_sum = 0
        for j in range(0, len(weight) - 1):
            criteria_sum += input_values[i][j] * weight[j]
        scores.append(criteria_sum)
    return scores, input_keys


def display_matrix(_matrix, LABELString, xLABELS, yLABELS,
                   rowstring, display_func=sys.stdout):
    '''Function to diplay the critieria matrix.'''
    # Display header
    xLABELS = [item.encode('utf-8') for item in xLABELS]
    print >> display_func, LABELString % tuple(xLABELS)
    i = 0
    while i < len(yLABELS):
        print >> display_func, \
                 rowstring % ((yLABELS[i],) + tuple(_matrix[i]))
        i += 1

def history_data(device, device_data, point_list):
            '''Store historical data on devices for use in "Input Matrix."'''
            data = {}
            for point in point_list:
                try:
                    value = device_data[point]
                except KeyError:
                    _log.error('Data names in point_list in config file do '
                               'not match available data published by device '
                               'drivers.')
                data.update({device: {point: value}})
            data[device].update({'date': dt.now()})
            return data

def input_matrix(builder, criteria_labels):
    '''Construct input normalized input matrix.'''
    sum_mat = {}
    inp_mat = {}
    label_check = builder.values()[-1].keys()
    if set(label_check) != set(criteria_labels):
        raise Exception('Input criteria and data criteria do not match.')
    for device_data in builder.values():
        for k,v in device_data.items():
            sum_mat[k] = v if k not in sum_mat else sum_mat[k] + v
    for key in builder:
        inp_mat[key] = [builder[key][tag]/sum_mat[tag] for tag in criteria_labels]
    
    return inp_mat
