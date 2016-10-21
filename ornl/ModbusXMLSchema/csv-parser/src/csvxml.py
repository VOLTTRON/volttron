# Copyright (c) 2014 Oak Ridge National Laboratory
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sellcopies of the Software, and to permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
# EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
# THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Author: Jibo Sanyal
# Date: 28 April 2014
#
# Description: Some users might need to customize the 'generateXMLfunctionBlock' function to add additional
# processing logic to handle specific translations from the csv register map to generate valid XML. The
# example in this case promotes the read vales of int8 to INT8, Low byte to Lower Byte, etc.
#
# Known bugs and limitations:
#   1. Unicode characters in the csv files are not supported, mainly becuase of Python 3.
#   2. Return codes for all functions are not checked always.
#   3. The code could use several try-except blocks, but the purpose is to provide an XML generator template.
#   

import sys
import xml.etree.ElementTree
import xml.dom.minidom
from xml.sax.saxutils import escape
import csv
import difflib
import operator
import re
import argparse
import configparser
import os
import string
    

# Function main wehich is called at the end of this script
def main():
    # Parse arguments
    argparser = argparse.ArgumentParser(description='Creates an XML file from a Modbus device address map.')
    argparser.add_argument('device_ini_file', help='ini-style file that provides device meta information')
    argparser.add_argument("-i", "--interactive", help="run interactively", action="store_true")
    
    args = argparser.parse_args()
    
    # Set True if interactive; False otherwise
    isInteractive = args.interactive

    # Parse device ini file
    deviceini = configparser.ConfigParser( allow_no_value = True )
    deviceini.read( args.device_ini_file )

    # Read in filenames
    csvFileName = deviceini.get('Input/Output', 'address_map_csv_file')
    xmlFileName = deviceini.get('Input/Output', 'output_xml_file')

    # Set output filename if not provided in ini file
    if not xmlFileName:
        fileName, fileExtension = os.path.splitext(args.device_csv_file)
        xmlFileName = fileName + ".xml"

    # Create the XML
    xmlstr = csv_to_xml(deviceini, csvFileName, isInteractive)


    # Write out an XML file
    try:
        xmlroot = xml.dom.minidom.parseString(xmlstr)
        xmlstr = xmlroot.toprettyxml()
        with open(xmlFileName, 'w') as xmlfile:
            xmlfile.write(xmlstr)
    except:
        print ("*** Error encountered: ", sys.exc_info()[0])
        print ("*** The xml string should still be saved to " + xmlFileName)
        with open(xmlFileName, 'w') as xmlfile:
            xmlfile.write(xmlstr)



# Most users, if they need to write custom code to process different CSV columns differently, will have to make
# changes to this function here. For the sake of lucidity, each XML element is processed separately. this also
# allows implementation of custom processing for any one field or column easy to implement. The examples here are
# for the fields of length, format, multiplier, and read and write codes.
def generateXMLfunctionBlock(deviceini, csvColumnIndices, csvRows, selectedMatchKey):
    xmlBlock = ''

    # handle 'description'
    elementKey = 'description'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'

    # handle 'addresses'
    elementKey = 'addresses'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'

    # handle 'length'
    elementKey = 'length'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal == 'Low byte':
            elementVal = 'Lower byte'
        if elementVal == 'Full':
            elementVal = 'Full word'
        if elementVal.upper() == 'NOT USE':
            elementVal = ''
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'
            
    # handle 'count'
    elementKey = 'count'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'
            
    # handle 'format'
    elementKey = 'format'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        elementVal = elementVal.upper()
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'
            
    # handle 'block_label'
    elementKey = 'block_label'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'
            
    # handle 'multiplier'
    elementKey = 'multiplier'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal == '0.1(?)':
            elementVal = '0.1'
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'
            
    # handle 'units'
    elementKey = 'units'
    columnVal = csvColumnIndices[elementKey]
    if columnVal != '':
        elementVal = str(csvRows[selectedMatchKey][columnVal])
        if elementVal != '':
            xmlBlock += '<' + elementKey + '>'  + escape(elementVal) + '</' + elementKey + '>'
            
    # handle 'read_function_code'
    elementKey = 'read_function_code'
    userColumnIndexA = deviceini.getint('Additional Column/Field Indices', 'operation_info')
    columnVal = str(csvRows[selectedMatchKey][userColumnIndexA])
    if columnVal != '':
        if 'R' in columnVal:
            xmlBlock += '<' + elementKey + '>'  + 'Enter read function code snippet here or adding a ' \
                        + 'user defined csv column and add parsing logic' + '</' + elementKey + '>'
            
    # handle 'write_function_code'
    elementKey = 'write_function_code'
    userColumnIndexA = deviceini.getint('Additional Column/Field Indices', 'operation_info')
    columnVal = str(csvRows[selectedMatchKey][userColumnIndexA])
    if columnVal != '':
        if 'W' in columnVal:
            xmlBlock += '<' + elementKey + '>'  + 'Enter write function code snippet here or adding a ' \
                        + 'user defined csv column and add parsing logic' + '</' + elementKey + '>'
          
    return xmlBlock



# Returns a blank string; used for handling optional column indices
def to_number(s):
    try:
        return int(s)
    except ValueError:
        return ''



# Most of the parsing, string matching, and string distance calculation performed in this function
def csv_to_xml(deviceini, csvFileName, isInteractive):
    # Read in column indices and create the dictionary
    csvColumnIndices = {}
    for (key, val) in deviceini.items('Column/Field Indices'):
        csvColumnIndices[key] = to_number(val)

    # Read in function name synonyms
    searchRows = []
    for (key, val) in deviceini.items('Function Name Search Synonyms'):
        keyval = val.split(',')
        
        # add key to the front of this list
        keyval.insert(0, key)
        
        # strip out white spaces in the list elements
        keyval = [kv.strip() for kv in keyval]
        searchRows.append(keyval)
        
    #print (searchRows)
    
    # Read in the address map from csv file skipping 'lines_to_skip' number of lines from top
    csvRows = []    
    with open(csvFileName, newline="") as csvFile:
        csvFileReader = csv.reader(csvFile, dialect="excel")
        counter = 0      
        for row in csvFileReader:
            if (counter+1) > deviceini.getint('Input/Output', 'lines_to_skip'):
                csvRows.append(row)
            counter = counter + 1

    # xml header
    xml = '<?xml version="1.0" encoding="US-ASCII"?>'
    xml += '<device xmlns="http://www.ornl.gov/ModbusXMLSchema">'
    xml += '<name>'        + deviceini.get('Modbus Device', 'device_name')        + '</name>'
    xml += '<description>' + deviceini.get('Modbus Device', 'device_description') + '</description>'

    for searchRow in searchRows:
        matchList = []
        print ( "\n")
        print( 'Function: ', searchRow[0] )
        print( 'Synonyms: ', ','.join(searchRow[1:]) )
        xml += '<function>'

        # create exact match list first
        exactMatchList = []
        for csvRowIndex, csvRow in enumerate (csvRows):
            # all lowercase and replace all double or more spaces with single
            descriptionStr = csvRow[csvColumnIndices['description']].lower()
            descriptionStr = re.sub(' +',' ', descriptionStr)

            # loop over all synonyms and grab first exact match
            for searchStr in searchRow[5:len(searchRow)]:
                # all lowercase and replace all double or more spaces with single
                searchStr = searchStr.lower()              
                searchStr = re.sub(' +',' ', searchStr)
                if searchStr in descriptionStr:
                    exactMatchList.append( csvRowIndex )
                    break
        
        for csvRowIndex, csvRow in enumerate (csvRows):
            # if csvRowIndex is one of the exact matches,
            # or if exact match list is empty, meaning no exact matches

            if csvRowIndex in exactMatchList or len(exactMatchList) == 0:
                # all lowercase and replace all double or more spaces with single
                descriptionStr = csvRow[csvColumnIndices['description']].lower()
                descriptionStr = re.sub(' +',' ', descriptionStr)

                # loop over all synonyms and grab best ratio
                bestRatio = -1
                for searchStr in searchRow[1:len(searchRow)]:
                    # all lowercase and replace all double or more spaces with single
                    searchStr = searchStr.lower()              
                    searchStr = re.sub(' +',' ', searchStr)   
                    diffRatio = difflib.SequenceMatcher(None, searchStr , descriptionStr).ratio()
                    if diffRatio > bestRatio:
                        bestRatio = diffRatio
                        
                # save the best similarity ratio found
                matchList.append( [csvRowIndex, bestRatio] )

        # sort descending on match ratio
        matchList.sort(key = operator.itemgetter(1), reverse=True)

        # use first matched value if isInteractive = false
        selectedMatchKey = matchList[0][0]

        # else present exact matches first for a selection

        if isInteractive == True:
            # present best matches 
            validIndices = []

            for match in matchList:
                validIndices.append(match[0])
                
            for index in validIndices:
                print( '[', index, ']', csvRows[index] )
            
                
            while True:
                print( '\n  For function: ', searchRow[0] )
                print( '  With synonyms: ', ','.join(searchRow[1:]) )
                if len(exactMatchList) == 0:
                    print( "  There were no exact matches. Fuzzy matches only." )
                else:
                    print( "  Exact matches ordered by fuzzy similarity." )
                entered = input("  Enter the matching row number from matches above: ")                
                try:
                    entered = int(entered)
                    if entered in validIndices:
                        selectedMatchKey = entered
                        break
                    else:
                        print( "*** Error: Entered number does not match row indices. ***" )
                except:
                    print( "*** Error: Invalid response. Please enter one of the row indices. ***" )
                

        # Generate the XML block
        xml += '<name>' + searchRow[0] + '</name>'
        xml += generateXMLfunctionBlock(deviceini, csvColumnIndices, csvRows, selectedMatchKey)
        xml += '</function>';

    
    xml += '</device>'
    return xml




# Main program begins here

if __name__ == '__main__':
    main()

