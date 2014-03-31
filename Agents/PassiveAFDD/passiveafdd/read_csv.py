"""
Read a comma-separated value (CSV) file, given a description of its contents.


**Notes:**

The description of the CSV file contents is contained in a description list,
or a ``descList``.

A sample ``descList`` looks like::

  descList = [('date',convert_dateStr,None), ('demand',float,float('nan')), None, 'oat']

This ``descList`` says the CSV file has four columns of interest (though it may
have more columns).

The first item, ``('date',convert_dateStr)``, says:

- Name the first column of the CSV file as 'date' in the returned data.
- Apply conversion function ``convert_dateStr`` to file entries.
- Use ``None`` as the default.

The second item, ``('demand',float,float('nan'))``, says:

- Name the second column of the CSV file as 'demand' in the returned data.
- Apply conversion function ``float`` to file entries.
- Use ``float('nan')``, i.e., not-a-number or ``NAN``, as the default.

The third item, ``None``, says:

- Skip the third column of the CSV file (i.e., do not return it).

The fourth item, ``'oat'``, says:

- Name the fourth column of the CSV file as 'oat' in the returned data.
- Read that column as a floating-point number.
- Use ``NAN`` as the default.

Semi-formally, a ``descList`` is::

  descList = [colDesc, colDesc, ...]
  colDesc = colDescTuple | colName | None
  colDescTuple = (colName, colReadFcn, colDefault)
  colName = Python string
  colReadFcn = function | lambda expression | type operator | None
  colDefault = Python object

These are used as follows:

- *colName* gives the name by which to access the returned data.
- *colReadFcn* maps a string read from the file into an object to be returned.
- *colDefault* is the value used if the file has no entry for the requested
  column in a non-empty row.
- If only *colName* is declared, then *colReadFcn* == ``float`` and
  *colDefault* == ``NAN`` (not-a-number) for the corresponding column.
- If *colReadFcn* is ``None``, the entry is returned as a string, exactly as
  read from the file.
- *colReadFcn* can return different types of objects, depending on the input.
- If *colReadFcn* raises an exception, processing stops.
- *colDefault* can have any type.  Its type does not have to match those
  returned by *colReadFcn*.
- If *colDesc* is ``None``, i.e., the literal Python ``None``, it means to skip
  the column.

**Enhancements:**

- Consider generalizing the column descriptors so that a single column of
  returned data could come out of multiple columns in the CSV file.  For example,
  consider a time format where year, month, day, and so on appear in individual
  columns of the CSV file.  The *descList* could specify that columns 1--3 are
  to be passed to a *colReadFcn* that accepts multiple arguments, and which
  could then form the date information.
"""

# TODO: Pull out information above into its own module, with a fcn that
# assembles ``descList`` objects.


#--- Provide access.
#
import csv


def read_csv_descList(fileName, descList,
    headerLineCt):
    """
    Read a CSV file according to the user-provided description list.

    **Arguments:**

    - *fileName*, name of CSV file to read.
    - *descList*, list of column descriptors, such as ``('demand',float,float('nan'))``
      or ``None``.  For a complete description, see the module-level comments
      for :mod:`file_read.read_csv`.
    - *headerLineCt*, number of lines to skip at head of file.

    **Returns:**

    - *colDict*, Python dictionary.  Each entry in *colDict* maps a column name,
      as specified in *descList*, to a list containing the objects read from the
      file.  For example, a description list item ``'oat'`` will yield an entry
      ``colDict['oat']`` that maps to a list of corresponding values from the file.

    **Raises:**

    - For a bad *descList*.
    - For a structural problem that makes it impossible to parse the CSV file.
    - For a problem applying a *colReadFcn* to an item from the CSV file.

    **Enhancements:**

    - Let caller pass in a :class:`csv.Dialect` object to configure the CSV-reader.
    - Add option to verify contents of header row.
    - Allow comments to define blank lines.
    """
    #
    # Check inputs.
    assert( type(descList) == list )
    assert( len(descList) > 0 )
    #
    # Implementation note - :func:`np.genfromtxt`.
    #   An earlier version of this function used ``np.genfromtxt``.
    #   Unfortunately, while that function handles empty columns, it does not
    # fill in missing columns.  For example, if a CSV file has a line like
    # "1,,3", then ``np.genfromtxt`` can catch the missing value in the second
    # column.  However it cannot, apparently, fill in a default for the fourth
    # column.  To get it to recognize the fourth column as having a missing
    # value, it seems necessary for the CSV file to have a trailing comma.  For
    # example, "1,,3," would do.  Of course, there may be some way to get
    # ``np.genfromtxt`` to catch that missing fourth column.  However, it was
    # not apparent from the documentation, and a number of comments on
    # Stack Overflow stated flat-out it is not possible.
    #   This rewrite is a little more flexible, anyway, since it returns Python
    # lists rather than a numpy array.  Therefore it can handle non-homogeneous
    # data.  Using a dictionary also allows the user to supplement the returned
    # data structure with other objects that have different lengths than the
    # data returned from the CSV file.
    #
    # Initialize.
    colNums = list()
    colNames = list()
    colReadFcns = list()
    colDefaults = list()
    #
    # Unpack *descList*.
    currColNum = 0
    for colDesc in descList:
        #
        if( type(colDesc) == str ):
            #
            # Here, *colDesc* is a string like 'oat'.  Treat it as the *colName*
            # for a column of floats.
            colNums.append(currColNum)
            colNames.append(colDesc)
            colReadFcns.append(float)
            colDefaults.append(float('nan'))
        elif( type(colDesc) == tuple ):
            # Here, *colDesc* should be a tuple (colName, colReadFcn, colDefault),
            # for example, ('demand', float, float('nan')).
            if( len(colDesc) != 3 ):
                raise Exception('Expect three entries in column description tuple {' +str(colDesc) +'}')
            colName = colDesc[0]
            if( type(colName) != str ):
                raise Exception('Expect entry #1 in column description tuple {' +str(colDesc) +
                    '} to be a string naming the column')
            colReadFcn = colDesc[1]
            if( not (colReadFcn is None or hasattr(colReadFcn, '__call__')) ):
                raise Exception('Expect entry #2 in column description tuple {' +str(colDesc) +
                    '} to be "None" or callable')
            colNums.append(currColNum)
            colNames.append(colName)
            colReadFcns.append(colReadFcn)
            colDefaults.append(colDesc[2])
        elif( colDesc is not None ):
            # Here, unknown *colDesc*.
            #   Note that if *colDesc* is ``None``, means skip column *currColNum*
            # in the CSV file.  Accomplish this by not putting an entry in *colNums*.
            raise Exception('Unrecognized column description {' +str(colDesc) +'}')
        #
        # Here, done processing the current *colDesc*.
        #
        # Prepare for next iteration.
        currColNum += 1
    #
    # Here, done processing *descList*.
    #
    # Prepare *colDict*.
    seekColCt = len(colNames)
    if( seekColCt == 0 ):
        raise Exception('Description list names no columns')
    colDict = dict()
    for colName in colNames:
        if( colName in colDict ):
            raise Exception('Description list cannot have more than one column named "' +colName +'"')
        colDict[colName] = list()
    #
    # Read the CSV file.
    with open(fileName, 'rU') as csvFile:
        #
        csvReader = csv.reader(csvFile, skipinitialspace=True, strict=True)
        #
        # Consume header rows.
        if( headerLineCt > 0 ):
            for rowList in csvReader:
                headerLineCt -= 1
                if( headerLineCt == 0 ):
                    break
        #
        # Process all remaining rows.
        for rowList in csvReader:
            #
            gotColCt = len(rowList)
            if( gotColCt == 0 ):
                # TODO: Need to test how *csvReader* actually handles blank rows.
                continue
            #
            for seekIdx in range(seekColCt):
                #
                # Use default for missing column.
                colIdx = colNums[seekIdx]
                if( colIdx >= gotColCt ):
                    colDict[colNames[seekIdx]].append(colDefaults[seekIdx])
                    continue
                #
                # Get column entry.
                colEntryStr = rowList[colIdx].strip()
                #
                # Use default for empty column.
                if( len(colEntryStr) == 0 ):
                    colDict[colNames[seekIdx]].append(colDefaults[seekIdx])
                    continue
                #
                # Accept string as-is for missing *colReadFcn*.
                colReadFcn = colReadFcns[seekIdx]
                if( colReadFcn is None ):
                    colDict[colNames[seekIdx]].append(colEntryStr)
                    continue
                #
                # Convert column entry.
                try:
                    colEntry = colReadFcn(colEntryStr)
                except:
                    raise Exception('Cannot convert CSV file entry "' +colEntryStr +
                        '" in column ' +str(colIdx+1) +
                        ' of row ' +str(csvReader.line_num))
                    colEntry = colDefaults[seekIdx]
                    colDict['exceptionCt'][seekIdx] += 1
                colDict[colNames[seekIdx]].append(colEntry)
            #
            # Here, done processing a row from the CSV file.
        #
        # Here, done processing all rows of CSV file.
    #
    return( colDict )
    #
    # End :func:`read_csv_descList`.
    """
Convert date and time strings to :mod:`datetime` objects.

The functions in this module simply wrap :meth:`datetime.strptime`.
They are provided as a convenience, for situations that require a function that
takes a single string argument and returns a :class:`datetime.datetime` object.
"""


#--- Provide access.
#
import datetime as dto


def mdy_hms_to_datetime(dateStr):
    """
    Convert date string, in ``mm/dd/yyyy hh:mm:ss`` format, to a :class:`datetime.datetime` object.

    **Notes:**

    - For two-digit entries, one digit is fine, e.g., ``mm`` can be '1' or '01'.
    - For ``yyyy``, year must have four digits.
    - For ``hh``, 24-hour number.
    """
    #
    return( dto.datetime.strptime(dateStr, '%m/%d/%Y %H:%M:%S') )


def mdy_hm_to_datetime(dateStr):
    """
    Convert date string, in ``mm/dd/yyyy hh:mm`` format, to a :class:`datetime.datetime` object.

    **Notes:**

    - For two-digit entries, one digit is fine, e.g., ``mm`` can be '1' or '01'.
    - For ``yyyy``, year must have four digits.
    - For ``hh``, 24-hour number.
    """
    #
    return( dto.datetime.strptime(dateStr, '%m/%d/%Y %H:%M') )


def dmy_hm_to_datetime(dateStr):
    """
    Convert date string, in ``dd/mm/yyyy hh:mm`` format, to a :class:`datetime.datetime` object.

    **Notes:**

    - For two-digit entries, one digit is fine, e.g., ``mm`` can be '1' or '01'.
    - For ``yyyy``, year must have four digits.
    - For ``hh``, 24-hour number.
    """
    #
    return( dto.datetime.strptime(dateStr, '%d/%m/%Y %H:%M') )

    
def ymd_hms_to_datetime_dash(dateStr):
    """
    Convert date string, in ``yyyy-mm-dd hh:mm:ss`` format, to a :class:`datetime.datetime` object.

    **Notes:**

    - For two-digit entries, one digit is fine, e.g., ``mm`` can be '1' or '01'.
    - For ``yyyy``, year must have four digits.
    - For ``hh``, 24-hour number.
    """
    #
    return( dto.datetime.strptime(dateStr, '%Y-%m-%d %H:%M:%S') )
